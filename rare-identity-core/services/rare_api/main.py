from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from rare_api.service import RareService
from rare_identity_protocol.errors import ProtocolError, ResourceLimitError, SignatureError


class SelfRegisterRequest(BaseModel):
    name: str | None = Field(default=None)
    key_mode: Literal["hosted-signer", "self-hosted"] = Field(default="hosted-signer")
    agent_public_key: str | None = Field(default=None)
    nonce: str | None = Field(default=None)
    issued_at: int | None = Field(default=None)
    expires_at: int | None = Field(default=None)
    signature_by_agent: str | None = Field(default=None)


class SetNameRequest(BaseModel):
    agent_id: str
    name: str
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_agent: str


class SignSetNameRequest(BaseModel):
    agent_id: str
    name: str
    ttl_seconds: int = 120


class RefreshAttestationRequest(BaseModel):
    agent_id: str


class IssuePublicAttestationRequest(BaseModel):
    agent_id: str


class IssueFullAttestationRequest(BaseModel):
    agent_id: str
    platform_aud: str
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_agent: str


class SignPlatformGrantRequest(BaseModel):
    agent_id: str
    platform_aud: str
    ttl_seconds: int = 120


class SignFullAttestationIssueRequest(BaseModel):
    agent_id: str
    platform_aud: str
    ttl_seconds: int = 120


class SignUpgradeRequest(BaseModel):
    agent_id: str
    target_level: Literal["L1", "L2"]
    request_id: str
    ttl_seconds: int = 120


class HostedManagementTokenRequest(BaseModel):
    agent_id: str


class SignDelegationRequest(BaseModel):
    agent_id: str
    session_pubkey: str
    aud: str
    scope: list[str] = Field(default_factory=lambda: ["login"])
    ttl_seconds: int = 3600


class PrepareAuthRequest(BaseModel):
    agent_id: str
    aud: str
    nonce: str
    issued_at: int
    expires_at: int
    scope: list[str] = Field(default_factory=lambda: ["login"])
    delegation_ttl_seconds: int = 3600


class SignActionRequest(BaseModel):
    agent_id: str
    session_pubkey: str
    session_token: str
    aud: str
    action: str
    action_payload: dict[str, Any]
    nonce: str
    issued_at: int
    expires_at: int


class ProfilePatchRequest(BaseModel):
    patch: dict[str, Any]


class CreateSubscriptionRequest(BaseModel):
    name: str
    webhook_url: str
    fields: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)


class PlatformRegisterChallengeRequest(BaseModel):
    platform_aud: str
    domain: str


class PlatformRegisterKey(BaseModel):
    kid: str
    public_key: str


class PlatformRegisterCompleteRequest(BaseModel):
    challenge_id: str
    platform_id: str
    platform_aud: str
    domain: str
    keys: list[PlatformRegisterKey]


class PlatformGrantRequest(BaseModel):
    agent_id: str
    platform_aud: str
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_agent: str


class PlatformGrantRevokeRequest(BaseModel):
    agent_id: str
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_agent: str


class IngestPlatformEventRequest(BaseModel):
    event_token: str


class UpgradeRequestCreate(BaseModel):
    agent_id: str
    target_level: Literal["L1", "L2"]
    request_id: str
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_agent: str
    contact_email: str | None = None


class UpgradeL1SendLinkRequest(BaseModel):
    upgrade_request_id: str


class UpgradeL2SocialStartRequest(BaseModel):
    upgrade_request_id: str
    provider: Literal["x", "github"]


class UpgradeL2SocialCompleteRequest(BaseModel):
    upgrade_request_id: str
    provider: Literal["x", "github"]
    provider_user_snapshot: dict[str, Any]


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


def _try_extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    return _extract_bearer_token(authorization)


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _has_complete_agent_proof(
    *,
    proof_agent_id: str | None,
    proof_nonce: str | None,
    proof_issued_at: int | None,
    proof_expires_at: int | None,
    proof_signature_by_agent: str | None,
) -> bool:
    return (
        bool(proof_agent_id)
        and bool(proof_nonce)
        and proof_issued_at is not None
        and proof_expires_at is not None
        and bool(proof_signature_by_agent)
    )


