from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

from rare_api.integrations import (
    GcpKmsEd25519JwsSigner,
    GcpKmsHostedKeyCipher,
    GitHubOAuthAdapter,
    LocalAesGcmHostedKeyCipher,
    NoopEmailProvider,
    SendGridEmailProvider,
    resolve_public_dns_txt,
)
from rare_api.key_provider import EphemeralKeyProvider, FileKeyProvider, GcpSecretManagerKeyProvider
from rare_api.service import RareService
from rare_api.state_store import InMemoryStateStore, PostgresRedisStateStore, SqliteStateStore
from rare_identity_protocol.errors import ProtocolError, ResourceLimitError, SignatureError

DEFAULT_MAX_REQUEST_BODY_BYTES = 256 * 1024
DEFAULT_DYNAMIC_OBJECT_MAX_BYTES = 16 * 1024
DEFAULT_DYNAMIC_OBJECT_MAX_KEYS = 64
DEFAULT_DYNAMIC_OBJECT_MAX_ITEMS = 256
DEFAULT_DYNAMIC_OBJECT_MAX_DEPTH = 6
logger = logging.getLogger(__name__)


def _walk_dynamic_value(value: Any, *, depth: int) -> None:
    if depth > DEFAULT_DYNAMIC_OBJECT_MAX_DEPTH:
        raise ValueError(f"object nesting exceeds max depth {DEFAULT_DYNAMIC_OBJECT_MAX_DEPTH}")
    if isinstance(value, dict):
        if len(value) > DEFAULT_DYNAMIC_OBJECT_MAX_KEYS:
            raise ValueError(f"object key count exceeds max {DEFAULT_DYNAMIC_OBJECT_MAX_KEYS}")
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("object keys must be strings")
            _walk_dynamic_value(nested, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > DEFAULT_DYNAMIC_OBJECT_MAX_ITEMS:
            raise ValueError(f"array item count exceeds max {DEFAULT_DYNAMIC_OBJECT_MAX_ITEMS}")
        for nested in value:
            _walk_dynamic_value(nested, depth=depth + 1)
        return
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    raise ValueError("unsupported value type in dynamic object")


def _validate_dynamic_object(value: dict[str, Any], *, field_name: str) -> dict[str, Any]:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > DEFAULT_DYNAMIC_OBJECT_MAX_BYTES:
        raise ValueError(f"{field_name} exceeds max {DEFAULT_DYNAMIC_OBJECT_MAX_BYTES} bytes")
    _walk_dynamic_value(value, depth=1)
    return value


class _RequestBodyTooLargeError(RuntimeError):
    pass


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, max_body_bytes: int) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"request body too large (max {self.max_body_bytes} bytes)"},
                    )
            except ValueError:
                pass

        received = 0
        receive = request.receive

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                received += len(body)
                if received > self.max_body_bytes:
                    raise _RequestBodyTooLargeError
            return message

        request._receive = limited_receive  # type: ignore[attr-defined]
        try:
            return await call_next(request)
        except _RequestBodyTooLargeError:
            return JSONResponse(
                status_code=413,
                content={"detail": f"request body too large (max {self.max_body_bytes} bytes)"},
            )


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


class HostedManagementRecoveryEmailSendRequest(BaseModel):
    agent_id: str


class HostedManagementRecoveryEmailVerifyRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


class HostedManagementRecoverySocialStartRequest(BaseModel):
    agent_id: str
    provider: Literal["x", "github", "linkedin"]


