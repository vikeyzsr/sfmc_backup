from typing import Any

from ..client import SFMCClient


async def list_email_definitions(
    client: SFMCClient,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
) -> dict[str, Any]:
    """List triggered send (email) definitions.

    status can be: Active, Inactive, Deleted, etc.
    """
    params: dict[str, Any] = {"$page": page, "$pageSize": page_size}
    if status:
        params["status"] = status

    data = await client.get("/messaging/v1/email/definitions", params=params)
    return {
        "page": data.get("page", page),
        "pageSize": data.get("pageSize", page_size),
        "count": data.get("count", 0),
        "definitions": data.get("definitions", data.get("items", [])),
    }


async def get_email_send_status(client: SFMCClient, message_key: str) -> dict[str, Any]:
    """Check the send status of a specific email message by its message key."""
    data = await client.get(f"/messaging/v1/email/messages/{message_key}")
    return data


async def list_content_builder_emails(
    client: SFMCClient,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """List all email assets from Content Builder / Email Studio.

    Returns name, subject line, status, category, and content for each email.
    """
    email_type_ids = [207, 208, 209]
    query_body: dict[str, Any] = {
        "page": {"page": page, "pageSize": page_size},
        "query": {
            "property": "assetType.id",
            "simpleOperator": "in",
            "value": email_type_ids,
        },
    }
    data = await client.post("/asset/v1/content/assets/query", json_body=query_body)
    items = data.get("items", [])

    emails = []
    for item in items:
        views = item.get("views", {})
        emails.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "customerKey": item.get("customerKey"),
            "assetType": item.get("assetType", {}).get("displayName"),
            "status": item.get("status", {}).get("name"),
            "category": item.get("category", {}).get("name"),
            "subject": views.get("subjectline", {}).get("content", ""),
            "preheader": views.get("preheader", {}).get("content", ""),
            "htmlContent": views.get("html", {}).get("content", ""),
            "createdDate": item.get("createdDate"),
            "modifiedDate": item.get("modifiedDate"),
        })

    return {
        "page": page,
        "pageSize": page_size,
        "count": data.get("count", 0),
        "emails": emails,
    }
