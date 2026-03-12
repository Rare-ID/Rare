from __future__ import annotations

import base64
import hashlib
import html
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from rare_identity_protocol.errors import TokenValidationError


class HostedKeyCipher(Protocol):
    def encrypt_text(self, value: str) -> str:
        """Encrypt a UTF-8 payload and return an opaque ASCII string."""

    def decrypt_text(self, value: str) -> str:
        """Decrypt an opaque ASCII payload produced by encrypt_text."""

    def readiness(self) -> dict[str, Any]:
        """Return runtime readiness information for the cipher backend."""


class PlaintextHostedKeyCipher:
    """Development fallback. Production deployments should replace this."""

    def encrypt_text(self, value: str) -> str:
        return value

    def decrypt_text(self, value: str) -> str:
        return value

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "plaintext"}


class LocalAesGcmHostedKeyCipher:
    def __init__(self, *, key_b64: str) -> None:
        key = base64.urlsafe_b64decode(key_b64.encode("ascii"))
        if len(key) not in {16, 24, 32}:
            raise ValueError("AES-GCM key must decode to 16, 24, or 32 bytes")
        self._aesgcm = AESGCM(key)

    def encrypt_text(self, value: str) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = self._aesgcm.encrypt(nonce, value.encode("utf-8"), None)
        payload = {"alg": "aesgcm", "nonce": _b64url_encode(nonce), "ciphertext": _b64url_encode(ciphertext)}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def decrypt_text(self, value: str) -> str:
        payload = json.loads(value)
        nonce = _b64url_decode(str(payload["nonce"]))
        ciphertext = _b64url_decode(str(payload["ciphertext"]))
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def readiness(self) -> dict[str, Any]:
        probe = self.encrypt_text("rare-ready")
        if self.decrypt_text(probe) != "rare-ready":
            raise RuntimeError("AES-GCM hosted key cipher self-check failed")
        return {"status": "ok", "backend": "aesgcm"}