class HostedManagementRecoverySocialCompleteRequest(BaseModel):
    agent_id: str
    provider: Literal["x", "github", "linkedin"]
    provider_user_snapshot: dict[str, Any]

    @field_validator("provider_user_snapshot")
    @classmethod
    def _validate_provider_user_snapshot(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_dynamic_object(value, field_name="provider_user_snapshot")


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

    @field_validator("action_payload")
    @classmethod
    def _validate_action_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_dynamic_object(value, field_name="action_payload")


class ProfilePatchRequest(BaseModel):
    patch: dict[str, Any]

    @field_validator("patch")
    @classmethod
    def _validate_patch(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_dynamic_object(value, field_name="patch")


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
    send_email: bool = True


class UpgradeL1SendLinkRequest(BaseModel):
    upgrade_request_id: str


class UpgradeL2SocialStartRequest(BaseModel):
    upgrade_request_id: str
    provider: Literal["x", "github", "linkedin"]


class UpgradeL2SocialCompleteRequest(BaseModel):
    upgrade_request_id: str
    provider: Literal["x", "github", "linkedin"]
    provider_user_snapshot: dict[str, Any]

    @field_validator("provider_user_snapshot")
    @classmethod
    def _validate_provider_user_snapshot(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_dynamic_object(value, field_name="provider_user_snapshot")


class VerifyUpgradeL1EmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


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


def _env_int(name: str, *, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return parsed


def _env_str(name: str, *, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value if value else default


def _env_csv(name: str, *, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = [item.strip().lower() for item in raw.split(",")]
    return [item for item in values if item]


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
    status_code, detail = _http_error_status_and_detail(exc)
    raise HTTPException(status_code=status_code, detail=detail) from exc


def _http_error_status_and_detail(exc: Exception) -> tuple[int, str]:
    if isinstance(exc, HTTPException):
        return exc.status_code, str(exc.detail)
    if isinstance(exc, KeyError):
        return 404, str(exc)
    if isinstance(exc, PermissionError):
        return 403, str(exc)
    if isinstance(exc, ResourceLimitError):
        return 429, str(exc)
    if isinstance(exc, SignatureError):
        return 401, str(exc)
    if isinstance(exc, ProtocolError):
        lower_detail = str(exc).lower()
        status = 409 if ("nonce" in lower_detail or "replay" in lower_detail) else 400
        return status, str(exc)
    logger.exception("Unhandled API exception")
    return 500, "internal server error"


def _human_time(timestamp: int | None) -> str:
    if timestamp is None:
        return "-"
    dt = datetime.fromtimestamp(timestamp, UTC)
    return dt.strftime("%b %d, %Y, %I:%M %p UTC").replace(" 0", " ")


def _status_page_html(
    *,
    eyebrow: str,
    title: str,
    message: str,
    accent: str,
    detail_rows: list[tuple[str, str]] | None = None,
) -> str:
    rows = ""
    if detail_rows:
        rendered = []
        for label, value in detail_rows:
            rendered.append(
                "<div style=\"display:flex;justify-content:space-between;gap:16px;padding:12px 0;border-top:1px solid rgba(31,26,23,0.09);\">"
                f"<span style=\"color:#6f675b;\">{escape(label)}</span>"
                f"<strong style=\"text-align:right;\">{escape(value)}</strong>"
                "</div>"
            )
        rows = "".join(rendered)
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | Rare</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />
  </head>
  <body style="margin:0;background:#f2f2f2;color:#111111;font-family:Georgia,'Times New Roman',serif;">
    <main style="max-width:720px;margin:0 auto;padding:28px 16px 56px;">
      <section style="background:#ffffff;border:1px solid #d8d8d8;border-radius:26px;overflow:hidden;box-shadow:0 18px 40px rgba(17,17,17,0.08);">
        <div style="padding:28px 32px 18px;background:{accent};">
          <div style="font-family:'Courier New',monospace;font-size:12px;letter-spacing:0.18em;text-transform:uppercase;color:#5a5a5a;margin-bottom:14px;">{escape(eyebrow)}</div>
          <h1 style="margin:0;font-size:42px;line-height:0.95;">{escape(title)}</h1>
        </div>
        <div style="padding:28px 32px 32px;font-size:17px;line-height:1.65;">
          <p style="margin:0 0 18px;">{escape(message)}</p>
          {rows}
        </div>
      </section>
    </main>
  </body>
</html>
"""


def _upgrade_verify_success_html(result: dict[str, Any]) -> str:
    return _status_page_html(
        eyebrow="Rare Identity",
        title="Email verified",
        message="Your Rare email verification is complete and the agent has been upgraded.",
        accent="linear-gradient(135deg,#fafafa 0%,#ebebeb 100%)",
        detail_rows=[
            ("Level", str(result.get("level", "-"))),
            ("Status", str(result.get("status", "-"))),
            ("Processed", _human_time(int(datetime.now(UTC).timestamp()))),
        ],
    )


def _recovery_verify_success_html(result: dict[str, Any]) -> str:
    token = str(result.get("hosted_management_token") or "")
    token_display = token if token else "Issued successfully"
    return _status_page_html(
        eyebrow="Rare Recovery",
        title="Hosted access recovered",
        message="Your hosted management token has been recovered. Store it now before closing this page.",
        accent="linear-gradient(135deg,#fafafa 0%,#ebebeb 100%)",
        detail_rows=[
            ("Agent", str(result.get("agent_id", "-"))),
            ("Expires", _human_time(result.get("hosted_management_token_expires_at"))),
            ("Token", token_display),
        ],
    )


def _error_status_page_html(*, eyebrow: str, title: str, message: str) -> str:
    return _status_page_html(
        eyebrow=eyebrow,
        title=title,
        message=message,
        accent="linear-gradient(135deg,#f1f1f1 0%,#dfdfdf 100%)",
    )


def create_app(service: RareService | None = None, *, admin_token: str | None = None) -> FastAPI:
    enable_docs = _env_bool("RARE_ENABLE_OPENAPI_DOCS", default=False)
    max_body_bytes = _env_int(
        "RARE_MAX_REQUEST_BODY_BYTES",
        default=DEFAULT_MAX_REQUEST_BODY_BYTES,
        minimum=1024,
    )
    if service is None:
        runtime_env = _env_str("RARE_ENV", default="dev").lower()
        if runtime_env not in {"dev", "staging", "prod"}:
            raise ValueError("RARE_ENV must be one of: dev, staging, prod")
        public_base_url = _env_str("RARE_PUBLIC_BASE_URL", default="")
        if runtime_env in {"staging", "prod"} and not public_base_url:
            raise ValueError("RARE_PUBLIC_BASE_URL is required when RARE_ENV is staging/prod")
        storage_backend = _env_str("RARE_STORAGE_BACKEND", default="memory").lower()
        if storage_backend not in {"memory", "postgres_redis", "sqlite"}:
            raise ValueError("RARE_STORAGE_BACKEND must be one of: memory, postgres_redis, sqlite")
        if runtime_env in {"staging", "prod"} and storage_backend == "memory":
            raise RuntimeError("RARE_STORAGE_BACKEND=memory is forbidden when RARE_ENV is staging/prod")

        if storage_backend == "postgres_redis":
            state_store = PostgresRedisStateStore(
                namespace=_env_str("RARE_STATE_NAMESPACE", default=f"{runtime_env}:default"),
                postgres_dsn=os.getenv("RARE_POSTGRES_DSN"),
                redis_url=os.getenv("RARE_REDIS_URL"),
            )
        elif storage_backend == "sqlite":
            sqlite_path = _env_str(
                "RARE_SQLITE_STATE_FILE",
                default=str(Path.home() / ".config" / "rare" / f"{runtime_env}-state.sqlite3"),
            )
            state_store = SqliteStateStore(path=sqlite_path)
        else:
            state_store = InMemoryStateStore()

        key_backend = _env_str("RARE_KEY_PROVIDER", default="file").lower()
        keyring_path = _env_str(
            "RARE_KEYRING_FILE",
            default=str(Path.home() / ".config" / "rare" / "keyring.json"),
        )
        if key_backend == "file":
            key_provider = FileKeyProvider(path=keyring_path)
        elif key_backend == "ephemeral":
            key_provider = EphemeralKeyProvider()
        elif key_backend in {"gcp", "gcp_secret_manager"}:
            key_provider = GcpSecretManagerKeyProvider(
                secret_name=_env_str("RARE_GCP_KEYRING_SECRET", default=f"rare-keyring-{runtime_env}"),
                project_id=os.getenv("RARE_GCP_PROJECT_ID"),
            )
        else:
            raise ValueError("RARE_KEY_PROVIDER must be one of: file, ephemeral, gcp_secret_manager")

        hosted_key_cipher_name = _env_str("RARE_HOSTED_KEY_CIPHER", default="plaintext").lower()
        if hosted_key_cipher_name == "aesgcm":
            cipher_key = os.getenv("RARE_HOSTED_KEY_CIPHER_KEY")
            if not cipher_key:
                raise ValueError("RARE_HOSTED_KEY_CIPHER_KEY is required when RARE_HOSTED_KEY_CIPHER=aesgcm")
            hosted_key_cipher = LocalAesGcmHostedKeyCipher(key_b64=cipher_key)
        elif hosted_key_cipher_name == "gcp_kms":
            kms_key_name = os.getenv("RARE_HOSTED_KEY_CIPHER_KMS_KEY")
            if not kms_key_name:
                raise ValueError(
                    "RARE_HOSTED_KEY_CIPHER_KMS_KEY is required when RARE_HOSTED_KEY_CIPHER=gcp_kms"
                )
            hosted_key_cipher = GcpKmsHostedKeyCipher(key_name=kms_key_name)
        else:
            hosted_key_cipher = None

        identity_jws_signer = None
        rare_delegation_signer = None
        if key_backend in {"gcp", "gcp_kms", "gcp_secret_manager"}:
            identity_kms_key_version = os.getenv("RARE_KMS_IDENTITY_KEY_VERSION")
            rare_signer_kms_key_version = os.getenv("RARE_KMS_RARE_SIGNER_KEY_VERSION")
            if identity_kms_key_version and rare_signer_kms_key_version:
                identity_jws_signer = GcpKmsEd25519JwsSigner(
                    kid=_env_str("RARE_KMS_IDENTITY_KID", default="rare-kms-identity"),
                    key_version_name=identity_kms_key_version,
                )
                rare_delegation_signer = GcpKmsEd25519JwsSigner(
                    kid=_env_str("RARE_KMS_RARE_SIGNER_KID", default="rare-kms-signer"),
                    key_version_name=rare_signer_kms_key_version,
                )

        email_provider_name = _env_str("RARE_EMAIL_PROVIDER", default="noop").lower()
        if email_provider_name == "sendgrid":
            sendgrid_api_key = os.getenv("RARE_SENDGRID_API_KEY")
            sendgrid_from_email = os.getenv("RARE_SENDGRID_FROM_EMAIL")
            if not sendgrid_api_key or not sendgrid_from_email:
                raise ValueError("SendGrid requires RARE_SENDGRID_API_KEY and RARE_SENDGRID_FROM_EMAIL")
            email_provider = SendGridEmailProvider(
                api_key=sendgrid_api_key,
                from_email=sendgrid_from_email,
            )
        else:
            email_provider = NoopEmailProvider()

        dns_resolver_name = _env_str(
            "RARE_DNS_RESOLVER",
            default="public" if runtime_env in {"staging", "prod"} else "noop",
        ).lower()
        if dns_resolver_name == "public":
            dns_txt_resolver = resolve_public_dns_txt
        elif dns_resolver_name == "noop":
            dns_txt_resolver = None
        else:
            raise ValueError("RARE_DNS_RESOLVER must be one of: noop, public")

        default_social_providers = ["github"] if runtime_env in {"staging", "prod"} else ["github", "x", "linkedin"]
        enabled_social_providers = _env_csv(
            "RARE_SOCIAL_PROVIDER_ALLOWLIST",
            default=default_social_providers,
        )
        social_provider_adapters = {}
        if "github" in enabled_social_providers:
            github_client_id = os.getenv("RARE_GITHUB_CLIENT_ID")
            github_client_secret = os.getenv("RARE_GITHUB_CLIENT_SECRET")
            if runtime_env in {"staging", "prod"}:
                if not github_client_id or not github_client_secret:
                    raise ValueError("GitHub OAuth requires RARE_GITHUB_CLIENT_ID and RARE_GITHUB_CLIENT_SECRET")
                social_provider_adapters["github"] = GitHubOAuthAdapter(
                    client_id=github_client_id,
                    client_secret=github_client_secret,
                    redirect_uri=f"{public_base_url.rstrip('/')}/v1/upgrades/l2/social/callback?provider=github",
                )
            else:
                social_provider_adapters["github"] = GitHubOAuthAdapter(
                    client_id=github_client_id or "rare-dev-github",
                    client_secret=github_client_secret or "rare-dev-secret",
                    redirect_uri=(
                        f"{public_base_url.rstrip('/')}/v1/upgrades/l2/social/callback?provider=github"
                        if public_base_url
                        else "https://rare.local/v1/upgrades/l2/social/callback?provider=github"
                    ),
                ) if github_client_id and github_client_secret else None  # type: ignore[assignment]
        unsupported_enabled = set(enabled_social_providers) - {"github"}
        if unsupported_enabled and runtime_env in {"staging", "prod"}:
            raise ValueError("Only GitHub OAuth is implemented for staging/prod")
        social_provider_adapters = {key: value for key, value in social_provider_adapters.items() if value is not None}

        resolved_admin_token = admin_token if admin_token is not None else os.getenv("RARE_ADMIN_TOKEN")
        rare_service = RareService(
            admin_token=resolved_admin_token,
            allow_local_upgrade_shortcuts=_env_bool("RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS", default=False),
            public_base_url=public_base_url or None,
            max_agent_records=_env_int("RARE_MAX_AGENT_RECORDS", default=100_000),
            max_upgrade_requests=_env_int("RARE_MAX_UPGRADE_REQUESTS", default=100_000),
            public_write_rate_limit_per_minute=_env_int("RARE_PUBLIC_WRITE_RATE_LIMIT_PER_MINUTE", default=120),
            state_store=state_store,
            key_provider=key_provider,
            hosted_key_cipher=hosted_key_cipher,
            email_provider=email_provider,
            dns_txt_resolver=dns_txt_resolver,
            social_provider_adapters=social_provider_adapters or None,
            identity_jws_signer=identity_jws_signer,
            rare_delegation_signer=rare_delegation_signer,
        )
    else:
        rare_service = service
        if admin_token is not None:
            rare_service.set_admin_token(admin_token)
    enable_legacy_magic_link_query = _env_bool(
        "RARE_ENABLE_LEGACY_MAGIC_LINK_QUERY_VERIFY",
        default=bool(getattr(rare_service, "public_base_url", None)),
    )
    app = FastAPI(
        title="Rare API Gateway",
        version="0.2.0",
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )
    app.add_middleware(MaxBodySizeMiddleware, max_body_bytes=max_body_bytes)
    static_dir = Path(__file__).with_name("static")
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return rare_service.health_report()

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        try:
            report = rare_service.readiness_report()
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=503, content={"status": "error", "detail": str(exc)})
        status_code = 200 if report.get("status") == "ok" else 503
        return JSONResponse(status_code=status_code, content=report)

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
    def self_register(request: SelfRegisterRequest, request_meta: Request) -> dict:
        try:
            client_id = request_meta.client.host if request_meta.client and request_meta.client.host else "unknown"
            rare_service.enforce_public_write_limit(operation="self_register", client_id=client_id)
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

    @app.get("/v1/signer/recovery/factors/{agent_id}")
    def get_management_recovery_factors(agent_id: str) -> dict:
        try:
            return rare_service.get_hosted_management_recovery_factors(agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/recovery/email/send-link")
    def send_management_recovery_email_link(
        request: HostedManagementRecoveryEmailSendRequest,
        request_meta: Request,
    ) -> dict:
        try:
            client_id = request_meta.client.host if request_meta.client and request_meta.client.host else "unknown"
            rare_service.enforce_public_write_limit(operation="recovery_email_send", client_id=client_id)
            return rare_service.send_hosted_management_recovery_email_link(agent_id=request.agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/recovery/email/verify")
    def verify_management_recovery_email(request: HostedManagementRecoveryEmailVerifyRequest) -> dict:
        try:
            return rare_service.verify_hosted_management_recovery_email(token=request.token)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/signer/recovery/email/verify")
    def verify_management_recovery_email_legacy(token: str = Query(...)) -> HTMLResponse:
        try:
            return HTMLResponse(content=_recovery_verify_success_html(rare_service.verify_hosted_management_recovery_email(token=token)))
        except Exception as exc:  # noqa: BLE001
            status_code, detail = _http_error_status_and_detail(exc)
            return HTMLResponse(
                status_code=status_code,
                content=_error_status_page_html(
                    eyebrow="Rare Recovery",
                    title="Recovery link failed",
                    message=detail,
                ),
            )

    @app.post("/v1/signer/recovery/social/start")
    def start_management_recovery_social(
        request: HostedManagementRecoverySocialStartRequest,
        request_meta: Request,
    ) -> dict:
        try:
            client_id = request_meta.client.host if request_meta.client and request_meta.client.host else "unknown"
            rare_service.enforce_public_write_limit(operation="recovery_social_start", client_id=client_id)
            return rare_service.start_hosted_management_recovery_social(
                agent_id=request.agent_id,
                provider=request.provider,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.post("/v1/signer/recovery/social/complete")
    def complete_management_recovery_social(
        request: HostedManagementRecoverySocialCompleteRequest,
    ) -> dict:
        try:
            return rare_service.complete_hosted_management_recovery_social(
                agent_id=request.agent_id,
                provider=request.provider,
                provider_user_snapshot=request.provider_user_snapshot,
            )
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

    @app.get("/v1/admin/agents")
    def list_agents(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.list_agents()
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/admin/agents/{agent_id}")
    def get_agent(agent_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.get_agent_details(agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/admin/agents/{agent_id}/audit")
    def get_agent_audit(agent_id: str, authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.list_agent_audit_events(agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/admin/upgrades/{upgrade_request_id}")
    def get_admin_upgrade(upgrade_request_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.get_admin_upgrade_request(upgrade_request_id=upgrade_request_id)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/admin/platforms")
    def list_platforms(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.list_platforms()
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/admin/platforms/{platform_aud}")
    def get_platform(platform_aud: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.get_platform(platform_aud=platform_aud)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/admin/audit")
    def list_audit(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        try:
            _authorize_admin_call(authorization)
            return rare_service.list_audit_events()
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
                send_email=request.send_email,
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

    @app.post("/v1/upgrades/l1/email/verify")
    def verify_upgrade_l1_email(request: VerifyUpgradeL1EmailRequest) -> dict:
        try:
            return rare_service.verify_upgrade_l1_email(token=request.token)
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    if enable_legacy_magic_link_query:

        @app.get("/v1/upgrades/l1/email/verify")
        def verify_upgrade_l1_email_legacy(token: str = Query(...)) -> HTMLResponse:
            try:
                return HTMLResponse(content=_upgrade_verify_success_html(rare_service.verify_upgrade_l1_email(token=token)))
            except Exception as exc:  # noqa: BLE001
                status_code, detail = _http_error_status_and_detail(exc)
                return HTMLResponse(
                    status_code=status_code,
                    content=_error_status_page_html(
                        eyebrow="Rare Identity",
                        title="Verification link failed",
                        message=detail,
                    ),
                )

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
        provider: Literal["x", "github", "linkedin"] = Query(...),
        code: str = Query(...),
        state: str = Query(...),
    ) -> dict:
        try:
            if rare_service.has_hosted_management_recovery_oauth_state(state=state):
                return rare_service.complete_hosted_management_recovery_social_callback(
                    provider=provider,
                    code=code,
                    state=state,
                )
            return rare_service.social_callback_upgrade_l2(
                provider=provider,
                code=code,
                state=state,
            )
        except Exception as exc:  # noqa: BLE001
            _raise_http(exc)

    @app.get("/v1/signer/recovery/social/callback")
    def social_callback_management_recovery(
        provider: Literal["x", "github", "linkedin"] = Query(...),
        code: str = Query(...),
        state: str = Query(...),
    ) -> dict:
        try:
            return rare_service.complete_hosted_management_recovery_social_callback(
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
