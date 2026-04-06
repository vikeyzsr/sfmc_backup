from typing import Any

from ..client import SFMCClient


async def list_data_extensions(client: SFMCClient) -> list[dict[str, Any]]:
    """List all data extensions in the account.

    Uses the legacy REST endpoint which returns DE name, customer key, and ID.
    """
    data = await client.get("/legacy/v1/beta/object/")
    if isinstance(data, list):
        return data
    return data.get("items", data.get("Results", [data]))


async def describe_data_extension(client: SFMCClient, customer_key: str) -> dict[str, Any]:
    """Retrieve field metadata (schema) for a data extension by its customer key."""
    data = await client.get(f"/legacy/v1/beta/object/{customer_key}/field")
    return {"customerKey": customer_key, "fields": data if isinstance(data, list) else data.get("items", [data])}


async def query_data_extension_rows(
    client: SFMCClient,
    customer_key: str,
    filter_expression: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Read rows from a data extension with optional OData-style filter.

    filter_expression example: "EmailAddress eq 'test@example.com'"
    """
    params: dict[str, Any] = {"$page": page, "$pageSize": page_size}
    if filter_expression:
        params["$filter"] = filter_expression

    data = await client.get(
        f"/data/v1/customobjectdata/key/{customer_key}/rowset",
        params=params,
    )
    return {
        "customerKey": customer_key,
        "page": data.get("page", page),
        "pageSize": data.get("pageSize", page_size),
        "count": data.get("count", 0),
        "items": data.get("items", []),
    }
