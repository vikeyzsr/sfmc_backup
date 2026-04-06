import time
import httpx


class SFMCAuth:
    """Manages OAuth2 client_credentials authentication for MC Engagement."""

    TOKEN_REFRESH_BUFFER_SECONDS = 120

    def __init__(self, client_id: str, client_secret: str, subdomain: str, account_id: str | None = None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._subdomain = subdomain
        self._account_id = account_id
        self._access_token: str | None = None
        self._token_expiry: float = 0
        self._rest_base_url: str | None = None
        self._soap_base_url: str | None = None

    @property
    def auth_url(self) -> str:
        return f"https://{self._subdomain}.auth.marketingcloudapis.com/v2/token"

    @property
    def rest_base_url(self) -> str:
        if self._rest_base_url:
            return self._rest_base_url.rstrip("/")
        return f"https://{self._subdomain}.rest.marketingcloudapis.com"

    async def get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        await self._refresh_token()
        assert self._access_token is not None
        return self._access_token

    async def _refresh_token(self) -> None:
        payload: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._account_id:
            payload["account_id"] = self._account_id

        async with httpx.AsyncClient() as http:
            resp = await http.post(self.auth_url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 1080)
        self._token_expiry = time.time() + expires_in - self.TOKEN_REFRESH_BUFFER_SECONDS
        self._rest_base_url = data.get("rest_instance_url")
        self._soap_base_url = data.get("soap_instance_url")
