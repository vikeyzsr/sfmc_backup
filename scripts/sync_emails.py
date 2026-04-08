#!/usr/bin/env python3
"""Fetch all SFMC Content Builder email assets and write them as individual HTML files.

Credentials are read from environment variables:
    SFMC_CLIENT_ID
    SFMC_CLIENT_SECRET
    SFMC_SUBDOMAIN

Output:
    email-content/{id}_{name}.html   -- one file per email
    email-content/manifest.json      -- metadata index of every email
    email-content/CHANGELOG.md       -- running history of changes
    email-content/.commit-summary    -- consumed by the workflow for the commit message
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "email-content"

EMAIL_TYPE_IDS = [207, 208, 209]  # templatebasedemail, htmlemail, textonlyemail
PAGE_SIZE = 2500

CHANGELOG_FILE = OUTPUT_DIR / "CHANGELOG.md"
COMMIT_SUMMARY_FILE = OUTPUT_DIR / ".commit-summary"
IGNORED_FILES = {"manifest.json", "CHANGELOG.md", ".commit-summary"}


# ---------------------------------------------------------------------------
# SFMC Authentication
# ---------------------------------------------------------------------------

def authenticate(client_id: str, client_secret: str, subdomain: str) -> tuple[str, str]:
    """Return (access_token, rest_base_url) via client_credentials grant."""
    auth_url = f"https://{subdomain}.auth.marketingcloudapis.com/v2/token"
    resp = httpx.post(
        auth_url,
        json={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    rest_url = data.get("rest_instance_url", f"https://{subdomain}.rest.marketingcloudapis.com")
    return data["access_token"], rest_url.rstrip("/")


# ---------------------------------------------------------------------------
# Content Builder API
# ---------------------------------------------------------------------------

def fetch_all_emails(token: str, rest_url: str) -> list[dict[str, Any]]:
    """Paginate through the Content Builder Asset query and return all email items."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    all_items: list[dict[str, Any]] = []
    page = 1

    while True:
        body: dict[str, Any] = {
            "page": {"page": page, "pageSize": PAGE_SIZE},
            "query": {
                "property": "assetType.id",
                "simpleOperator": "in",
                "value": EMAIL_TYPE_IDS,
            },
        }
        resp = httpx.post(
            f"{rest_url}/asset/v1/content/assets/query",
            headers=headers,
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        all_items.extend(items)

        count = data.get("count", 0)
        print(f"  Page {page}: {len(items)} items (total {len(all_items)}/{count})")

        if not items or page * PAGE_SIZE >= count:
            break
        page += 1

    return all_items


# ---------------------------------------------------------------------------
# File writing with change detection
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\s\-]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name or "unnamed"


def _email_metadata(item: dict[str, Any]) -> dict[str, str]:
    """Extract human-readable metadata from an SFMC asset item."""
    modified_by = item.get("modifiedBy", {})
    return {
        "name": item.get("name", "unnamed"),
        "modifiedByName": modified_by.get("name", "unknown"),
        "modifiedDate": item.get("modifiedDate", ""),
    }


