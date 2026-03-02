from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from moltbook_api.service import MoltbookService
from rare_identity_protocol.errors import ProtocolError, ResourceLimitError, SignatureError


class AuthChallengeRequest(BaseModel):
    aud: str | None = None


class AuthCompleteRequest(BaseModel):
    nonce: str
    agent_id: str
    session_pubkey: str
    delegation_token: str
    signature_by_session: str
    public_identity_attestation: str | None = None
    full_identity_attestation: str | None = None


class PostRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_session: str


class CommentRequest(BaseModel):
    post_id: str
    content: str = Field(min_length=1, max_length=2000)
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_session: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing Authorization header")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid Authorization header")
    token = authorization[len(prefix) :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty bearer token")
    return token


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, SignatureError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        status = 429 if "rate limit" in str(exc).lower() else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    if isinstance(exc, ResourceLimitError):
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    if isinstance(exc, ProtocolError):
        status = 409 if "nonce" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="internal server error") from exc


def create_app(service: MoltbookService) -> FastAPI:
    app = FastAPI(title="Moltbook-like API", version="0.2.0")

    @app.post("/auth/challenge")
    def auth_challenge(request: AuthChallengeRequest) -> dict:
        if request.aud and request.aud != service.aud:
            raise HTTPException(status_code=400, detail="aud mismatch")
        return service.issue_challenge()

    @app.post("/auth/complete")
    def auth_complete(request: AuthCompleteRequest) -> dict:
        try:
            return service.complete_auth(
                nonce=request.nonce,
                agent_id=request.agent_id,
                session_pubkey=request.session_pubkey,
                delegation_token=request.delegation_token,
                signature_by_session=request.signature_by_session,
                public_identity_attestation=request.public_identity_attestation,
                full_identity_attestation=request.full_identity_attestation,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/posts")
    def create_post(request: PostRequest, authorization: str | None = Header(default=None)) -> dict:
        token = _extract_bearer_token(authorization)
        try:
            return service.create_post(
                session_token=token,
                content=request.content,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_session=request.signature_by_session,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/comments")
    def create_comment(
        request: CommentRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        token = _extract_bearer_token(authorization)
        try:
            return service.create_comment(
                session_token=token,
                post_id=request.post_id,
                content=request.content,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_session=request.signature_by_session,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    return app
