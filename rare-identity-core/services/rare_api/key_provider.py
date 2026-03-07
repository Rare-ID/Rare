from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from rare_identity_protocol import generate_ed25519_keypair, now_ts


DEFAULT_KEY_RETIRE_SECONDS = 365 * 24 * 3600


@dataclass
class PersistedSigningKey:
    kid: str
    private_key: str
    created_at: int
    retire_at: int


@dataclass
class PersistedKeyRing:
    active_identity_kid: str
    identity_keys: list[PersistedSigningKey]
    rare_signer_key: PersistedSigningKey


class KeyProvider(Protocol):
    def load_or_create(self) -> PersistedKeyRing:
        """Load an existing key ring or create one if it does not exist."""

    def readiness(self) -> dict[str, Any]:
        """Return runtime readiness information for the backing store."""


def _new_kid(prefix: str) -> str:
    # Date + 8 hex chars avoids monthly collisions while staying human-readable.
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(4)}"


def _build_new_keyring() -> PersistedKeyRing:
    now = now_ts()
    identity_private, _ = generate_ed25519_keypair()
    signer_private, _ = generate_ed25519_keypair()
    identity_kid = _new_kid("rare")
    signer_kid = _new_kid("rare-signer")
    identity_key = PersistedSigningKey(
        kid=identity_kid,
        private_key=identity_private,
        created_at=now,
        retire_at=now + DEFAULT_KEY_RETIRE_SECONDS,
    )
    signer_key = PersistedSigningKey(
        kid=signer_kid,
        private_key=signer_private,
        created_at=now,
        retire_at=now + DEFAULT_KEY_RETIRE_SECONDS,
    )
    return PersistedKeyRing(
        active_identity_kid=identity_key.kid,
        identity_keys=[identity_key],
        rare_signer_key=signer_key,
    )


class EphemeralKeyProvider:
    """Process-local provider mainly for tests."""

    def __init__(self) -> None:
        self._keyring: PersistedKeyRing | None = None

    def load_or_create(self) -> PersistedKeyRing:
        if self._keyring is None:
            self._keyring = _build_new_keyring()
        return self._keyring

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "ephemeral"}


class FileKeyProvider:
    """Stable local/CI key provider backed by a JSON keyring file."""

    def __init__(self, *, path: str | Path) -> None:
        self.path = Path(path)

    def _write(self, keyring: PersistedKeyRing) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "active_identity_kid": keyring.active_identity_kid,
            "identity_keys": [asdict(item) for item in keyring.identity_keys],
            "rare_signer_key": asdict(keyring.rare_signer_key),
        }
        self.path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _read(self) -> PersistedKeyRing:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        identity_keys = [PersistedSigningKey(**item) for item in payload["identity_keys"]]
        signer = PersistedSigningKey(**payload["rare_signer_key"])
        return PersistedKeyRing(
            active_identity_kid=str(payload["active_identity_kid"]),
            identity_keys=identity_keys,
            rare_signer_key=signer,
        )

    def load_or_create(self) -> PersistedKeyRing:
        if self.path.exists():
            return self._read()
        keyring = _build_new_keyring()
        self._write(keyring)
        return keyring

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "file", "path": str(self.path)}