class GcpKmsHostedKeyCipher:
    """
    Wiring placeholder for production GCP deployments.

    This class is intentionally import-safe when google-cloud-kms is unavailable so local tests
    can still run. Runtime usage requires the dependency and valid GCP credentials.
    """

    def __init__(self, *, key_name: str) -> None:
        self.key_name = key_name
        try:
            from google.cloud import kms  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("google-cloud-kms is required for GcpKmsHostedKeyCipher") from exc
        self._client = kms.KeyManagementServiceClient()

    def encrypt_text(self, value: str) -> str:
        response = self._client.encrypt(request={"name": self.key_name, "plaintext": value.encode("utf-8")})
        return json.dumps(
            {
                "alg": "gcp-kms",
                "key_name": self.key_name,
                "ciphertext": _b64url_encode(bytes(response.ciphertext)),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def decrypt_text(self, value: str) -> str:
        payload = json.loads(value)
        ciphertext = _b64url_decode(str(payload["ciphertext"]))
        response = self._client.decrypt(request={"name": self.key_name, "ciphertext": ciphertext})
        return bytes(response.plaintext).decode("utf-8")

    def readiness(self) -> dict[str, Any]:
        probe = self.encrypt_text("rare-ready")
        if self.decrypt_text(probe) != "rare-ready":
            raise RuntimeError("GCP KMS hosted key cipher self-check failed")
        return {"status": "ok", "backend": "gcp_kms", "key_name": self.key_name}


class EmailProvider(Protocol):
    def send_upgrade_link(
        self,
        *,
        recipient_hint: str,
        upgrade_request_id: str,
        verify_url: str,
        expires_at: int,
    ) -> dict[str, Any]:
        """Send the upgrade link and return provider metadata."""

    def send_management_recovery_link(
        self,
        *,
        recipient_hint: str,
        agent_id: str,
        verify_url: str,
        expires_at: int,
    ) -> dict[str, Any]:
        """Send the hosted management token recovery link and return provider metadata."""

    def readiness(self) -> dict[str, Any]:
        """Return runtime readiness information for the email provider."""


class NoopEmailProvider:
    @staticmethod
    def _build_response(
        *,
        recipient_hint: str,
        verify_url: str,
        expires_at: int,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "provider": "noop",
            "recipient_hint": recipient_hint,
            "verify_url": verify_url,
            "expires_at": expires_at,
            **extra,
        }

    def send_upgrade_link(
        self,
        *,
        recipient_hint: str,
        upgrade_request_id: str,
        verify_url: str,
        expires_at: int,
    ) -> dict[str, Any]:
        return self._build_response(
            recipient_hint=recipient_hint,
            verify_url=verify_url,
            expires_at=expires_at,
            extra={"upgrade_request_id": upgrade_request_id},
        )

    def send_management_recovery_link(
        self,
        *,
        recipient_hint: str,
        agent_id: str,
        verify_url: str,
        expires_at: int,
    ) -> dict[str, Any]:
        return self._build_response(
            recipient_hint=recipient_hint,
            verify_url=verify_url,
            expires_at=expires_at,
            extra={"agent_id": agent_id},
        )

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "noop"}


class SendGridEmailProvider:
    def __init__(self, *, api_key: str, from_email: str, http_client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self._http_client = http_client

    def send_upgrade_link(
        self,
        *,
        recipient_hint: str,
        upgrade_request_id: str,
        verify_url: str,
        expires_at: int,
    ) -> dict[str, Any]:
        response = self._send_mail(
            recipient_hint=recipient_hint,
            subject="Rare identity upgrade verification",
            text_body=(
                f"Verify your Rare identity upgrade request {upgrade_request_id}.\n\n"
                f"{verify_url}\n\n"
                f"Expires: {_human_deadline(expires_at)}\n\n"
                "If you did not request this change, you can ignore this email."
            ),
            html_body=_build_upgrade_email_html(
                upgrade_request_id=upgrade_request_id,
                verify_url=verify_url,
                expires_at=expires_at,
                from_email=self.from_email,
            ),
        )
        return {
            **response,
            "upgrade_request_id": upgrade_request_id,
            "verify_url": verify_url,
            "expires_at": expires_at,
        }

    def send_management_recovery_link(
        self,
        *,
        recipient_hint: str,
        agent_id: str,
        verify_url: str,
        expires_at: int,
    ) -> dict[str, Any]:
        response = self._send_mail(
            recipient_hint=recipient_hint,
            subject="Rare hosted token recovery",
            text_body=(
                f"Recover the Rare hosted management token for agent {agent_id}.\n\n"
                f"{verify_url}\n\n"
                f"Expires: {_human_deadline(expires_at)}\n\n"
                "If you did not request this recovery, you can ignore this email."
            ),
            html_body=_build_recovery_email_html(
                agent_id=agent_id,
                verify_url=verify_url,
                expires_at=expires_at,
                from_email=self.from_email,
            ),
        )
        return {
            **response,
            "agent_id": agent_id,
            "verify_url": verify_url,
            "expires_at": expires_at,
        }

    def _send_mail(
        self,
        *,
        recipient_hint: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
    ) -> dict[str, Any]:
        content = [
            {
                "type": "text/plain",
                "value": text_body,
            }
        ]
        if html_body is not None:
            content.append(
                {
                    "type": "text/html",
                    "value": html_body,
                }
            )
        payload = {
            "personalizations": [{"to": [{"email": recipient_hint}]}],
            "from": {"email": self.from_email},
            "subject": subject,
            "content": content,
        }
        reply_to = _reply_to_email(self.from_email)
        if reply_to is not None:
            payload["reply_to"] = {"email": reply_to}
        response = self._post_mail(payload=payload)
        response.raise_for_status()
        request_id = response.headers.get("x-message-id") or response.headers.get("x-request-id")
        return {
            "provider": "sendgrid",
            "recipient_hint": recipient_hint,
            "from_email": self.from_email,
            "delivery_status": "queued",
            "provider_request_id": request_id,
        }

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "sendgrid", "from_email": self.from_email}

    def _post_mail(self, *, payload: dict[str, Any]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self._http_client is not None:
            return self._http_client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers=headers,
                json=payload,
            )
        with httpx.Client(timeout=10.0) as client:
            return client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers=headers,
                json=payload,
            )