def _resolve_management_token_or_require_proof(
    *,
    authorization: str | None,
    proof_agent_id: str | None,
    proof_nonce: str | None,
    proof_issued_at: int | None,
    proof_expires_at: int | None,
    proof_signature_by_agent: str | None,
) -> str | None:
    token = _try_extract_bearer_token(authorization)
    if token is not None:
        return token
    if not _has_complete_agent_proof(
        proof_agent_id=proof_agent_id,
        proof_nonce=proof_nonce,
        proof_issued_at=proof_issued_at,
        proof_expires_at=proof_expires_at,
        proof_signature_by_agent=proof_signature_by_agent,
    ):
        raise HTTPException(status_code=401, detail="missing authorization")
    return None


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ResourceLimitError):
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    if isinstance(exc, SignatureError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, ProtocolError):
        lower_detail = str(exc).lower()
        status = 409 if ("nonce" in lower_detail or "replay" in lower_detail) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="internal server error") from exc


def create_app(service: RareService | None = None, *, admin_token: str | None = None) -> FastAPI:
    if service is None:
        resolved_admin_token = admin_token if admin_token is not None else os.getenv("RARE_ADMIN_TOKEN")
        rare_service = RareService(
            admin_token=resolved_admin_token,
            allow_local_upgrade_shortcuts=_env_bool("RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS", default=False),
        )
    else:
        rare_service = service
        if admin_token is not None:
            rare_service.set_admin_token(admin_token)
    app = FastAPI(title="Rare API Gateway", version="0.2.0")

    def _authorize_hosted_signer_call(*, agent_id: str, authorization: str | None) -> None:
        token = _extract_bearer_token(authorization)
        rare_service.authorize_hosted_management(agent_id=agent_id, token=token)

    def _authorize_admin_call(authorization: str | None) -> None:
        token = _extract_bearer_token(authorization)
        rare_service.authorize_admin(token=token)

    def _authorize_agent_management_call(
        *,
        agent_id: str,
        operation: str,
        resource_id: str,
        authorization: str | None,
        proof_agent_id: str | None,
        proof_nonce: str | None,
        proof_issued_at: int | None,
        proof_expires_at: int | None,
        proof_signature_by_agent: str | None,
    ) -> None:
        token = _resolve_management_token_or_require_proof(
            authorization=authorization,
            proof_agent_id=proof_agent_id,
            proof_nonce=proof_nonce,
            proof_issued_at=proof_issued_at,
            proof_expires_at=proof_expires_at,
            proof_signature_by_agent=proof_signature_by_agent,
        )
        rare_service.authorize_admin_or_hosted_or_agent_proof(
            agent_id=agent_id,
            token=token,
            operation=operation,
            resource_id=resource_id,
            proof_agent_id=proof_agent_id,
            proof_nonce=proof_nonce,
            proof_issued_at=proof_issued_at,
            proof_expires_at=proof_expires_at,
            proof_signature_by_agent=proof_signature_by_agent,
        )

    @app.post("/v1/agents/self_register")
    def self_register(request: SelfRegisterRequest) -> dict:
        try:
            return rare_service.self_register(
                name=request.name,
                key_mode=request.key_mode,
                agent_public_key=request.agent_public_key,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_agent=request.signature_by_agent,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/agents/set_name")
    def set_name(request: SetNameRequest) -> dict:
        try:
            return rare_service.set_name(
                agent_id=request.agent_id,
                name=request.name,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_agent=request.signature_by_agent,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/attestations/refresh")
    def refresh_attestation(request: RefreshAttestationRequest) -> dict:
        try:
            return rare_service.refresh_attestation(agent_id=request.agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/attestations/public/issue")
    def issue_public_attestation(request: IssuePublicAttestationRequest) -> dict:
        try:
            return rare_service.issue_public_attestation(agent_id=request.agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/attestations/full/issue")
    def issue_full_attestation(request: IssueFullAttestationRequest) -> dict:
        try:
            return rare_service.issue_full_attestation(
                agent_id=request.agent_id,
                platform_aud=request.platform_aud,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_agent=request.signature_by_agent,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/sign_delegation")
    def sign_delegation(request: SignDelegationRequest, authorization: str | None = Header(default=None)) -> dict:
        try:
            _authorize_hosted_signer_call(agent_id=request.agent_id, authorization=authorization)
            return rare_service.sign_delegation(
                agent_id=request.agent_id,
                session_pubkey=request.session_pubkey,
                aud=request.aud,
                scope=request.scope,
                ttl_seconds=request.ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/sign_set_name")
    def sign_set_name(request: SignSetNameRequest, authorization: str | None = Header(default=None)) -> dict:
        try:
            _authorize_hosted_signer_call(agent_id=request.agent_id, authorization=authorization)
            return rare_service.sign_set_name(
                agent_id=request.agent_id,
                name=request.name,
                ttl_seconds=request.ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/sign_platform_grant")
    def sign_platform_grant(
        request: SignPlatformGrantRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        try:
            _authorize_hosted_signer_call(agent_id=request.agent_id, authorization=authorization)
            return rare_service.sign_platform_grant(
                agent_id=request.agent_id,
                platform_aud=request.platform_aud,
                ttl_seconds=request.ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/sign_full_attestation_issue")
    def sign_full_attestation_issue(
        request: SignFullAttestationIssueRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        try:
            _authorize_hosted_signer_call(agent_id=request.agent_id, authorization=authorization)
            return rare_service.sign_full_attestation_issue(
                agent_id=request.agent_id,
                platform_aud=request.platform_aud,
                ttl_seconds=request.ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/sign_upgrade_request")
    def sign_upgrade_request(request: SignUpgradeRequest, authorization: str | None = Header(default=None)) -> dict:
        try:
            _authorize_hosted_signer_call(agent_id=request.agent_id, authorization=authorization)
            return rare_service.sign_upgrade_request(
                agent_id=request.agent_id,
                target_level=request.target_level,
                request_id=request.request_id,
                ttl_seconds=request.ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/prepare_auth")
    def prepare_auth(request: PrepareAuthRequest, authorization: str | None = Header(default=None)) -> dict:
        try:
            _authorize_hosted_signer_call(agent_id=request.agent_id, authorization=authorization)
            return rare_service.prepare_auth(
                agent_id=request.agent_id,
                aud=request.aud,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                scope=request.scope,
                delegation_ttl_seconds=request.delegation_ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/sign_action")
    def sign_action(request: SignActionRequest, authorization: str | None = Header(default=None)) -> dict:
        try:
            _authorize_hosted_signer_call(agent_id=request.agent_id, authorization=authorization)
            return rare_service.sign_action(
                agent_id=request.agent_id,
                session_pubkey=request.session_pubkey,
                session_token=request.session_token,
                aud=request.aud,
                action=request.action,
                action_payload=request.action_payload,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/rotate_management_token")
    def rotate_management_token(
        request: HostedManagementTokenRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        try:
            token = _extract_bearer_token(authorization)
            return rare_service.rotate_hosted_management_token(agent_id=request.agent_id, token=token)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/revoke_management_token")
    def revoke_management_token(
        request: HostedManagementTokenRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        try:
            token = _extract_bearer_token(authorization)
            return rare_service.revoke_hosted_management_token(agent_id=request.agent_id, token=token)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/identity-library/profiles/{agent_id}")
    def get_identity_profile(agent_id: str) -> dict:
        try:
            return rare_service.get_identity_profile(agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.patch("/v1/identity-library/profiles/{agent_id}")
    def patch_identity_profile(
        agent_id: str,
        request: ProfilePatchRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        try:
            _authorize_admin_call(authorization)
            return rare_service.upsert_identity_profile(agent_id=agent_id, patch=request.patch)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/identity-library/subscriptions")
    def create_identity_subscription(
        request: CreateSubscriptionRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        try:
            _authorize_admin_call(authorization)
            return rare_service.create_identity_subscription(
                name=request.name,
                webhook_url=request.webhook_url,
                fields=request.fields,
                event_types=request.event_types,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/identity-library/subscriptions")
    def list_identity_subscriptions(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.list_identity_subscriptions()
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/platforms/register/challenge")
    def issue_platform_register_challenge(request: PlatformRegisterChallengeRequest) -> dict:
        try:
            return rare_service.issue_platform_register_challenge(
                platform_aud=request.platform_aud,
                domain=request.domain,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/platforms/register/complete")
    def complete_platform_register(request: PlatformRegisterCompleteRequest) -> dict:
        try:
            return rare_service.complete_platform_register(
                challenge_id=request.challenge_id,
                platform_id=request.platform_id,
                platform_aud=request.platform_aud,
                domain=request.domain,
                keys=[key.model_dump() if hasattr(key, "model_dump") else key.dict() for key in request.keys],
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/agents/platform-grants")
    def create_platform_grant(request: PlatformGrantRequest) -> dict:
        try:
            return rare_service.create_platform_grant(
                agent_id=request.agent_id,
                platform_aud=request.platform_aud,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_agent=request.signature_by_agent,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.delete("/v1/agents/platform-grants/{platform_aud}")
    def revoke_platform_grant(platform_aud: str, request: PlatformGrantRevokeRequest) -> dict:
        try:
            return rare_service.revoke_platform_grant(
                agent_id=request.agent_id,
                platform_aud=platform_aud,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_agent=request.signature_by_agent,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/agents/platform-grants/{agent_id}")
    def list_platform_grants(
        agent_id: str,
        authorization: str | None = Header(default=None),
        proof_agent_id: str | None = Header(default=None, alias="X-Rare-Agent-Id"),
        proof_nonce: str | None = Header(default=None, alias="X-Rare-Agent-Nonce"),
        proof_issued_at: int | None = Header(default=None, alias="X-Rare-Agent-Issued-At"),
        proof_expires_at: int | None = Header(default=None, alias="X-Rare-Agent-Expires-At"),
        proof_signature_by_agent: str | None = Header(default=None, alias="X-Rare-Agent-Signature"),
    ) -> dict:
        try:
            _authorize_agent_management_call(
                agent_id=agent_id,
                operation="list_platform_grants",
                resource_id=agent_id,
                authorization=authorization,
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            return rare_service.list_platform_grants(agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/identity-library/events/ingest")
    def ingest_platform_events(request: IngestPlatformEventRequest) -> dict:
        try:
            return rare_service.ingest_platform_events(event_token=request.event_token)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/upgrades/requests")
    def create_upgrade_request(request: UpgradeRequestCreate) -> dict:
        try:
            return rare_service.create_upgrade_request(
                agent_id=request.agent_id,
                target_level=request.target_level,
                request_id=request.request_id,
                nonce=request.nonce,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                signature_by_agent=request.signature_by_agent,
                contact_email=request.contact_email,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/upgrades/requests/{upgrade_request_id}")
    def get_upgrade_request(
        upgrade_request_id: str,
        authorization: str | None = Header(default=None),
        proof_agent_id: str | None = Header(default=None, alias="X-Rare-Agent-Id"),
        proof_nonce: str | None = Header(default=None, alias="X-Rare-Agent-Nonce"),
        proof_issued_at: int | None = Header(default=None, alias="X-Rare-Agent-Issued-At"),
        proof_expires_at: int | None = Header(default=None, alias="X-Rare-Agent-Expires-At"),
        proof_signature_by_agent: str | None = Header(default=None, alias="X-Rare-Agent-Signature"),
    ) -> dict:
        try:
            token = _resolve_management_token_or_require_proof(
                authorization=authorization,
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            return rare_service.get_upgrade_request_authorized(
                upgrade_request_id=upgrade_request_id,
                token=token,
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/upgrades/l1/email/send-link")
    def send_upgrade_l1_link(
        request: UpgradeL1SendLinkRequest,
        authorization: str | None = Header(default=None),
        proof_agent_id: str | None = Header(default=None, alias="X-Rare-Agent-Id"),
        proof_nonce: str | None = Header(default=None, alias="X-Rare-Agent-Nonce"),
        proof_issued_at: int | None = Header(default=None, alias="X-Rare-Agent-Issued-At"),
        proof_expires_at: int | None = Header(default=None, alias="X-Rare-Agent-Expires-At"),
        proof_signature_by_agent: str | None = Header(default=None, alias="X-Rare-Agent-Signature"),
    ) -> dict:
        try:
            token = _resolve_management_token_or_require_proof(
                authorization=authorization,
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            rare_service.authorize_upgrade_request_operation(
                upgrade_request_id=request.upgrade_request_id,
                token=token,
                operation="upgrade_send_link",
                resource_id=request.upgrade_request_id,
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            return rare_service.send_upgrade_l1_email_link(upgrade_request_id=request.upgrade_request_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/upgrades/l1/email/verify")
    def verify_upgrade_l1_email(token: str = Query(...)) -> dict:
        try:
            return rare_service.verify_upgrade_l1_email(token=token)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/upgrades/l2/social/start")
    def start_upgrade_l2_social(
        request: UpgradeL2SocialStartRequest,
        authorization: str | None = Header(default=None),
        proof_agent_id: str | None = Header(default=None, alias="X-Rare-Agent-Id"),
        proof_nonce: str | None = Header(default=None, alias="X-Rare-Agent-Nonce"),
        proof_issued_at: int | None = Header(default=None, alias="X-Rare-Agent-Issued-At"),
        proof_expires_at: int | None = Header(default=None, alias="X-Rare-Agent-Expires-At"),
        proof_signature_by_agent: str | None = Header(default=None, alias="X-Rare-Agent-Signature"),
    ) -> dict:
        try:
            token = _resolve_management_token_or_require_proof(
                authorization=authorization,
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            rare_service.authorize_upgrade_request_operation(
                upgrade_request_id=request.upgrade_request_id,
                token=token,
                operation="upgrade_start_social",
                resource_id=f"{request.upgrade_request_id}:{request.provider}",
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            return rare_service.start_upgrade_l2_social(
                upgrade_request_id=request.upgrade_request_id,
                provider=request.provider,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/upgrades/l2/social/callback")
    def social_callback_upgrade_l2(
        provider: Literal["x", "github"] = Query(...),
        code: str = Query(...),
        state: str = Query(...),
    ) -> dict:
        try:
            return rare_service.social_callback_upgrade_l2(
                provider=provider,
                code=code,
                state=state,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/upgrades/l2/social/complete")
    def complete_upgrade_l2_social(
        request: UpgradeL2SocialCompleteRequest,
        authorization: str | None = Header(default=None),
        proof_agent_id: str | None = Header(default=None, alias="X-Rare-Agent-Id"),
        proof_nonce: str | None = Header(default=None, alias="X-Rare-Agent-Nonce"),
        proof_issued_at: int | None = Header(default=None, alias="X-Rare-Agent-Issued-At"),
        proof_expires_at: int | None = Header(default=None, alias="X-Rare-Agent-Expires-At"),
        proof_signature_by_agent: str | None = Header(default=None, alias="X-Rare-Agent-Signature"),
    ) -> dict:
        try:
            token = _resolve_management_token_or_require_proof(
                authorization=authorization,
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            rare_service.authorize_upgrade_request_operation(
                upgrade_request_id=request.upgrade_request_id,
                token=token,
                operation="upgrade_complete_social",
                resource_id=f"{request.upgrade_request_id}:{request.provider}",
                proof_agent_id=proof_agent_id,
                proof_nonce=proof_nonce,
                proof_issued_at=proof_issued_at,
                proof_expires_at=proof_expires_at,
                proof_signature_by_agent=proof_signature_by_agent,
            )
            return rare_service.complete_upgrade_l2_social(
                upgrade_request_id=request.upgrade_request_id,
                provider=request.provider,
                provider_user_snapshot=request.provider_user_snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/.well-known/rare-keys.json")
    def get_keys() -> dict:
        return rare_service.get_jwks()

    return app


app = create_app()
