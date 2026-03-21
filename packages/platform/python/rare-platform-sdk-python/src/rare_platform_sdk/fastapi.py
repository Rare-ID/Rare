from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rare_identity_protocol import SignatureError, TokenValidationError

from rare_platform_sdk.types import AuthCompleteInput, RarePlatformKit


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