def write_emails(emails: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list]]:
    """Write each email to disk. Returns (manifest, changes).

    changes = {"added": [...], "modified": [...], "deleted": [...], "unchanged": int}
    Each entry in added/modified is {"file": str, "name": str, "modifiedBy": str, "modifiedDate": str}.
    Each entry in deleted is {"file": str}.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    existing_files: dict[str, str] = {}
    for f in OUTPUT_DIR.iterdir():
        if f.is_file() and f.name not in IGNORED_FILES:
            existing_files[f.name] = f.read_text(encoding="utf-8", errors="replace")

    written_files: set[str] = set()
    manifest: list[dict[str, Any]] = []
    added: list[dict[str, str]] = []
    modified: list[dict[str, str]] = []
    unchanged_count = 0

    for item in emails:
        views = item.get("views", {})
        html_content = views.get("html", {}).get("content", "")
        email_id = item.get("id", 0)
        name = item.get("name", "unnamed")
        safe_name = sanitize_filename(name)
        meta = _email_metadata(item)

        if html_content:
            filename = f"{email_id}_{safe_name}.html"
            content = html_content
        else:
            filename = f"{email_id}_{safe_name}.txt"
            subject = views.get("subjectline", {}).get("content", "")
            content = f"(Text Only Email - no HTML content)\nName: {name}\nSubject: {subject}\n"

        filepath = OUTPUT_DIR / filename
        change_entry = {
            "file": filename,
            "name": name,
            "modifiedBy": meta["modifiedByName"],
            "modifiedDate": meta["modifiedDate"],
        }

        if filename not in existing_files:
            added.append(change_entry)
        elif existing_files[filename] != content:
            modified.append(change_entry)
        else:
            unchanged_count += 1

        filepath.write_text(content, encoding="utf-8")
        written_files.add(filename)

        manifest.append({
            "file": filename,
            "id": email_id,
            "name": name,
            "customerKey": item.get("customerKey", ""),
            "assetType": item.get("assetType", {}).get("displayName", ""),
            "status": item.get("status", {}).get("name", ""),
            "category": item.get("category", {}).get("name", ""),
            "subject": views.get("subjectline", {}).get("content", ""),
            "preheader": views.get("preheader", {}).get("content", ""),
            "createdDate": item.get("createdDate", ""),
            "modifiedDate": item.get("modifiedDate", ""),
            "modifiedBy": meta["modifiedByName"],
        })

    deleted: list[dict[str, str]] = []
    stale = set(existing_files.keys()) - written_files
    for stale_file in sorted(stale):
        (OUTPUT_DIR / stale_file).unlink()
        deleted.append({"file": stale_file})
        print(f"  Removed stale file: {stale_file}")

    manifest.sort(key=lambda m: m["id"])
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    changes = {
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "unchanged": unchanged_count,
    }
    return manifest, changes


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

def _format_change_line(entry: dict[str, str]) -> str:
    date_part = entry.get("modifiedDate", "")
    if date_part:
        date_part = date_part.split("T")[0]
    by = entry.get("modifiedBy", "unknown")
    return f"- `{entry['file']}` -- \"{entry['name']}\" (modified in SFMC by {by} on {date_part})"


def append_changelog(changes: dict[str, Any], timestamp: str) -> bool:
    """Append a changelog entry. Returns True if anything changed."""
    added = changes["added"]
    modified = changes["modified"]
    deleted = changes["deleted"]
    unchanged = changes["unchanged"]

    if not added and not modified and not deleted:
        return False

    lines: list[str] = [f"## {timestamp}\n"]

    if added:
        lines.append(f"### Added ({len(added)})")
        for entry in added:
            lines.append(_format_change_line(entry))
        lines.append("")

    if modified:
        lines.append(f"### Modified ({len(modified)})")
        for entry in modified:
            lines.append(_format_change_line(entry))
        lines.append("")

    if deleted:
        lines.append(f"### Deleted ({len(deleted)})")
        for entry in deleted:
            lines.append(f"- `{entry['file']}`")
        lines.append("")

    lines.append(f"### Unchanged: {unchanged} email(s)\n")
    lines.append("---\n")

    new_entry = "\n".join(lines)

    existing = ""
    if CHANGELOG_FILE.exists():
        existing = CHANGELOG_FILE.read_text(encoding="utf-8")

    header = "# SFMC Email Content Changelog\n\n"
    if existing.startswith("# SFMC Email Content Changelog"):
        body = existing[existing.index("\n") + 1:].lstrip("\n")
        CHANGELOG_FILE.write_text(header + new_entry + "\n" + body, encoding="utf-8")
    else:
        CHANGELOG_FILE.write_text(header + new_entry + "\n" + existing, encoding="utf-8")

    return True


# ---------------------------------------------------------------------------
# Commit summary
# ---------------------------------------------------------------------------

def write_commit_summary(changes: dict[str, Any], timestamp: str) -> None:
    """Write a file the workflow can use as the git commit message."""
    added = changes["added"]
    modified = changes["modified"]
    deleted = changes["deleted"]
    unchanged = changes["unchanged"]

    subject = f"chore: sync SFMC email content {timestamp}"
    stats = f"Added: {len(added)} | Modified: {len(modified)} | Deleted: {len(deleted)} | Unchanged: {unchanged}"

    lines = [subject, "", stats, ""]

    if added:
        lines.append("Added:")
        for e in added:
            lines.append(f"  - {e['file']} ({e['name']})")
    if modified:
        lines.append("Modified:")
        for e in modified:
            lines.append(f"  - {e['file']} ({e['name']})")
    if deleted:
        lines.append("Deleted:")
        for e in deleted:
            lines.append(f"  - {e['file']}")

    lines.append("")
    COMMIT_SUMMARY_FILE.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    client_id = os.environ.get("SFMC_CLIENT_ID", "")
    client_secret = os.environ.get("SFMC_CLIENT_SECRET", "")
    subdomain = os.environ.get("SFMC_SUBDOMAIN", "")

    if not all([client_id, client_secret, subdomain]):
        print("ERROR: Set SFMC_CLIENT_ID, SFMC_CLIENT_SECRET, and SFMC_SUBDOMAIN environment variables.")
        return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("Authenticating with SFMC...")
    try:
        token, rest_url = authenticate(client_id, client_secret, subdomain)
    except httpx.HTTPStatusError as exc:
        print(f"ERROR: Authentication failed: {exc}")
        return 1
    print(f"Authenticated. REST endpoint: {rest_url}")

    print("Fetching Content Builder emails...")
    try:
        emails = fetch_all_emails(token, rest_url)
    except httpx.HTTPStatusError as exc:
        print(f"ERROR: Failed to fetch emails: {exc}")
        return 1
    print(f"Retrieved {len(emails)} email(s).")

    print(f"Writing files to {OUTPUT_DIR}/...")
    manifest, changes = write_emails(emails)

    added = len(changes["added"])
    modified = len(changes["modified"])
    deleted = len(changes["deleted"])
    unchanged = changes["unchanged"]
    print(f"Changes: {added} added, {modified} modified, {deleted} deleted, {unchanged} unchanged")

    if added or modified or deleted:
        append_changelog(changes, timestamp)
        print("Updated CHANGELOG.md")

    write_commit_summary(changes, timestamp)
    print(f"Done. {len(manifest)} email(s) synced.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
