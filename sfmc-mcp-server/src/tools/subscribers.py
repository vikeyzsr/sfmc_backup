from typing import Any

from ..client import SFMCClient


async def search_contacts(
    client: SFMCClient,
    contact_key: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Search for contacts by contact key or email address.

    At least one of contact_key or email must be provided.
    """
    if not contact_key and not email:
        return {"error": "Provide at least one of contact_key or email"}

    payload: dict[str, Any] = {}
    if contact_key:
        payload["contactKey"] = [contact_key]
    if email:
        payload["email"] = [email]

    data = await client.post("/contacts/v1/contacts/search", json_body=payload)
    return data


async def get_contact(client: SFMCClient, contact_id: str) -> dict[str, Any]:
    """Retrieve full details for a specific contact by ID."""
    data = await client.get(f"/contacts/v1/contacts/{contact_id}")
    return data
