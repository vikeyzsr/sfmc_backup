from typing import Any

from ..client import SFMCClient


async def list_automations(
    client: SFMCClient,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """List all automations in the account."""
    params: dict[str, Any] = {"$page": page, "$pageSize": page_size}
    data = await client.get("/automation/v1/automations", params=params)
    return {
        "page": data.get("page", page),
        "pageSize": data.get("pageSize", page_size),
        "count": data.get("count", 0),
        "items": data.get("items", []),
    }


async def get_automation(client: SFMCClient, automation_id: str) -> dict[str, Any]:
    """Get full details of a specific automation by its ID."""
    data = await client.get(f"/automation/v1/automations/{automation_id}")
    return data