def _reply_to_email(from_email: str) -> str | None:
    local, sep, domain = from_email.partition("@")
    if sep != "@" or not domain:
        return None
    if local.lower() == "contact":
        return from_email
    return f"contact@{domain}"


def _format_email_timestamp(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp, UTC)
    return dt.strftime("%b %d, %Y, %I:%M %p UTC").replace(" 0", " ")


def _human_deadline(expires_at: int) -> str:
    now = int(datetime.now(UTC).timestamp())
    remaining = max(0, expires_at - now)
    if remaining < 3600:
        amount = max(1, remaining // 60 or 1)
        unit = "minute"
    elif remaining < 86400:
        amount = remaining // 3600
        unit = "hour"
    else:
        amount = remaining // 86400
        unit = "day"
    plural = "" if amount == 1 else "s"
    return f"{_format_email_timestamp(expires_at)} (in about {amount} {unit}{plural})"


def _email_shell(*, eyebrow: str, title: str, body_html: str, cta_label: str, cta_url: str, footer_email: str) -> str:
    safe_eyebrow = html.escape(eyebrow)
    safe_title = html.escape(title)
    safe_url = html.escape(cta_url, quote=True)
    safe_cta = html.escape(cta_label)
    safe_footer_email = html.escape(_reply_to_email(footer_email) or footer_email)
    return f"""\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="light only" />
    <meta name="supported-color-schemes" content="light" />
    <style>
      :root {{
        color-scheme: light only;
        supported-color-schemes: light;
      }}
      body, table, td, div, p, a {{
        font-family: Georgia, "Times New Roman", serif;
      }}
    </style>
  </head>
  <body style="margin:0;padding:0;background:#f2f2f2;color:#111111;font-family:Georgia,'Times New Roman',serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #d8d8d8;border-radius:24px;overflow:hidden;">
            <tr>
              <td style="padding:28px 32px 18px;background:#ffffff;border-bottom:1px solid #e5e5e5;">
                <div style="font-family:'Courier New',monospace;font-size:12px;letter-spacing:0.18em;text-transform:uppercase;color:#555555 !important;-webkit-text-fill-color:#555555;margin-bottom:14px;">{safe_eyebrow}</div>
                <div style="font-size:38px;line-height:0.95;font-weight:700;color:#111111 !important;-webkit-text-fill-color:#111111;">{safe_title}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:28px 32px 32px;font-size:16px;line-height:1.65;color:#111111 !important;-webkit-text-fill-color:#111111;">
                {body_html}
                <p style="margin:28px 0 0;">
                  <a href="{safe_url}" style="display:inline-block;padding:14px 22px;background:#111111;color:#ffffff;text-decoration:none;border-radius:14px;font-weight:700;">{safe_cta}</a>
                </p>
                <p style="margin:24px 0 0;color:#666666;font-size:14px;line-height:1.6;">
                  Need help? Reply to {safe_footer_email}.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _build_upgrade_email_html(*, upgrade_request_id: str, verify_url: str, expires_at: int, from_email: str) -> str:
    body_html = (
        f"<p style=\"margin:0 0 16px;\">Verify your Rare L1 upgrade request "
        f"<strong>{html.escape(upgrade_request_id)}</strong>.</p>"
        f"<p style=\"margin:0 0 16px;\">This link expires <strong>{html.escape(_human_deadline(expires_at))}</strong>.</p>"
        "<p style=\"margin:0;\">If you did not request this change, you can ignore this email.</p>"
    )
    return _email_shell(
        eyebrow="Rare Identity",
        title="Verify your email",
        body_html=body_html,
        cta_label="Verify email",
        cta_url=verify_url,
        footer_email=from_email,
    )


def _build_recovery_email_html(*, agent_id: str, verify_url: str, expires_at: int, from_email: str) -> str:
    body_html = (
        f"<p style=\"margin:0 0 16px;\">Recover the hosted management token for "
        f"<strong>{html.escape(agent_id)}</strong>.</p>"
        f"<p style=\"margin:0 0 16px;\">This recovery link expires <strong>{html.escape(_human_deadline(expires_at))}</strong>.</p>"
        "<p style=\"margin:0;\">If you did not request this recovery, you can ignore this email.</p>"
    )
    return _email_shell(
        eyebrow="Rare Recovery",
        title="Recover hosted access",
        body_html=body_html,
        cta_label="Recover token",
        cta_url=verify_url,
        footer_email=from_email,
    )


class SocialProviderAdapter(Protocol):
    provider: str

    def build_authorize_url(self, *, state: str) -> str:
        """Return the provider authorize URL."""

    def exchange_code(self, *, code: str, state: str) -> dict[str, Any]:
        """Return a normalized provider snapshot."""

    def readiness(self) -> dict[str, Any]:
        """Return runtime readiness information for the social provider."""


class JwsSigner(Protocol):
    kid: str

    def sign_bytes(self, signing_input: bytes) -> bytes:
        """Sign raw JWS signing input bytes."""

    def public_key(self) -> Ed25519PublicKey:
        """Return the Ed25519 public key for verification/JWKS."""

    def readiness(self) -> dict[str, Any]:
        """Return runtime readiness information for the signer."""


@dataclass(frozen=True)
class LocalEd25519JwsSigner:
    kid: str
    private_key: Ed25519PrivateKey

    def sign_bytes(self, signing_input: bytes) -> bytes:
        return self.private_key.sign(signing_input)

    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "local", "kid": self.kid}


class GcpKmsEd25519JwsSigner:
    def __init__(self, *, kid: str, key_version_name: str) -> None:
        self.kid = kid
        self.key_version_name = key_version_name
        try:
            from google.cloud import kms  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("google-cloud-kms is required for GcpKmsEd25519JwsSigner") from exc
        self._client = kms.KeyManagementServiceClient()
        self._public_key: Ed25519PublicKey | None = None

    def sign_bytes(self, signing_input: bytes) -> bytes:
        response = self._client.asymmetric_sign(
            request={
                "name": self.key_version_name,
                "data": signing_input,
            }
        )
        return bytes(response.signature)

    def public_key(self) -> Ed25519PublicKey:
        if self._public_key is None:
            response = self._client.get_public_key(request={"name": self.key_version_name})
            loaded = serialization.load_pem_public_key(response.pem.encode("utf-8"))
            if not isinstance(loaded, Ed25519PublicKey):
                raise RuntimeError("KMS public key is not Ed25519")
            self._public_key = loaded
        return self._public_key

    def readiness(self) -> dict[str, Any]:
        self.public_key()
        return {"status": "ok", "backend": "gcp_kms", "kid": self.kid, "key_version_name": self.key_version_name}


@dataclass(frozen=True)
class StubSocialProviderAdapter:
    provider: str

    def build_authorize_url(self, *, state: str) -> str:
        return f"https://oauth.{self.provider}.local/authorize?state={state}&client_id=rare-dev"

    def exchange_code(self, *, code: str, state: str) -> dict[str, Any]:
        digest = hashlib.sha256(f"{self.provider}:{state}:{code}".encode("utf-8")).hexdigest()
        suffix = digest[:10]
        if self.provider == "github":
            return {
                "provider": self.provider,
                "provider_user_id": digest[:12],
                "username_or_handle": f"gh_{suffix}",
                "display_name": f"GitHub {suffix}",
                "profile_url": f"https://github.com/gh_{suffix}",
                "raw_snapshot": {"id": digest[:12], "login": f"gh_{suffix}"},
            }
        if self.provider == "x":
            return {
                "provider": self.provider,
                "provider_user_id": digest[:12],
                "username_or_handle": f"x_{suffix}",
                "display_name": f"X {suffix}",
                "profile_url": f"https://x.com/x_{suffix}",
                "raw_snapshot": {"id": digest[:12], "handle": f"x_{suffix}"},
            }
        if self.provider == "linkedin":
            return {
                "provider": self.provider,
                "provider_user_id": digest[:12],
                "username_or_handle": f"li_{suffix}",
                "display_name": f"LinkedIn {suffix}",
                "profile_url": f"https://www.linkedin.com/in/li_{suffix}",
                "raw_snapshot": {"id": digest[:12], "vanity_name": f"li_{suffix}"},
            }
        raise TokenValidationError("unsupported social provider")

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "stub", "provider": self.provider}


@dataclass(frozen=True)
class GitHubOAuthAdapter:
    client_id: str
    client_secret: str
    redirect_uri: str
    provider: str = "github"
    http_client: httpx.Client | None = None

    def build_authorize_url(self, *, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "read:user user:email",
                "state": state,
            }
        )
        return f"https://github.com/login/oauth/authorize?{query}"

    def exchange_code(self, *, code: str, state: str) -> dict[str, Any]:
        if self.http_client is not None:
            user_payload = self._exchange_with_client(client=self.http_client, code=code, state=state)
        else:
            with httpx.Client(timeout=10.0) as client:
                user_payload = self._exchange_with_client(client=client, code=code, state=state)
        user_id = str(user_payload.get("id") or "").strip()
        login = str(user_payload.get("login") or "").strip()
        if not user_id or not login:
            raise TokenValidationError("github user profile missing id/login")
        profile_url = str(user_payload.get("html_url") or f"https://github.com/{login}")
        display_name = str(user_payload.get("name") or login)
        return {
            "provider": self.provider,
            "provider_user_id": user_id,
            "username_or_handle": login,
            "display_name": display_name,
            "profile_url": profile_url,
            "raw_snapshot": user_payload,
        }

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "oauth", "provider": self.provider, "redirect_uri": self.redirect_uri}

    def _exchange_with_client(self, *, client: Any, code: str, state: str) -> dict[str, Any]:
        token_response = client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "state": state,
            },
        )
        token_response.raise_for_status()
        token_payload = token_response.json()
        access_token = str(token_payload.get("access_token") or "").strip()
        if not access_token:
            raise TokenValidationError("github access token missing")

        user_response = client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        user_response.raise_for_status()
        return user_response.json()


def default_social_provider_adapters() -> dict[str, SocialProviderAdapter]:
    return {
        "github": StubSocialProviderAdapter(provider="github"),
        "x": StubSocialProviderAdapter(provider="x"),
        "linkedin": StubSocialProviderAdapter(provider="linkedin"),
    }


def resolve_public_dns_txt(name: str) -> list[str]:
    try:
        import dns.resolver  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("dnspython is required for public DNS TXT resolution") from exc

    try:
        answers = dns.resolver.resolve(name, "TXT")
    except Exception as exc:  # noqa: BLE001
        if exc.__class__.__name__ in {"NXDOMAIN", "NoAnswer", "NoNameservers", "LifetimeTimeout"}:
            return []
        raise

    values: list[str] = []
    for answer in answers:
        strings = getattr(answer, "strings", None)
        if strings is not None:
            values.append("".join(part.decode("utf-8") for part in strings))
            continue
        values.append(str(answer).strip('"'))
    return values


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))
