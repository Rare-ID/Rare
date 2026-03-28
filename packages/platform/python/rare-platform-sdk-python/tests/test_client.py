from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from rare_platform_sdk import RareApiClient
from rare_platform_sdk.client import extract_rare_signer_public_key_b64_from_jwks


def run(coro):
    return asyncio.run(coro)


def test_client_sends_expected_platform_register_challenge_request() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "challenge_id": "c1",
                "txt_name": "_rare.example.com",
                "txt_value": "proof",
                "expires_at": 123,
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = RareApiClient(
        rare_base_url="https://rare.example",
        http_client=http_client,
    )
    try:
        response = run(
            client.issue_platform_register_challenge(
                platform_aud="platform", domain="example.com"
            )
        )
    finally:
        run(http_client.aclose())
        run(client.aclose())

    assert captured["url"] == "https://rare.example/v1/platforms/register/challenge"
    assert captured["method"] == "POST"
    assert json.loads(captured["body"]) == {
        "platform_aud": "platform",
        "domain": "example.com",
    }
    assert response["challenge_id"] == "c1"


def test_client_raises_rich_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(400, json={"detail": "bad request"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = RareApiClient(
        rare_base_url="https://rare.example",
        http_client=http_client,
    )
    try:
        with pytest.raises(Exception, match="rare api error 400: bad request"):
            run(client.get_jwks())
    finally:
        run(http_client.aclose())
        run(client.aclose())


def test_extracts_hosted_signer_key_from_jwks() -> None:
    assert extract_rare_signer_public_key_b64_from_jwks(
        {
            "keys": [
                {
                    "kid": "rare-identity-k1",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "identity-key",
                    "rare_role": "identity",
                },
                {
                    "kid": "rare-signer-k1",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "delegation-key",
                    "rare_role": "delegation",
                },
            ]
        }
    ) == "delegation-key"
