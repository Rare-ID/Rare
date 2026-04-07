from __future__ import annotations

from dataclasses import asdict
from typing import Any
from typing import Mapping

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from rare_identity_protocol import SignatureError, TokenValidationError

from rare_platform_sdk.kit import create_rare_platform_kit_from_env
from rare_platform_sdk.types import AuthCompleteInput, RarePlatformKit
from rare_platform_sdk.types import PlatformSession, SessionStore


class AuthChallengeRequest(BaseModel):
    aud: str | None = None


class AuthChallengeResponse(BaseModel):
    nonce: str
    aud: str
    issued_at: int
    expires_at: int


class AuthCompleteRequest(BaseModel):
    nonce: str
    agent_id: str
    session_pubkey: str
    delegation_token: str
    signature_by_session: str
    public_identity_attestation: str | None = None
    full_identity_attestation: str | None = None


class AuthCompleteResponse(BaseModel):
    session_token: str
    agent_id: str
    level: str
    raw_level: str
    identity_mode: str
    display_name: str
    session_pubkey: str


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, (TokenValidationError, SignatureError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="internal server error") from exc


def create_fastapi_rare_router(
    kit: RarePlatformKit, prefix: str = ""
) -> APIRouter:
    router = APIRouter(prefix=prefix)

    @router.post("/auth/challenge", response_model=AuthChallengeResponse)
    async def auth_challenge(request: AuthChallengeRequest) -> AuthChallengeResponse:
        try:
            challenge = await kit.issue_challenge(request.aud)
            return AuthChallengeResponse(**asdict(challenge))
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @router.post("/auth/complete", response_model=AuthCompleteResponse)
    async def auth_complete(request: AuthCompleteRequest) -> AuthCompleteResponse:
        try:
            result = await kit.complete_auth(
                AuthCompleteInput(
                    nonce=request.nonce,
                    agent_id=request.agent_id,
                    session_pubkey=request.session_pubkey,
                    delegation_token=request.delegation_token,
                    signature_by_session=request.signature_by_session,
                    public_identity_attestation=request.public_identity_attestation,
                    full_identity_attestation=request.full_identity_attestation,
                )
            )
            return AuthCompleteResponse(**asdict(result))
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    return router


def extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    resolved = token.strip()
    return resolved or None


async def resolve_platform_session(
    session_store: SessionStore,
    *,
    authorization: str | None = None,
    session_token: str | None = None,
    cookie_value: str | None = None,
) -> PlatformSession | None:
    resolved_token = session_token or extract_bearer_token(authorization) or cookie_value
    if not resolved_token:
        return None
    return await session_store.get(resolved_token)


def create_fastapi_session_dependency(
    session_store: SessionStore,
    *,
    cookie_name: str = "rare_session",
    auto_error: bool = True,
):
    async def dependency(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> PlatformSession | None:
        session = await resolve_platform_session(
            session_store,
            authorization=authorization,
            cookie_value=request.cookies.get(cookie_name),
        )
        if session is None and auto_error:
            raise HTTPException(status_code=401, detail="invalid session token")
        return session

    return dependency


def create_fastapi_rare_router_from_env(
    *,
    challenge_store: Any,
    replay_store: Any,
    session_store: Any,
    prefix: str = "",
    env: Mapping[str, str] | None = None,
    rare_api_client: Any | None = None,
    http_client: httpx.AsyncClient | None = None,
    default_headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
    key_resolver: Any | None = None,
    initial_jwks: dict[str, Any] | None = None,
    challenge_ttl_seconds: int = 120,
    session_ttl_seconds: int = 3600,
    max_signed_ttl_seconds: int = 300,
    clock_skew_seconds: int = 30,
) -> APIRouter:
    kit = create_rare_platform_kit_from_env(
        challenge_store=challenge_store,
        replay_store=replay_store,
        session_store=session_store,
        env=env,
        rare_api_client=rare_api_client,
        http_client=http_client,
        default_headers=default_headers,
        timeout_seconds=timeout_seconds,
        key_resolver=key_resolver,
        initial_jwks=initial_jwks,
        challenge_ttl_seconds=challenge_ttl_seconds,
        session_ttl_seconds=session_ttl_seconds,
        max_signed_ttl_seconds=max_signed_ttl_seconds,
        clock_skew_seconds=clock_skew_seconds,
    )
    return create_fastapi_rare_router(kit, prefix=prefix)
