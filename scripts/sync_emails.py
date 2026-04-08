#!/usr/bin/env python3
"""Fetch all SFMC Content Builder assets (emails + content blocks) and write
them as individual files for version tracking.

Credentials are read from environment variables:
    SFMC_CLIENT_ID
    SFMC_CLIENT_SECRET
    SFMC_SUBDOMAIN

Output:
    email-content/emails/{id}_{name}.html       -- one file per email
    email-content/emails/manifest.json          -- metadata index of emails
    email-content/content-blocks/{id}_{name}.*  -- one file per content block
    email-content/content-blocks/manifest.json  -- metadata index of blocks
    email-content/CHANGELOG.md                  -- running history of changes
    email-content/.commit-summary               -- consumed by the workflow
"""

from __future__ import annotations

import difflib
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
EMAILS_DIR = OUTPUT_DIR / "emails"
CONTENT_BLOCKS_DIR = OUTPUT_DIR / "content-blocks"

EMAIL_TYPE_IDS = [207, 208, 209]  # templatebasedemail, htmlemail, textonlyemail
CONTENT_BLOCK_TYPE_IDS = [
    195,  # webpage
    196,  # textblock
    197,  # htmlblock
    199,  # buttonblock
    220,  # codesnippetblock
    227,  # dynamiccontentblock
]
PAGE_SIZE = 2500

CHANGELOG_FILE = OUTPUT_DIR / "CHANGELOG.md"
COMMIT_SUMMARY_FILE = OUTPUT_DIR / ".commit-summary"
META_FILES = {"manifest.json"}


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

def fetch_assets(token: str, rest_url: str, type_ids: list[int], label: str) -> list[dict[str, Any]]:
    """Paginate through the Content Builder Asset query and return all items
    matching the given asset type IDs."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    all_items: list[dict[str, Any]] = []
    page = 1

    while True:
        body: dict[str, Any] = {
            "page": {"page": page, "pageSize": PAGE_SIZE},
            "query": {
                "property": "assetType.id",
                "simpleOperator": "in",
                "value": type_ids,
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
        print(f"  [{label}] Page {page}: {len(items)} items (total {len(all_items)}/{count})")

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


def _asset_metadata(item: dict[str, Any]) -> dict[str, str]:
    """Extract human-readable metadata from an SFMC asset item."""
    modified_by = item.get("modifiedBy", {})
    return {
        "name": item.get("name", "unnamed"),
        "modifiedByName": modified_by.get("name", "unknown"),
        "modifiedDate": item.get("modifiedDate", ""),
    }


def _load_previous_manifest(directory: Path) -> dict[str, dict[str, Any]]:
    """Load the previous manifest.json from a directory, keyed by filename."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {e["file"]: e for e in entries}
    except (json.JSONDecodeError, KeyError):
        return {}


def _extract_content(item: dict[str, Any]) -> tuple[str, str]:
    """Determine filename extension and text content for any asset type.

    Returns (extension, content_string).
    """
    views = item.get("views", {})
    html_content = views.get("html", {}).get("content", "")

    if html_content:
        return ".html", html_content

    text_content = views.get("text", {}).get("content", "")
    if text_content:
        return ".txt", text_content

    raw_content = item.get("content", "")
    if raw_content:
        return ".html", raw_content

    name = item.get("name", "unnamed")
    asset_type = item.get("assetType", {}).get("displayName", "unknown")
    subject = views.get("subjectline", {}).get("content", "")
    fallback = f"(No extractable content)\nName: {name}\nType: {asset_type}\n"
    if subject:
        fallback += f"Subject: {subject}\n"
    return ".txt", fallback


