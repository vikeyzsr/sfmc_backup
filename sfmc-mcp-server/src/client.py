from typing import Any
import httpx

from .auth import SFMCAuth


class SFMCClient:
    """HTTP client for Salesforce Marketing Cloud Engagement REST API."""

    def __init__(self, auth: SFMCAuth):
        self._auth = auth

    async def _headers(self) -> dict[str, str]:
        token = await self._auth.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._auth.rest_base_url}/{path.lstrip('/')}"
        headers = await self._headers()
        async with httpx.AsyncClient() as http:
            resp = await http.get(url, headers=headers, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()

    async def post(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        url = f"{self._auth.rest_base_url}/{path.lstrip('/')}"
        headers = await self._headers()
        async with httpx.AsyncClient() as http:
            resp = await http.post(url, headers=headers, json=json_body, timeout=60)
            resp.raise_for_status()
            return resp.json()

    async def get_paginated(
        self,
        path: str,
        items_key: str = "items",
        params: dict[str, Any] | None = None,
        max_pages: int = 10,
    ) -> list[Any]:
        """Fetches multiple pages and returns the combined items list."""
        all_items: list[Any] = []
        page = 1
        request_params = dict(params or {})

        for _ in range(max_pages):
            request_params["$page"] = page
            data = await self.get(path, params=request_params)

            items = data.get(items_key, [])
            if isinstance(data, list):
                all_items.extend(data)
                break

            all_items.extend(items)

            count = data.get("count", 0)
            page_size = data.get("pageSize", data.get("page_size", 50))
            if not items or page * page_size >= count:
                break
            page += 1

        return all_items
