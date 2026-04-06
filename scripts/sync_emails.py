#!/usr/bin/env python3
"""Fetch all SFMC Content Builder email assets and write them as individual HTML files.

Credentials are read from environment variables:
    SFMC_CLIENT_ID
    SFMC_CLIENT_SECRET
    SFMC_SUBDOMAIN

Output:
    email-content/{id}_{name}.html   -- one file per email
    email-content/manifest.json      -- metadata index of every email
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "email-content"

EMAIL_TYPE_IDS = [207, 208, 209]  # templatebasedemail, htmlemail, textonlyemail
PAGE_SIZE = 50


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
# File writing
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\s\-]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name or "unnamed"


def write_emails(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Write each email to disk and return the manifest entries."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    existing_files = {f.name for f in OUTPUT_DIR.iterdir() if f.is_file() and f.name != "manifest.json"}
    written_files: set[str] = set()
    manifest: list[dict[str, Any]] = []

    for item in emails:
        views = item.get("views", {})
        html_content = views.get("html", {}).get("content", "")
        email_id = item.get("id", 0)
        name = item.get("name", "unnamed")
        safe_name = sanitize_filename(name)

        if html_content:
            filename = f"{email_id}_{safe_name}.html"
            content = html_content
        else:
            filename = f"{email_id}_{safe_name}.txt"
            subject = views.get("subjectline", {}).get("content", "")
            content = f"(Text Only Email - no HTML content)\nName: {name}\nSubject: {subject}\n"

        filepath = OUTPUT_DIR / filename
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
        })

    # Remove files that no longer exist in SFMC (deleted emails)
    stale = existing_files - written_files
    for stale_file in stale:
        (OUTPUT_DIR / stale_file).unlink()
        print(f"  Removed stale file: {stale_file}")

    manifest.sort(key=lambda m: m["id"])
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    return manifest


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
    manifest = write_emails(emails)
    print(f"Done. {len(manifest)} email(s) written + manifest.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