def write_assets(
    assets: list[dict[str, Any]],
    directory: Path,
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, list]]:
    """Write each asset to disk. Returns (manifest, changes).

    changes = {"added": [...], "modified": [...], "deleted": [...], "unchanged": int}
    """
    directory.mkdir(parents=True, exist_ok=True)

    existing_files: dict[str, str] = {}
    for f in directory.iterdir():
        if f.is_file() and f.name not in META_FILES:
            existing_files[f.name] = f.read_text(encoding="utf-8", errors="replace")

    prev_manifest = _load_previous_manifest(directory)

    written_files: set[str] = set()
    manifest: list[dict[str, Any]] = []
    added: list[dict[str, str]] = []
    modified: list[dict[str, str]] = []
    unchanged_count = 0

    for item in assets:
        asset_id = item.get("id", 0)
        name = item.get("name", "unnamed")
        safe_name = sanitize_filename(name)
        meta = _asset_metadata(item)

        ext, content = _extract_content(item)
        filename = f"{asset_id}_{safe_name}{ext}"

        filepath = directory / filename
        rel_path = f"{label}/{filename}"
        change_entry = {
            "file": rel_path,
            "name": name,
            "modifiedBy": meta["modifiedByName"],
            "modifiedDate": meta["modifiedDate"],
        }

        if filename not in existing_files:
            added.append(change_entry)
        else:
            old_content = existing_files[filename]
            content_changed = old_content != content
            prev_entry = prev_manifest.get(filename, {})
            metadata_changed = prev_entry.get("modifiedDate", "") != meta["modifiedDate"]
            if content_changed or metadata_changed:
                diff_lines = list(difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                ))
                change_entry["diff"] = "".join(diff_lines) if diff_lines else "(metadata changed, content identical)"
                modified.append(change_entry)
            else:
                unchanged_count += 1

        filepath.write_text(content, encoding="utf-8")
        written_files.add(filename)

        views = item.get("views", {})
        manifest.append({
            "file": filename,
            "id": asset_id,
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
        old_content = existing_files.get(stale_file, "")
        (directory / stale_file).unlink()
        deleted.append({
            "file": f"{label}/{stale_file}",
            "old_content": old_content,
        })
        print(f"  Removed stale file: {label}/{stale_file}")

    manifest.sort(key=lambda m: m["id"])
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    changes = {
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "unchanged": unchanged_count,
    }
    return manifest, changes


# ---------------------------------------------------------------------------
# Merge change dicts from multiple asset categories
# ---------------------------------------------------------------------------

def _merge_changes(*change_dicts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {"added": [], "modified": [], "deleted": [], "unchanged": 0}
    for ch in change_dicts:
        merged["added"].extend(ch["added"])
        merged["modified"].extend(ch["modified"])
        merged["deleted"].extend(ch["deleted"])
        merged["unchanged"] += ch["unchanged"]
    return merged


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
            diff_text = entry.get("diff", "")
            if diff_text:
                lines.append("")
                lines.append("<details>")
                lines.append(f"<summary>Diff for {entry['file']}</summary>")
                lines.append("")
                lines.append("```diff")
                lines.append(diff_text.rstrip())
                lines.append("```")
                lines.append("")
                lines.append("</details>")
            lines.append("")

    if deleted:
        lines.append(f"### Deleted ({len(deleted)})")
        for entry in deleted:
            lines.append(f"- `{entry['file']}`")
            old_content = entry.get("old_content", "")
            if old_content:
                lines.append("")
                lines.append("<details>")
                lines.append(f"<summary>Last known content of {entry['file']}</summary>")
                lines.append("")
                lines.append("```html")
                lines.append(old_content.rstrip())
                lines.append("```")
                lines.append("")
                lines.append("</details>")
            lines.append("")

    lines.append(f"### Unchanged: {unchanged} asset(s)\n")
    lines.append("---\n")

    new_entry = "\n".join(lines)

    existing = ""
    if CHANGELOG_FILE.exists():
        existing = CHANGELOG_FILE.read_text(encoding="utf-8")

    header = "# SFMC Content Builder Changelog\n\n"
    if existing.startswith("# SFMC"):
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

    subject = f"chore: sync SFMC content {timestamp}"
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

    # --- Fetch emails ---
    print("Fetching emails...")
    try:
        emails = fetch_assets(token, rest_url, EMAIL_TYPE_IDS, "emails")
    except httpx.HTTPStatusError as exc:
        print(f"ERROR: Failed to fetch emails: {exc}")
        return 1
    print(f"Retrieved {len(emails)} email(s).")

    # --- Fetch content blocks ---
    print("Fetching content blocks...")
    try:
        blocks = fetch_assets(token, rest_url, CONTENT_BLOCK_TYPE_IDS, "content-blocks")
    except httpx.HTTPStatusError as exc:
        print(f"ERROR: Failed to fetch content blocks: {exc}")
        return 1
    print(f"Retrieved {len(blocks)} content block(s).")

    # --- Write emails ---
    print(f"Writing emails to {EMAILS_DIR}/...")
    email_manifest, email_changes = write_assets(emails, EMAILS_DIR, "emails")
    _print_changes("Emails", email_changes)

    # --- Write content blocks ---
    print(f"Writing content blocks to {CONTENT_BLOCKS_DIR}/...")
    block_manifest, block_changes = write_assets(blocks, CONTENT_BLOCKS_DIR, "content-blocks")
    _print_changes("Content blocks", block_changes)

    # --- Changelog & commit summary ---
    all_changes = _merge_changes(email_changes, block_changes)

    has_changes = (
        all_changes["added"] or all_changes["modified"] or all_changes["deleted"]
    )
    if has_changes:
        append_changelog(all_changes, timestamp)
        print("Updated CHANGELOG.md")

    write_commit_summary(all_changes, timestamp)
    total = len(email_manifest) + len(block_manifest)
    print(f"Done. {total} asset(s) synced ({len(email_manifest)} emails, {len(block_manifest)} content blocks).")

    return 0


def _print_changes(label: str, changes: dict[str, Any]) -> None:
    a = len(changes["added"])
    m = len(changes["modified"])
    d = len(changes["deleted"])
    u = changes["unchanged"]
    print(f"  {label}: {a} added, {m} modified, {d} deleted, {u} unchanged")


if __name__ == "__main__":
    sys.exit(main())
