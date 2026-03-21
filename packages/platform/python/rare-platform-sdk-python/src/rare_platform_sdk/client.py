from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class RareApiClientError(RuntimeError):
    """Raised for Rare API failures."""


@dataclass(frozen=True)
class ApiError(RareApiClientError):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return f"rare api error {self.status_code}: {self.detail}"


class RareApiClient:
    def __init__(
        self,
        *,
        rare_base_url: str,
        http_client: httpx.AsyncClient | None = None,
        default_headers: dict[str, str] | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.rare_base_url = rare_base_url.rstrip("/")
        self.default_headers = default_headers or {}
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http.aclose()

    async def get_jwks(self) -> dict[str, Any]:
        return await self._request_json("GET", "/.well-known/rare-keys.json")

    async def issue_platform_register_challenge(
        self, *, platform_aud: str, domain: str
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/v1/platforms/register/challenge",
            {"platform_aud": platform_aud, "domain": domain},
        )

    async def complete_platform_register(
        self,
        *,
        challenge_id: str,
        platform_id: str,
        platform_aud: str,
        domain: str,
        keys: list[dict[str, str]],
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/v1/platforms/register/complete",
            {
                "challenge_id": challenge_id,
                "platform_id": platform_id,
                "platform_aud": platform_aud,
                "domain": domain,
                "keys": keys,
            },
        )

    async def ingest_platform_events(self, event_token: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/v1/identity-library/events/ingest",
            {"event_token": event_token},
        )

    async def _request_json(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._http.request(
            method,
            f"{self.rare_base_url}{path}",
            headers={
                "Content-Type": "application/json",
                **self.default_headers,
            },
            json=body,
        )

        payload: dict[str, Any] | str
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            payload = response.text

        if response.status_code >= 400:
            if isinstance(payload, dict):
                detail = str(payload.get("detail") or payload)
            else:
                detail = payload
            raise ApiError(status_code=response.status_code, detail=detail)

        if not isinstance(payload, dict):
            raise RareApiClientError("expected JSON object response")
        return payload