class GcpSecretManagerKeyProvider:
    """
    Production-reserved key provider.

    Stores the Rare keyring JSON in a single Secret Manager secret. The first writer creates
    the secret with automatic replication and adds an initial version.
    """

    def __init__(
        self,
        *,
        secret_name: str,
        project_id: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not secret_name.strip():
            raise ValueError("secret_name is required")
        self.secret_name = secret_name.strip()
        self.project_id = project_id.strip() if isinstance(project_id, str) and project_id.strip() else None
        self._client = client

    def load_or_create(self) -> PersistedKeyRing:
        client = self._get_client()
        secret_path = self._secret_path(client=client)
        payload = self._read_latest_payload(client=client, secret_path=secret_path)
        if payload is not None:
            return self._payload_to_keyring(payload)

        keyring = _build_new_keyring()
        encoded = self._keyring_to_payload(keyring)
        self._ensure_secret(client=client, secret_path=secret_path)
        self._add_version(client=client, secret_path=secret_path, payload=encoded)
        return keyring

    def readiness(self) -> dict[str, Any]:
        client = self._get_client()
        secret_path = self._secret_path(client=client)
        self._ensure_secret(client=client, secret_path=secret_path, create_if_missing=False)
        return {"status": "ok", "backend": "gcp_secret_manager", "secret": secret_path}

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from google.cloud import secretmanager  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("google-cloud-secret-manager is required for GcpSecretManagerKeyProvider") from exc
        self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def _resolve_project_id(self, *, client: Any) -> str:
        if self.project_id:
            return self.project_id
        if self.secret_name.startswith("projects/"):
            parts = self.secret_name.split("/")
            if len(parts) >= 2 and parts[1]:
                return parts[1]
        for env_name in ("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT", "GCLOUD_PROJECT"):
            value = os.getenv(env_name)
            if value and value.strip():
                return value.strip()
        raise RuntimeError("project_id is required when secret_name is not a full resource name")

    def _secret_path(self, *, client: Any) -> str:
        if self.secret_name.startswith("projects/"):
            return self.secret_name
        project_id = self._resolve_project_id(client=client)
        if hasattr(client, "secret_path"):
            return client.secret_path(project_id, self.secret_name)
        return f"projects/{project_id}/secrets/{self.secret_name}"

    def _ensure_secret(self, *, client: Any, secret_path: str, create_if_missing: bool = True) -> None:
        try:
            client.get_secret(request={"name": secret_path})
        except Exception as exc:  # noqa: BLE001
            if not create_if_missing or not self._is_not_found(exc):
                raise
            parent, _, secret_id = secret_path.rpartition("/secrets/")
            if not parent or not secret_id:
                raise RuntimeError(f"invalid Secret Manager secret path: {secret_path}") from exc
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )

    def _read_latest_payload(self, *, client: Any, secret_path: str) -> str | None:
        version_name = f"{secret_path}/versions/latest"
        try:
            response = client.access_secret_version(request={"name": version_name})
        except Exception as exc:  # noqa: BLE001
            if self._is_not_found(exc):
                return None
            raise
        payload = bytes(response.payload.data).decode("utf-8")
        return payload or None

    @staticmethod
    def _add_version(*, client: Any, secret_path: str, payload: str) -> None:
        client.add_secret_version(
            request={
                "parent": secret_path,
                "payload": {"data": payload.encode("utf-8")},
            }
        )

    @staticmethod
    def _keyring_to_payload(keyring: PersistedKeyRing) -> str:
        return json.dumps(
            {
                "active_identity_kid": keyring.active_identity_kid,
                "identity_keys": [asdict(item) for item in keyring.identity_keys],
                "rare_signer_key": asdict(keyring.rare_signer_key),
            },
            sort_keys=True,
            indent=2,
        )

    @staticmethod
    def _payload_to_keyring(payload: str) -> PersistedKeyRing:
        parsed = json.loads(payload)
        identity_keys = [PersistedSigningKey(**item) for item in parsed["identity_keys"]]
        signer = PersistedSigningKey(**parsed["rare_signer_key"])
        return PersistedKeyRing(
            active_identity_kid=str(parsed["active_identity_kid"]),
            identity_keys=identity_keys,
            rare_signer_key=signer,
        )

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        code = getattr(exc, "code", None)
        if callable(code):
            try:
                value = code()
            except Exception:  # noqa: BLE001
                value = None
            if str(value) in {"404", "StatusCode.NOT_FOUND"}:
                return True
        return exc.__class__.__name__ in {"NotFound", "ResourceNotFound"}
