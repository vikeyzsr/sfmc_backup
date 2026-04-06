from typing import Any

from ..client import SFMCClient


async def list_journeys(
    client: SFMCClient,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
) -> dict[str, Any]:
    """List journeys (interactions) with optional status filter.

    status can be: Draft, Running, Stopped, etc.
    """
    params: dict[str, Any] = {"$page": page, "$pageSize": page_size}
    if status:
        params["status"] = status

    data = await client.get("/interaction/v1/interactions", params=params)
    return {
        "page": data.get("page", page),
        "pageSize": data.get("pageSize", page_size),
        "count": data.get("count", 0),
        "items": data.get("items", []),
    }


async def get_journey(client: SFMCClient, journey_id: str) -> dict[str, Any]:
    """Get full details of a specific journey by its ID."""
    data = await client.get(f"/interaction/v1/interactions/{journey_id}")
    return data
