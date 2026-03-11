from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

from rare_api.key_provider import FileKeyProvider, KeyProvider
from rare_api.integrations import (
    EmailProvider,
    HostedKeyCipher,
    JwsSigner,
    LocalEd25519JwsSigner,
    NoopEmailProvider,
    PlaintextHostedKeyCipher,
    SocialProviderAdapter,
    default_social_provider_adapters,
)
from rare_api.state_store import InMemoryStateStore, SnapshotCapableStateStore, StateStore
from rare_identity_protocol import (
    TokenValidationError,
    ResourceLimitError,
    ExpiringMap,
    ExpiringSet,
    b64url_encode,
    json_dumps_compact,
    build_action_payload,
    build_agent_auth_payload,
    build_auth_challenge_payload,
    build_full_attestation_issue_payload,
    build_register_payload,
    build_set_name_payload,
    build_upgrade_request_payload,
    decode_jws,
    generate_ed25519_keypair,
    generate_nonce,
    load_private_key,
    load_public_key,
    now_ts,
    public_key_to_b64,
    sign_detached,
    validate_name,
    verify_detached,
    verify_jws,
)
from rare_identity_protocol.tokens import build_identity_payload


LEVELS = {"L0", "L1", "L2"}
NEGATIVE_EVENT_CATEGORIES = {"spam", "fraud", "abuse", "policy_violation"}
SOCIAL_PROVIDERS = {"x", "github", "linkedin"}
MAX_SIGNED_TTL_SECONDS = 300
MAX_DELEGATION_TTL_SECONDS = 3600
DEFAULT_REPLAY_CACHE_CAPACITY = 50_000
DEFAULT_SESSION_CACHE_CAPACITY = 20_000
DEFAULT_CHALLENGE_CACHE_CAPACITY = 10_000
DEFAULT_HOSTED_MANAGEMENT_TOKEN_TTL_SECONDS = 30 * 24 * 3600
DEFAULT_MAX_AGENT_RECORDS = 100_000
DEFAULT_MAX_UPGRADE_REQUESTS = 100_000
DEFAULT_MAX_PLATFORM_RECORDS = 20_000
DEFAULT_MAX_PLATFORM_EVENTS = 200_000
DEFAULT_MAX_IDENTITY_PROFILES = 100_000
DEFAULT_MAX_IDENTITY_SUBSCRIPTIONS = 10_000
DEFAULT_UPGRADE_REQUEST_RETENTION_SECONDS = 7 * 24 * 3600
DEFAULT_PLATFORM_EVENT_RETENTION_SECONDS = 30 * 24 * 3600
DEFAULT_PUBLIC_WRITE_RATE_LIMIT_PER_MINUTE = 120
DEFAULT_PUBLIC_RATE_COUNTER_CAPACITY = 20_000


@dataclass
class AgentRecord:
    agent_id: str
    name: str
    level: str = "L0"
    owner_id: str | None = None
    recovery_email_masked: str | None = None
    recovery_email_ciphertext: str | None = None
    org_id: str | None = None
    social_accounts: dict[str, dict[str, Any]] = field(default_factory=dict)
    twitter: dict[str, str] | None = None
    github: dict[str, str] | None = None
    linkedin: dict[str, str] | None = None
    key_mode: str = "hosted-signer"
    status: str = "active"
    created_at: int = field(default_factory=now_ts)
    name_updated_at: int = field(default_factory=now_ts)


@dataclass
class SigningKey:
    kid: str
    private_key: Ed25519PrivateKey
    created_at: int
    retire_at: int


@dataclass
class HostedSessionRecord:
    session_pubkey: str
    agent_id: str
    aud: str
    private_key: Ed25519PrivateKey
    created_at: int
    expires_at: int


@dataclass
class HostedManagementTokenRecord:
    token_hash: str
    issued_at: int
    expires_at: int
    revoked_at: int | None = None
    version: int = 1


@dataclass
class IdentityProfileRecord:
    agent_id: str
    risk_score: float = 0.0
    labels: list[str] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: int = field(default_factory=now_ts)
    version: int = 1


@dataclass
class PlatformKeyRecord:
    kid: str
    public_key_b64: str
    status: str = "active"
    created_at: int = field(default_factory=now_ts)


@dataclass
class PlatformRecord:
    platform_id: str
    platform_aud: str
    domain: str
    status: str = "active"
    keys: dict[str, PlatformKeyRecord] = field(default_factory=dict)
    created_at: int = field(default_factory=now_ts)
    updated_at: int = field(default_factory=now_ts)


@dataclass
class PlatformRegisterChallenge:
    challenge_id: str
    platform_aud: str
    domain: str
    txt_name: str
    txt_value: str
    expires_at: int
    status: str = "issued"
    created_at: int = field(default_factory=now_ts)


@dataclass
class PlatformNegativeEvent:
    platform_id: str
    platform_aud: str
    event_id: str
    agent_id: str
    category: str
    severity: int
    outcome: str
    occurred_at: int
    evidence_hash: str | None
    ingested_at: int = field(default_factory=now_ts)


@dataclass
class UpgradeRequestRecord:
    upgrade_request_id: str
    agent_id: str
    target_level: str
    status: str
    requested_at: int
    expires_at: int
    contact_email_hash: str | None = None
    contact_email_masked: str | None = None
    contact_email_ciphertext: str | None = None
    email_verified_at: int | None = None
    social_provider: str | None = None
    social_verified_at: int | None = None
    social_account: dict[str, Any] | None = None
    email_delivery_state: str = "not_requested"
    email_delivery_provider: str | None = None
    email_delivery_attempt_count: int = 0
    email_delivery_last_attempt_at: int | None = None
    email_delivery_last_error_code: str | None = None
    email_delivery_last_error_detail: str | None = None
    failure_reason: str | None = None
    last_transition_at: int = field(default_factory=now_ts)


@dataclass
class UpgradeMagicLinkRecord:
    token_hash: str
    upgrade_request_id: str
    expires_at: int
    used_at: int | None = None
    created_at: int = field(default_factory=now_ts)


@dataclass
class UpgradeOAuthStateRecord:
    state: str
    upgrade_request_id: str
    provider: str
    expires_at: int
    used_at: int | None = None
    created_at: int = field(default_factory=now_ts)


@dataclass
class ManagementRecoveryEmailLinkRecord:
    token_hash: str
    agent_id: str
    expires_at: int
    used_at: int | None = None
    created_at: int = field(default_factory=now_ts)


@dataclass
class ManagementRecoveryOAuthStateRecord:
    state: str
    agent_id: str
    provider: str
    expires_at: int
    used_at: int | None = None
    created_at: int = field(default_factory=now_ts)


@dataclass
class AuditEventRecord:
    event_id: str
    actor_type: str
    actor_id: str | None
    agent_id: str | None
    event_type: str
    resource_type: str
    resource_id: str
    status: str
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=now_ts)


class RareService:
    def __init__(
        self,
        *,
        issuer: str = "rare",
        attestation_ttl_seconds: int = 86400,
        platform_register_challenge_ttl_seconds: int = 600,
        upgrade_request_ttl_seconds: int = 24 * 3600,
        magic_link_ttl_seconds: int = 600,
        oauth_state_ttl_seconds: int = 600,
        dns_txt_resolver: Callable[[str], list[str]] | None = None,
        max_signed_ttl_seconds: int = MAX_SIGNED_TTL_SECONDS,
        max_delegation_ttl_seconds: int = MAX_DELEGATION_TTL_SECONDS,
        replay_cache_capacity: int = DEFAULT_REPLAY_CACHE_CAPACITY,
        session_cache_capacity: int = DEFAULT_SESSION_CACHE_CAPACITY,
        challenge_cache_capacity: int = DEFAULT_CHALLENGE_CACHE_CAPACITY,
        hosted_management_token_ttl_seconds: int = DEFAULT_HOSTED_MANAGEMENT_TOKEN_TTL_SECONDS,
        max_agent_records: int = DEFAULT_MAX_AGENT_RECORDS,
        max_upgrade_requests: int = DEFAULT_MAX_UPGRADE_REQUESTS,
        max_platform_records: int = DEFAULT_MAX_PLATFORM_RECORDS,
        max_platform_events: int = DEFAULT_MAX_PLATFORM_EVENTS,
        max_identity_profiles: int = DEFAULT_MAX_IDENTITY_PROFILES,
        max_identity_subscriptions: int = DEFAULT_MAX_IDENTITY_SUBSCRIPTIONS,
        upgrade_request_retention_seconds: int = DEFAULT_UPGRADE_REQUEST_RETENTION_SECONDS,
        platform_event_retention_seconds: int = DEFAULT_PLATFORM_EVENT_RETENTION_SECONDS,
        public_write_rate_limit_per_minute: int = DEFAULT_PUBLIC_WRITE_RATE_LIMIT_PER_MINUTE,
        public_rate_counter_capacity: int = DEFAULT_PUBLIC_RATE_COUNTER_CAPACITY,
        allow_local_upgrade_shortcuts: bool = False,
        public_base_url: str | None = None,
        admin_token: str | None = None,
        key_provider: KeyProvider | None = None,
        state_store: StateStore | None = None,
        email_provider: EmailProvider | None = None,
        hosted_key_cipher: HostedKeyCipher | None = None,
        social_provider_adapters: dict[str, SocialProviderAdapter] | None = None,
        identity_jws_signer: JwsSigner | None = None,
        rare_delegation_signer: JwsSigner | None = None,
    ) -> None:
        self.issuer = issuer
        self.attestation_ttl_seconds = attestation_ttl_seconds
        self.platform_register_challenge_ttl_seconds = platform_register_challenge_ttl_seconds
        self.upgrade_request_ttl_seconds = upgrade_request_ttl_seconds
        self.magic_link_ttl_seconds = magic_link_ttl_seconds
        self.oauth_state_ttl_seconds = oauth_state_ttl_seconds
        self.max_signed_ttl_seconds = max_signed_ttl_seconds
        self.max_delegation_ttl_seconds = max_delegation_ttl_seconds
        if hosted_management_token_ttl_seconds <= 0:
            raise ValueError("hosted_management_token_ttl_seconds must be greater than 0")
        self.hosted_management_token_ttl_seconds = hosted_management_token_ttl_seconds
        if max_agent_records <= 0:
            raise ValueError("max_agent_records must be greater than 0")
        if max_upgrade_requests <= 0:
            raise ValueError("max_upgrade_requests must be greater than 0")
        if max_platform_records <= 0:
            raise ValueError("max_platform_records must be greater than 0")
        if max_platform_events <= 0:
            raise ValueError("max_platform_events must be greater than 0")
        if max_identity_profiles <= 0:
            raise ValueError("max_identity_profiles must be greater than 0")
        if max_identity_subscriptions <= 0:
            raise ValueError("max_identity_subscriptions must be greater than 0")
        if upgrade_request_retention_seconds <= 0:
            raise ValueError("upgrade_request_retention_seconds must be greater than 0")
        if platform_event_retention_seconds <= 0:
            raise ValueError("platform_event_retention_seconds must be greater than 0")
        if public_write_rate_limit_per_minute <= 0:
            raise ValueError("public_write_rate_limit_per_minute must be greater than 0")
        if public_rate_counter_capacity <= 0:
            raise ValueError("public_rate_counter_capacity must be greater than 0")
        self.max_agent_records = max_agent_records
        self.max_upgrade_requests = max_upgrade_requests
        self.max_platform_records = max_platform_records
        self.max_platform_events = max_platform_events
        self.max_identity_profiles = max_identity_profiles
        self.max_identity_subscriptions = max_identity_subscriptions
        self.upgrade_request_retention_seconds = upgrade_request_retention_seconds
        self.platform_event_retention_seconds = platform_event_retention_seconds
        self.public_write_rate_limit_per_minute = public_write_rate_limit_per_minute
        self.allow_local_upgrade_shortcuts = allow_local_upgrade_shortcuts
        self.public_base_url = self._normalize_public_base_url(public_base_url)
        self.dns_txt_resolver = dns_txt_resolver or (lambda _name: [])
        self._admin_token = admin_token
        self.email_provider = email_provider or NoopEmailProvider()
        self.hosted_key_cipher = hosted_key_cipher or PlaintextHostedKeyCipher()
        self.social_provider_adapters = social_provider_adapters or default_social_provider_adapters()
        self.enabled_social_providers = set(self.social_provider_adapters)

        self._state_store = state_store or InMemoryStateStore()
        handles = self._state_store.open(
            replay_cache_capacity=replay_cache_capacity,
            session_cache_capacity=session_cache_capacity,
            challenge_cache_capacity=challenge_cache_capacity,
            public_rate_counter_capacity=public_rate_counter_capacity,
        )
        self.agents = handles.agents
        self.hosted_agent_private_keys = handles.hosted_agent_private_keys
        self.hosted_management_tokens = handles.hosted_management_tokens
        self.hosted_session_keys = handles.hosted_session_keys
        self.public_write_counters = handles.public_write_counters
        self.name_change_events = handles.name_change_events
        self.used_name_nonces = handles.used_name_nonces
        self.used_action_nonces = handles.used_action_nonces
        self.used_agent_auth_nonces = handles.used_agent_auth_nonces
        self.used_full_issue_nonces = handles.used_full_issue_nonces
        self.seen_upgrade_nonces = handles.seen_upgrade_nonces
        self.identity_profiles = handles.identity_profiles
        self.identity_subscriptions = handles.identity_subscriptions
        self.platforms = handles.platforms
        self.platform_register_challenges = handles.platform_register_challenges
        self.platform_events = handles.platform_events
        self.seen_platform_jtis = handles.seen_platform_jtis
        self.upgrade_requests = handles.upgrade_requests
        self.upgrade_magic_links = handles.upgrade_magic_links
        self.upgrade_oauth_states = handles.upgrade_oauth_states
        self.management_recovery_email_links = handles.management_recovery_email_links
        self.management_recovery_oauth_states = handles.management_recovery_oauth_states
        self.audit_events: list[AuditEventRecord] = []
        self._snapshot_revision: int | None = None

        self._key_provider = key_provider or self._default_key_provider()
        keyring = self._key_provider.load_or_create()
        self.identity_keys = {
            item.kid: SigningKey(
                kid=item.kid,
                private_key=load_private_key(item.private_key),
                created_at=item.created_at,
                retire_at=item.retire_at,
            )
            for item in keyring.identity_keys
        }
        if not self.identity_keys:
            raise ValueError("key provider returned no identity keys")
        self.active_identity_kid = keyring.active_identity_kid
        if self.active_identity_kid not in self.identity_keys:
            raise ValueError("active identity kid is missing from keyring")
        signer_key = keyring.rare_signer_key
        self.rare_signer_key = SigningKey(
            kid=signer_key.kid,
            private_key=load_private_key(signer_key.private_key),
            created_at=signer_key.created_at,
            retire_at=signer_key.retire_at,
        )
        self.identity_jws_signer = identity_jws_signer or LocalEd25519JwsSigner(
            kid=self.active_identity_kid,
            private_key=self.identity_keys[self.active_identity_kid].private_key,
        )
        self.rare_delegation_signer = rare_delegation_signer or LocalEd25519JwsSigner(
            kid=self.rare_signer_key.kid,
            private_key=self.rare_signer_key.private_key,
        )
        self._load_persisted_snapshot(force=True, include_ephemeral=True)

    @staticmethod
    def _default_key_provider() -> KeyProvider:
        provider = Path.home() / ".config" / "rare" / "keyring.json"
        return FileKeyProvider(path=provider)

    @staticmethod
    def _normalize_public_base_url(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        return normalized or None

    def _build_public_url(self, path: str, *, query: dict[str, Any] | None = None) -> str:
        if not self.public_base_url:
            raise RuntimeError("public_base_url is not configured")
        query_string = f"?{urlencode(query, doseq=True)}" if query else ""
        return f"{self.public_base_url}{path}{query_string}"

    def _build_email_verify_url(self, *, token: str) -> str:
        if self.public_base_url:
            return self._build_public_url("/v1/upgrades/l1/email/verify", query={"token": token})
        return "https://rare.local/v1/upgrades/l1/email/verify"

    def _build_management_recovery_email_verify_url(self, *, token: str) -> str:
        if self.public_base_url:
            return self._build_public_url("/v1/signer/recovery/email/verify", query={"token": token})
        return "https://rare.local/v1/signer/recovery/email/verify"

    def _build_social_callback_url(self, *, provider: str) -> str:
        if self.public_base_url:
            return self._build_public_url("/v1/upgrades/l2/social/callback", query={"provider": provider})
        return f"https://oauth.{provider}.local/callback"

    @staticmethod
    def _private_key_to_b64(private_key: Ed25519PrivateKey) -> str:
        return b64url_encode(
            private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    @staticmethod
    def _encode_key(key: Any) -> str:
        return json.dumps(key, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode_key(key: str) -> Any:
        decoded = json.loads(key)
        if isinstance(decoded, list):
            return tuple(decoded)
        return decoded

    @staticmethod
    def _serialize_expiring_map(
        value: ExpiringMap[Any, Any],
        *,
        value_serializer: Callable[[Any], Any] | None = None,
    ) -> list[dict[str, Any]]:
        serializer = value_serializer or (lambda item: item)
        payload: list[dict[str, Any]] = []
        if hasattr(value, "snapshot_entries"):
            for key, item, expires_at in value.snapshot_entries():  # type: ignore[attr-defined]
                payload.append(
                    {
                        "key": RareService._encode_key(key),
                        "value": serializer(item),
                        "expires_at": expires_at,
                    }
                )
            return payload
        for key, entry in value._entries.items():  # type: ignore[attr-defined]
            payload.append(
                {
                    "key": RareService._encode_key(key),
                    "value": serializer(entry.value),
                    "expires_at": entry.expires_at,
                }
            )
        return payload

    @staticmethod
    def _serialize_expiring_set(value: ExpiringSet[Any]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        if hasattr(value, "snapshot_entries"):
            for key, expires_at in value.snapshot_entries():  # type: ignore[attr-defined]
                payload.append({"key": RareService._encode_key(key), "expires_at": expires_at})
            return payload
        for key, entry in value._store._entries.items():  # type: ignore[attr-defined]
            payload.append({"key": RareService._encode_key(key), "expires_at": entry.expires_at})
        return payload

    @staticmethod
    def _load_expiring_map(
        target: ExpiringMap[Any, Any],
        items: list[dict[str, Any]],
        *,
        value_loader: Callable[[Any], Any] | None = None,
    ) -> None:
        loader = value_loader or (lambda item: item)
        for item in items:
            target.set(
                key=RareService._decode_key(str(item["key"])),
                value=loader(item["value"]),
                expires_at=int(item["expires_at"]),
                now=0,
                grace_seconds=0,
            )

    @staticmethod
    def _load_expiring_set(target: ExpiringSet[Any], items: list[dict[str, Any]]) -> None:
        for item in items:
            target.add(
                key=RareService._decode_key(str(item["key"])),
                expires_at=int(item["expires_at"]),
                now=0,
                grace_seconds=0,
            )

    def _serialize_snapshot(self) -> dict[str, Any]:
        return {
            "agents": {agent_id: asdict(record) for agent_id, record in self.agents.items()},
            "hosted_agent_private_keys": {
                agent_id: self.hosted_key_cipher.encrypt_text(self._private_key_to_b64(private_key))
                for agent_id, private_key in self.hosted_agent_private_keys.items()
            },
            "hosted_management_tokens": {
                agent_id: asdict(record) for agent_id, record in self.hosted_management_tokens.items()
            },
            "name_change_events": self.name_change_events,
            "identity_profiles": {agent_id: asdict(record) for agent_id, record in self.identity_profiles.items()},
            "identity_subscriptions": self.identity_subscriptions,
            "platforms": {platform_aud: asdict(record) for platform_aud, record in self.platforms.items()},
            "platform_events": {
                self._encode_key(event_key): asdict(record) for event_key, record in self.platform_events.items()
            },
            "platform_register_challenges": self._serialize_expiring_map(
                self.platform_register_challenges,
                value_serializer=asdict,
            ),
            "public_write_counters": self._serialize_expiring_map(self.public_write_counters),
            "used_name_nonces": self._serialize_expiring_set(self.used_name_nonces),
            "used_action_nonces": self._serialize_expiring_set(self.used_action_nonces),
            "used_agent_auth_nonces": self._serialize_expiring_set(self.used_agent_auth_nonces),
            "used_full_issue_nonces": self._serialize_expiring_set(self.used_full_issue_nonces),
            "seen_upgrade_nonces": self._serialize_expiring_set(self.seen_upgrade_nonces),
            "seen_platform_jtis": self._serialize_expiring_set(self.seen_platform_jtis),
            "hosted_session_keys": self._serialize_expiring_map(
                self.hosted_session_keys,
                value_serializer=lambda item: {
                    "session_pubkey": item.session_pubkey,
                    "agent_id": item.agent_id,
                    "aud": item.aud,
                    "private_key_ciphertext": self.hosted_key_cipher.encrypt_text(
                        self._private_key_to_b64(item.private_key)
                    ),
                    "created_at": item.created_at,
                    "expires_at": item.expires_at,
                },
            ),
            "upgrade_requests": {
                request_id: asdict(record) for request_id, record in self.upgrade_requests.items()
            },
            "upgrade_magic_links": self._serialize_expiring_map(
                self.upgrade_magic_links,
                value_serializer=asdict,
            ),
            "upgrade_oauth_states": self._serialize_expiring_map(
                self.upgrade_oauth_states,
                value_serializer=asdict,
            ),
            "management_recovery_email_links": self._serialize_expiring_map(
                self.management_recovery_email_links,
                value_serializer=asdict,
            ),
            "management_recovery_oauth_states": self._serialize_expiring_map(
                self.management_recovery_oauth_states,
                value_serializer=asdict,
            ),
            "audit_events": [asdict(record) for record in self.audit_events],
        }

    def _load_persisted_snapshot(self, *, force: bool = False, include_ephemeral: bool = False) -> None:
        snapshot_store = self._get_snapshot_store()
        if snapshot_store is None:
            return
        revision = snapshot_store.snapshot_revision()
        if not force and revision == self._snapshot_revision:
            return
        snapshot = snapshot_store.load_snapshot()
        if not snapshot:
            return
        self.agents.clear()
        self.hosted_agent_private_keys.clear()
        self.hosted_management_tokens.clear()
        self.name_change_events.clear()
        self.identity_profiles.clear()
        self.identity_subscriptions.clear()
        self.platforms.clear()
        self.platform_events.clear()
        self.upgrade_requests.clear()
        self.agents.update(
            {agent_id: AgentRecord(**record) for agent_id, record in snapshot.get("agents", {}).items()}
        )
        self.hosted_agent_private_keys.update(
            {
                agent_id: load_private_key(self.hosted_key_cipher.decrypt_text(ciphertext))
                for agent_id, ciphertext in snapshot.get("hosted_agent_private_keys", {}).items()
            }
        )
        self.hosted_management_tokens.update(
            {
                agent_id: HostedManagementTokenRecord(**record)
                for agent_id, record in snapshot.get("hosted_management_tokens", {}).items()
            }
        )
        self.name_change_events.update(
            {str(agent_id): [int(item) for item in timestamps] for agent_id, timestamps in snapshot.get("name_change_events", {}).items()}
        )
        self.identity_profiles.update(
            {
                agent_id: IdentityProfileRecord(**record)
                for agent_id, record in snapshot.get("identity_profiles", {}).items()
            }
        )
        self.identity_subscriptions.update(snapshot.get("identity_subscriptions", {}))
        for platform_aud, record in snapshot.get("platforms", {}).items():
            keys = {kid: PlatformKeyRecord(**value) for kid, value in record.get("keys", {}).items()}
            self.platforms[platform_aud] = PlatformRecord(
                platform_id=record["platform_id"],
                platform_aud=record["platform_aud"],
                domain=record["domain"],
                status=record.get("status", "active"),
                keys=keys,
                created_at=record.get("created_at", now_ts()),
                updated_at=record.get("updated_at", now_ts()),
            )
        self.platform_events.update(
            {
                self._decode_key(event_key): PlatformNegativeEvent(**record)
                for event_key, record in snapshot.get("platform_events", {}).items()
            }
        )
        if include_ephemeral:
            self._load_expiring_map(
                self.platform_register_challenges,
                snapshot.get("platform_register_challenges", []),
                value_loader=lambda value: PlatformRegisterChallenge(**value),
            )
            self._load_expiring_map(self.public_write_counters, snapshot.get("public_write_counters", []))
            self._load_expiring_set(self.used_name_nonces, snapshot.get("used_name_nonces", []))
            self._load_expiring_set(self.used_action_nonces, snapshot.get("used_action_nonces", []))
            self._load_expiring_set(self.used_agent_auth_nonces, snapshot.get("used_agent_auth_nonces", []))
            self._load_expiring_set(self.used_full_issue_nonces, snapshot.get("used_full_issue_nonces", []))
            self._load_expiring_set(self.seen_upgrade_nonces, snapshot.get("seen_upgrade_nonces", []))
            self._load_expiring_set(self.seen_platform_jtis, snapshot.get("seen_platform_jtis", []))
            self._load_expiring_map(
                self.hosted_session_keys,
                snapshot.get("hosted_session_keys", []),
                value_loader=lambda value: HostedSessionRecord(
                    session_pubkey=value["session_pubkey"],
                    agent_id=value["agent_id"],
                    aud=value["aud"],
                    private_key=load_private_key(
                        self.hosted_key_cipher.decrypt_text(value["private_key_ciphertext"])
                    ),
                    created_at=value["created_at"],
                    expires_at=value["expires_at"],
                ),
            )
        self.upgrade_requests.update(
            {
                request_id: UpgradeRequestRecord(**record)
                for request_id, record in snapshot.get("upgrade_requests", {}).items()
            }
        )
        if include_ephemeral:
            self._load_expiring_map(
                self.upgrade_magic_links,
                snapshot.get("upgrade_magic_links", []),
                value_loader=lambda value: UpgradeMagicLinkRecord(**value),
            )
            self._load_expiring_map(
                self.upgrade_oauth_states,
                snapshot.get("upgrade_oauth_states", []),
                value_loader=lambda value: UpgradeOAuthStateRecord(**value),
            )
            self._load_expiring_map(
                self.management_recovery_email_links,
                snapshot.get("management_recovery_email_links", []),
                value_loader=lambda value: ManagementRecoveryEmailLinkRecord(**value),
            )
            self._load_expiring_map(
                self.management_recovery_oauth_states,
                snapshot.get("management_recovery_oauth_states", []),
                value_loader=lambda value: ManagementRecoveryOAuthStateRecord(**value),
            )
        self.audit_events = [AuditEventRecord(**record) for record in snapshot.get("audit_events", [])]
        self._snapshot_revision = revision

    def _persist_state(self) -> None:
        snapshot_store = self._get_snapshot_store()
        if snapshot_store is not None:
            snapshot_store.save_snapshot(self._serialize_snapshot())
            self._snapshot_revision = snapshot_store.snapshot_revision()

    def _get_snapshot_store(self) -> SnapshotCapableStateStore | None:
        if hasattr(self._state_store, "load_snapshot") and hasattr(self._state_store, "save_snapshot"):
            return self._state_store  # type: ignore[return-value]
        return None

    def _append_audit_event(
        self,
        *,
        actor_type: str,
        actor_id: str | None,
        agent_id: str | None,
        event_type: str,
        resource_type: str,
        resource_id: str,
        status: str = "success",
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        self.audit_events.append(
            AuditEventRecord(
                event_id=generate_nonce(12),
                actor_type=actor_type,
                actor_id=actor_id,
                agent_id=agent_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                request_id=request_id,
                metadata=metadata or {},
            )
        )
        self._persist_state()

    def _sync_state(self) -> None:
        self._load_persisted_snapshot()

    def _generate_identity_signing_key(self) -> str:
        private_b64, _ = generate_ed25519_keypair()
        kid = f"rare-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(4)}"
        created_at = now_ts()
        self.identity_keys[kid] = SigningKey(
            kid=kid,
            private_key=load_private_key(private_b64),
            created_at=created_at,
            retire_at=created_at + 365 * 24 * 3600,
        )
        return kid

    @staticmethod
    def _sign_compact_jws(*, payload: dict[str, Any], signer: JwsSigner, typ: str) -> str:
        header = {"alg": "EdDSA", "kid": signer.kid, "typ": typ}
        encoded_header = b64url_encode(json_dumps_compact(header))
        encoded_payload = b64url_encode(json_dumps_compact(payload))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = b64url_encode(signer.sign_bytes(signing_input))
        return f"{encoded_header}.{encoded_payload}.{signature}"

    def _issue_rare_delegation_token(
        self,
        *,
        agent_id: str,
        session_pubkey: str,
        aud: str,
        scope: Iterable[str],
        ttl_seconds: int,
        jti: str,
    ) -> str:
        iat = now_ts()
        payload = {
            "typ": "rare.delegation",
            "ver": 1,
            "iss": "rare-signer",
            "agent_id": agent_id,
            "session_pubkey": session_pubkey,
            "aud": aud,
            "scope": list(scope),
            "iat": iat,
            "exp": iat + ttl_seconds,
            "act": "delegated_by_rare",
            "jti": jti,
        }
        return self._sign_compact_jws(
            payload=payload,
            signer=self.rare_delegation_signer,
            typ="rare.delegation+jws",
        )

    def get_jwks(self) -> dict:
        return {
            "issuer": self.issuer,
            "keys": [
                {
                    "kid": self.identity_jws_signer.kid,
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": public_key_to_b64(self.identity_jws_signer.public_key()),
                    "retire_at": self.identity_keys.get(self.active_identity_kid, self.rare_signer_key).retire_at,
                }
            ],
        }

    def get_identity_public_key(self, kid: str) -> Ed25519PublicKey | None:
        if kid == self.identity_jws_signer.kid:
            return self.identity_jws_signer.public_key()
        key = self.identity_keys.get(kid)
        return key.private_key.public_key() if key else None

    def get_rare_signer_public_key(self) -> Ed25519PublicKey:
        return self.rare_delegation_signer.public_key()

    def health_report(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "issuer": self.issuer,
            "public_base_url": self.public_base_url,
            "enabled_social_providers": sorted(self.enabled_social_providers),
        }

    def readiness_report(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}

        if hasattr(self._state_store, "readiness"):
            checks["state_store"] = self._state_store.readiness()  # type: ignore[assignment]
        else:
            checks["state_store"] = {"status": "ok", "backend": self._state_store.__class__.__name__}

        if hasattr(self._key_provider, "readiness"):
            checks["key_provider"] = self._key_provider.readiness()  # type: ignore[assignment]
        else:
            checks["key_provider"] = {"status": "ok", "backend": self._key_provider.__class__.__name__}

        if hasattr(self.email_provider, "readiness"):
            checks["email_provider"] = self.email_provider.readiness()  # type: ignore[assignment]
        else:
            checks["email_provider"] = {"status": "ok", "backend": self.email_provider.__class__.__name__}

        if hasattr(self.hosted_key_cipher, "readiness"):
            checks["hosted_key_cipher"] = self.hosted_key_cipher.readiness()  # type: ignore[assignment]
        else:
            checks["hosted_key_cipher"] = {"status": "ok", "backend": self.hosted_key_cipher.__class__.__name__}

        checks["identity_signer"] = self.identity_jws_signer.readiness()
        checks["rare_signer"] = self.rare_delegation_signer.readiness()
        checks["social_providers"] = {
            provider: adapter.readiness() for provider, adapter in self.social_provider_adapters.items()
        }

        overall = "ok"
        for value in checks.values():
            if isinstance(value, dict) and value.get("status") not in {None, "ok"}:
                overall = "error"
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, dict) and nested.get("status") not in {None, "ok"}:
                        overall = "error"
        return {"status": overall, "checks": checks}

    def _issue_public_identity_attestation(self, record: AgentRecord) -> str:
        iat = now_ts()
        exp = iat + self.attestation_ttl_seconds
        public_level = record.level if record.level in {"L0", "L1"} else "L1"
        payload = build_identity_payload(
            agent_id=record.agent_id,
            level=public_level,
            name=record.name,
            iat=iat,
            exp=exp,
            jti=generate_nonce(12),
            include_extended_claims=False,
            name_updated_at=record.name_updated_at,
        )
        return self._sign_compact_jws(
            payload=payload,
            signer=self.identity_jws_signer,
            typ="rare.identity.public+jws",
        )

    def _issue_full_identity_attestation(self, record: AgentRecord, *, aud: str) -> str:
        iat = now_ts()
        payload = build_identity_payload(
            agent_id=record.agent_id,
            level=record.level,
            name=record.name,
            aud=aud,
            iat=iat,
            exp=iat + self.attestation_ttl_seconds,
            jti=generate_nonce(12),
            include_extended_claims=True,
            name_updated_at=record.name_updated_at,
            owner_id=record.owner_id,
            org_id=record.org_id,
            twitter=record.twitter,
            github=record.github,
            linkedin=record.linkedin,
        )
        return self._sign_compact_jws(
            payload=payload,
            signer=self.identity_jws_signer,
            typ="rare.identity.full+jws",
        )

    def _ensure_identity_profile(self, agent_id: str) -> IdentityProfileRecord:
        profile = self.identity_profiles.get(agent_id)
        if profile is None:
            self._ensure_capacity(
                self.identity_profiles,
                key=agent_id,
                max_items=self.max_identity_profiles,
                resource_name="identity profile",
            )
            profile = IdentityProfileRecord(agent_id=agent_id)
            self.identity_profiles[agent_id] = profile
        return profile

    @staticmethod
    def _ensure_capacity(
        mapping: dict[Any, Any],
        *,
        key: Any,
        max_items: int,
        resource_name: str,
    ) -> None:
        if key in mapping:
            return
        if len(mapping) >= max_items:
            raise ResourceLimitError(f"{resource_name} capacity exceeded")

    def enforce_public_write_limit(self, *, operation: str, client_id: str) -> None:
        now = now_ts()
        self.public_write_counters.cleanup(now=now)
        counter_key = (operation, client_id)
        current = self.public_write_counters.get(counter_key) or 0
        if current >= self.public_write_rate_limit_per_minute:
            raise ResourceLimitError(f"public write rate limit exceeded for {operation}")
        self.public_write_counters.set(
            key=counter_key,
            value=current + 1,
            expires_at=now + 60,
            now=now,
        )
        self._persist_state()

    def _profile_to_dict(self, profile: IdentityProfileRecord) -> dict[str, Any]:
        return {
            "agent_id": profile.agent_id,
            "risk_score": profile.risk_score,
            "labels": profile.labels,
            "summary": profile.summary,
            "metadata": profile.metadata,
            "updated_at": profile.updated_at,
            "version": profile.version,
        }

    def _agent_to_dict(self, record: AgentRecord) -> dict[str, Any]:
        hosted_token = self.hosted_management_tokens.get(record.agent_id)
        return {
            "agent_id": record.agent_id,
            "name": record.name,
            "level": record.level,
            "key_mode": record.key_mode,
            "status": record.status,
            "owner_id": record.owner_id,
            "recovery_email_masked": record.recovery_email_masked,
            "org_id": record.org_id,
            "social_accounts": record.social_accounts,
            "twitter": record.twitter,
            "github": record.github,
            "linkedin": record.linkedin,
            "created_at": record.created_at,
            "name_updated_at": record.name_updated_at,
            "profile": self._profile_to_dict(self._ensure_identity_profile(record.agent_id)),
            "hosted_management": (
                {
                    "issued_at": hosted_token.issued_at,
                    "expires_at": hosted_token.expires_at,
                    "revoked_at": hosted_token.revoked_at,
                    "version": hosted_token.version,
                }
                if hosted_token is not None
                else None
            ),
        }

    @staticmethod
    def _platform_to_dict(record: PlatformRecord) -> dict[str, Any]:
        return {
            "platform_id": record.platform_id,
            "platform_aud": record.platform_aud,
            "domain": record.domain,
            "status": record.status,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "keys": [asdict(item) for item in record.keys.values()],
        }

    def list_agents(self) -> list[dict[str, Any]]:
        self._sync_state()
        return [self._agent_to_dict(record) for record in sorted(self.agents.values(), key=lambda item: item.created_at)]

    def get_agent_details(self, *, agent_id: str) -> dict[str, Any]:
        self._sync_state()
        return self._agent_to_dict(self.require_agent(agent_id))

    def list_agent_audit_events(self, *, agent_id: str) -> list[dict[str, Any]]:
        self._sync_state()
        self.require_agent(agent_id)
        return [asdict(item) for item in self.audit_events if item.agent_id == agent_id]

    def get_admin_upgrade_request(self, *, upgrade_request_id: str) -> dict[str, Any]:
        self._sync_state()
        return self._upgrade_status_payload(self._require_upgrade_request(upgrade_request_id))

    def list_platforms(self) -> list[dict[str, Any]]:
        self._sync_state()
        return [self._platform_to_dict(record) for record in self.platforms.values()]

    def get_platform(self, *, platform_aud: str) -> dict[str, Any]:
        self._sync_state()
        record = self.platforms.get(platform_aud)
        if record is None:
            raise KeyError("platform not found")
        return self._platform_to_dict(record)

    def list_audit_events(self) -> list[dict[str, Any]]:
        self._sync_state()
        return [asdict(item) for item in self.audit_events]

    def get_identity_profile(self, *, agent_id: str) -> dict[str, Any]:
        self._sync_state()
        self.require_agent(agent_id)
        return self._profile_to_dict(self._ensure_identity_profile(agent_id))

    def upsert_identity_profile(self, *, agent_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        self._sync_state()
        self.require_agent(agent_id)
        profile = self._ensure_identity_profile(agent_id)

        if "risk_score" in patch:
            value = float(patch["risk_score"])
            if value < 0.0 or value > 1.0:
                raise TokenValidationError("risk_score must be between 0.0 and 1.0")
            profile.risk_score = value

        if "labels" in patch:
            labels = patch["labels"]
            if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
                raise TokenValidationError("labels must be string list")
            profile.labels = labels

        if "summary" in patch:
            summary = patch["summary"]
            if not isinstance(summary, str):
                raise TokenValidationError("summary must be string")
            profile.summary = summary

        if "metadata" in patch:
            metadata = patch["metadata"]
            if not isinstance(metadata, dict):
                raise TokenValidationError("metadata must be object")
            profile.metadata = metadata

        profile.version += 1
        profile.updated_at = now_ts()
        result = self._profile_to_dict(profile)
        self._append_audit_event(
            actor_type="admin",
            actor_id="admin",
            agent_id=agent_id,
            event_type="identity_profile_patch",
            resource_type="identity_profile",
            resource_id=agent_id,
            metadata={"patch_keys": sorted(patch.keys())},
        )
        return result

    def create_identity_subscription(
        self,
        *,
        name: str,
        webhook_url: str,
        fields: list[str],
        event_types: list[str],
    ) -> dict[str, Any]:
        self._sync_state()
        if not name.strip():
            raise TokenValidationError("subscription name cannot be empty")
        if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
            raise TokenValidationError("webhook_url must be http/https")

        subscription_id = generate_nonce(8)
        self._ensure_capacity(
            self.identity_subscriptions,
            key=subscription_id,
            max_items=self.max_identity_subscriptions,
            resource_name="identity subscription",
        )
        record = {
            "subscription_id": subscription_id,
            "name": name,
            "webhook_url": webhook_url,
            "fields": fields,
            "event_types": event_types,
            "created_at": now_ts(),
        }
        self.identity_subscriptions[subscription_id] = record
        self._append_audit_event(
            actor_type="admin",
            actor_id="admin",
            agent_id=None,
            event_type="identity_subscription_create",
            resource_type="identity_subscription",
            resource_id=subscription_id,
            metadata={"name": name},
        )
        return record

    def list_identity_subscriptions(self) -> list[dict[str, Any]]:
        self._sync_state()
        return list(self.identity_subscriptions.values())

    def self_register(
        self,
        *,
        name: str | None,
        key_mode: str,
        agent_public_key: str | None,
        nonce: str | None,
        issued_at: int | None,
        expires_at: int | None,
        signature_by_agent: str | None,
    ) -> dict:
        self._sync_state()
        normalized_name = validate_name(name) if name else f"Agent-{generate_nonce(5)[:8]}"
        hosted_management_token: str | None = None
        hosted_management_token_expires_at: int | None = None

        if key_mode == "hosted-signer":
            if agent_public_key is not None:
                raise TokenValidationError("agent_public_key is not allowed in hosted-signer mode")
            generated_private_key, generated_public_key = generate_ed25519_keypair()
            agent_id = generated_public_key
            self._ensure_capacity(
                self.hosted_agent_private_keys,
                key=agent_id,
                max_items=self.max_agent_records,
                resource_name="hosted signer key",
            )
            self.hosted_agent_private_keys[agent_id] = load_private_key(generated_private_key)
            hosted_management_token, hosted_management_token_expires_at = self._issue_hosted_management_token(
                agent_id=agent_id
            )
        elif key_mode == "self-hosted":
            if agent_public_key is None:
                raise TokenValidationError("agent_public_key is required in self-hosted mode")
            if nonce is None or issued_at is None or expires_at is None or signature_by_agent is None:
                raise TokenValidationError("self-hosted registration proof is required")

            load_public_key(agent_public_key)
            now = now_ts()
            self._validate_signed_window(
                issued_at=issued_at,
                expires_at=expires_at,
                now=now,
                prefix="registration",
            )

            registration_payload = build_register_payload(
                agent_id=agent_public_key,
                name=normalized_name,
                nonce=nonce,
                issued_at=issued_at,
                expires_at=expires_at,
            )
            verify_detached(
                registration_payload,
                signature_by_agent,
                load_public_key(agent_public_key),
            )
            agent_id = agent_public_key
        else:
            raise TokenValidationError("key_mode must be hosted-signer or self-hosted")

        existing = self.agents.get(agent_id)
        if existing is None:
            self._ensure_capacity(
                self.agents,
                key=agent_id,
                max_items=self.max_agent_records,
                resource_name="agent",
            )
            existing = AgentRecord(agent_id=agent_id, name=normalized_name, key_mode=key_mode)
            self.agents[agent_id] = existing
        else:
            existing.key_mode = key_mode

        self._ensure_identity_profile(existing.agent_id)

        attestation = self._issue_public_identity_attestation(existing)

        response = {
            "agent_id": existing.agent_id,
            "profile": {"name": existing.name},
            "public_identity_attestation": attestation,
            "key_mode": key_mode,
        }
        if hosted_management_token is not None:
            response["hosted_management_token"] = hosted_management_token
            response["hosted_management_token_expires_at"] = hosted_management_token_expires_at
        self._append_audit_event(
            actor_type="agent",
            actor_id=existing.agent_id,
            agent_id=existing.agent_id,
            event_type="self_register",
            resource_type="agent",
            resource_id=existing.agent_id,
            metadata={"key_mode": key_mode},
        )
        return response

    def issue_public_attestation(self, *, agent_id: str) -> dict:
        self._sync_state()
        record = self.require_agent(agent_id)
        return {
            "agent_id": record.agent_id,
            "profile": {"name": record.name},
            "public_identity_attestation": self._issue_public_identity_attestation(record),
        }

    def refresh_attestation(self, *, agent_id: str) -> dict:
        self._sync_state()
        return self.issue_public_attestation(agent_id=agent_id)

    @staticmethod
    def _sha256_hex(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _mask_email(email: str) -> str:
        local, _, domain = email.partition("@")
        if not local or not domain:
            raise TokenValidationError("invalid contact_email")
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + ("*" * (len(local) - 2)) + local[-1]
        return f"{masked_local}@{domain}"

    def _validate_contact_email(self, email: str) -> tuple[str, str, str]:
        normalized = self._normalize_email(email)
        local, sep, domain = normalized.partition("@")
        if not sep or not local or not domain or "." not in domain:
            raise TokenValidationError("invalid contact_email")
        if any(ch.isspace() for ch in normalized):
            raise TokenValidationError("invalid contact_email")
        return normalized, self._sha256_hex(normalized), self._mask_email(normalized)

    def _cleanup_upgrade_requests(self, now: int) -> None:
        delete_before = now - self.upgrade_request_retention_seconds
        for request_id, request in list(self.upgrade_requests.items()):
            if request.status in {"upgraded", "expired", "revoked"} and request.last_transition_at < delete_before:
                self.upgrade_requests.pop(request_id, None)
                continue
            if request.status in {"upgraded", "expired", "revoked"}:
                continue
            if request.expires_at + 30 < now:
                request.status = "expired"
                request.failure_reason = "upgrade request expired"
                request.last_transition_at = now

    def _cleanup_upgrade_magic_links(self, now: int) -> None:
        self.upgrade_magic_links.cleanup(now=now)

    def _cleanup_upgrade_oauth_states(self, now: int) -> None:
        self.upgrade_oauth_states.cleanup(now=now)

    def _cleanup_management_recovery_email_links(self, now: int) -> None:
        self.management_recovery_email_links.cleanup(now=now)

    def _cleanup_management_recovery_oauth_states(self, now: int) -> None:
        self.management_recovery_oauth_states.cleanup(now=now)

    def _require_upgrade_request(self, upgrade_request_id: str) -> UpgradeRequestRecord:
        now = now_ts()
        self._cleanup_upgrade_requests(now)
        request = self.upgrade_requests.get(upgrade_request_id)
        if request is None:
            raise KeyError("upgrade request not found")
        if request.status == "expired":
            raise TokenValidationError("upgrade request expired")
        return request

    def _upgrade_status_payload(self, request: UpgradeRequestRecord) -> dict[str, Any]:
        next_step = ""
        if request.status in {"requested", "human_pending"}:
            next_step = "verify_email" if request.target_level == "L1" else "connect_social"
        payload = {
            "upgrade_request_id": request.upgrade_request_id,
            "agent_id": request.agent_id,
            "target_level": request.target_level,
            "status": request.status,
            "next_step": next_step,
            "expires_at": request.expires_at,
            "failure_reason": request.failure_reason,
            "contact_email_masked": request.contact_email_masked,
            "social_provider": request.social_provider,
        }
        if request.target_level == "L1":
            payload["email_delivery"] = {
                "state": request.email_delivery_state,
                "provider": request.email_delivery_provider,
                "attempt_count": request.email_delivery_attempt_count,
                "last_attempt_at": request.email_delivery_last_attempt_at,
                "last_error_code": request.email_delivery_last_error_code,
                "last_error_detail": request.email_delivery_last_error_detail,
            }
        return payload

    @staticmethod
    def _email_delivery_error_code(exc: Exception) -> str:
        error_name = exc.__class__.__name__.strip()
        if not error_name:
            return "email_delivery_error"
        return f"email_delivery_{error_name.lower()}"

    def _send_upgrade_l1_email_link_internal(
        self,
        *,
        request: UpgradeRequestRecord,
    ) -> dict[str, Any]:
        now = now_ts()
        self._cleanup_upgrade_magic_links(now)
        if request.target_level != "L1":
            raise TokenValidationError("email link is only available for L1 upgrade")
        if request.status not in {"human_pending", "requested"}:
            raise TokenValidationError("upgrade request is not waiting for email verification")
        if not request.contact_email_hash or not request.contact_email_ciphertext:
            raise TokenValidationError("contact_email missing in upgrade request")

        request.email_delivery_attempt_count += 1
        request.email_delivery_last_attempt_at = now

        raw_token = generate_nonce(24)
        token_hash = self._sha256_hex(raw_token)
        record = UpgradeMagicLinkRecord(
            token_hash=token_hash,
            upgrade_request_id=request.upgrade_request_id,
            expires_at=now + self.magic_link_ttl_seconds,
        )
        self.upgrade_magic_links.set(
            key=token_hash,
            value=record,
            expires_at=record.expires_at,
            now=now,
        )
        response = {
            "upgrade_request_id": request.upgrade_request_id,
            "sent": True,
            "expires_at": record.expires_at,
        }
        if self.public_base_url or self.allow_local_upgrade_shortcuts:
            response["magic_link"] = self._build_email_verify_url(token=raw_token)
            response["verify_endpoint"] = "/v1/upgrades/l1/email/verify"
        if self.allow_local_upgrade_shortcuts:
            response["token"] = raw_token
        try:
            email_metadata = self.email_provider.send_upgrade_link(
                recipient_hint=self.hosted_key_cipher.decrypt_text(request.contact_email_ciphertext),
                upgrade_request_id=request.upgrade_request_id,
                verify_url=response.get("magic_link", "/v1/upgrades/l1/email/verify"),
                expires_at=record.expires_at,
            )
        except Exception as exc:
            request.email_delivery_state = "failed"
            request.email_delivery_provider = self.email_provider.__class__.__name__
            request.email_delivery_last_error_code = self._email_delivery_error_code(exc)
            request.email_delivery_last_error_detail = str(exc)
            raise

        request.email_delivery_state = "queued"
        request.email_delivery_provider = str(email_metadata.get("provider") or self.email_provider.__class__.__name__)
        request.email_delivery_last_error_code = None
        request.email_delivery_last_error_detail = None
        email_metadata["recipient_hint"] = request.contact_email_masked or "hidden"
        response["delivery"] = email_metadata
        response["email_delivery"] = self._upgrade_status_payload(request)["email_delivery"]
        return response

    def require_agent(self, agent_id: str) -> AgentRecord:
        record = self.agents.get(agent_id)
        if record is None:
            raise KeyError("agent not found")
        return record

    def set_admin_token(self, token: str | None) -> None:
        self._admin_token = token

    def _hash_token(self, token: str) -> str:
        return self._sha256_hex(token)

    def _issue_hosted_management_token(self, *, agent_id: str) -> tuple[str, int]:
        self._require_hosted_agent_private_key(agent_id)
        now = now_ts()
        token = generate_nonce(32)
        expires_at = now + self.hosted_management_token_ttl_seconds
        self._ensure_capacity(
            self.hosted_management_tokens,
            key=agent_id,
            max_items=self.max_agent_records,
            resource_name="hosted management token",
        )
        self.hosted_management_tokens[agent_id] = HostedManagementTokenRecord(
            token_hash=self._hash_token(token),
            issued_at=now,
            expires_at=expires_at,
        )
        return token, expires_at

    def _require_hosted_management_recovery_agent(self, *, agent_id: str) -> AgentRecord:
        record = self.require_agent(agent_id)
        if record.key_mode != "hosted-signer":
            raise PermissionError("management token recovery is only available for hosted-signer agents")
        self._require_hosted_agent_private_key(agent_id)
        return record

    @staticmethod
    def _social_snapshot_identity(snapshot: dict[str, Any]) -> tuple[str, str]:
        provider_user_id = str(
            snapshot.get("provider_user_id")
            or snapshot.get("id")
            or snapshot.get("user_id")
            or ""
        ).strip()
        username_or_handle = str(
            snapshot.get("username_or_handle")
            or snapshot.get("handle")
            or snapshot.get("login")
            or snapshot.get("vanity_name")
            or ""
        ).strip()
        return provider_user_id, username_or_handle

    def _issue_recovered_hosted_management_token(
        self,
        *,
        agent_id: str,
        factor: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        next_token, expires_at = self._issue_hosted_management_token(agent_id=agent_id)
        result = {
            "agent_id": agent_id,
            "hosted_management_token": next_token,
            "hosted_management_token_expires_at": expires_at,
            "recovered": True,
            "recovery_factor": factor,
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="hosted_management_token_recover",
            resource_type="hosted_management_token",
            resource_id=agent_id,
            metadata={"factor": factor, **(metadata or {}), "expires_at": expires_at},
        )
        return result

    def get_hosted_management_recovery_factors(self, *, agent_id: str) -> dict[str, Any]:
        self._sync_state()
        record = self._require_hosted_management_recovery_agent(agent_id=agent_id)
        factors: list[dict[str, Any]] = []
        if record.owner_id and record.recovery_email_ciphertext and record.recovery_email_masked:
            factors.append(
                {
                    "type": "email",
                    "level": "L1" if record.level == "L1" else "L2",
                    "contact": record.recovery_email_masked,
                }
            )
        if record.level == "L2":
            for provider, snapshot in sorted(record.social_accounts.items()):
                if provider not in self.enabled_social_providers:
                    continue
                factors.append(
                    {
                        "type": "social",
                        "provider": provider,
                        "level": "L2",
                        "handle": snapshot.get("username_or_handle"),
                    }
                )
        preferred_factor = "social" if any(item["type"] == "social" for item in factors) else ("email" if factors else None)
        return {
            "agent_id": agent_id,
            "key_mode": record.key_mode,
            "level": record.level,
            "available_factors": factors,
            "preferred_factor": preferred_factor,
        }

    def send_hosted_management_recovery_email_link(self, *, agent_id: str) -> dict[str, Any]:
        self._sync_state()
        now = now_ts()
        self._cleanup_management_recovery_email_links(now)
        record = self._require_hosted_management_recovery_agent(agent_id=agent_id)
        if not record.owner_id or not record.recovery_email_ciphertext or not record.recovery_email_masked:
            raise PermissionError("email recovery is not available for this agent")

        raw_token = generate_nonce(24)
        token_hash = self._sha256_hex(raw_token)
        recovery = ManagementRecoveryEmailLinkRecord(
            token_hash=token_hash,
            agent_id=agent_id,
            expires_at=now + self.magic_link_ttl_seconds,
        )
        self.management_recovery_email_links.set(
            key=token_hash,
            value=recovery,
            expires_at=recovery.expires_at,
            now=now,
        )
        verify_url = "/v1/signer/recovery/email/verify"
        if self.public_base_url or self.allow_local_upgrade_shortcuts:
            verify_url = self._build_management_recovery_email_verify_url(token=raw_token)
        response = {
            "agent_id": agent_id,
            "sent": True,
            "recovery_factor": "email",
            "contact_email_masked": record.recovery_email_masked,
            "expires_at": recovery.expires_at,
            "verify_endpoint": "/v1/signer/recovery/email/verify",
        }
        if self.public_base_url or self.allow_local_upgrade_shortcuts:
            response["magic_link"] = verify_url
        if self.allow_local_upgrade_shortcuts:
            response["token"] = raw_token

        metadata = self.email_provider.send_management_recovery_link(
            recipient_hint=self.hosted_key_cipher.decrypt_text(record.recovery_email_ciphertext),
            agent_id=agent_id,
            verify_url=verify_url,
            expires_at=recovery.expires_at,
        )
        metadata["recipient_hint"] = record.recovery_email_masked
        response["delivery"] = metadata
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="hosted_management_token_recovery_email_send",
            resource_type="hosted_management_token",
            resource_id=agent_id,
            metadata={"provider": metadata.get("provider", "unknown")},
        )
        return response

    def verify_hosted_management_recovery_email(self, *, token: str) -> dict[str, Any]:
        self._sync_state()
        now = now_ts()
        self._cleanup_management_recovery_email_links(now)
        token_hash = self._sha256_hex(token)
        link = self.management_recovery_email_links.get(token_hash)
        if link is None:
            raise KeyError("management recovery link not found")
        if link.used_at is not None:
            raise TokenValidationError("management recovery link already used")
        if link.expires_at < now - 30:
            raise TokenValidationError("management recovery link expired")
        link.used_at = now
        return self._issue_recovered_hosted_management_token(
            agent_id=link.agent_id,
            factor="email",
            metadata={"channel": "email"},
        )

    def start_hosted_management_recovery_social(self, *, agent_id: str, provider: str) -> dict[str, Any]:
        self._sync_state()
        now = now_ts()
        self._cleanup_management_recovery_oauth_states(now)
        record = self._require_hosted_management_recovery_agent(agent_id=agent_id)
        normalized_provider = provider.strip().lower()
        if normalized_provider not in self.enabled_social_providers:
            raise TokenValidationError(f"provider {normalized_provider} is not enabled")
        if record.level != "L2":
            raise PermissionError("social recovery requires L2 agent")
        if normalized_provider not in record.social_accounts:
            raise PermissionError(f"{normalized_provider} recovery is not linked for this agent")

        state = generate_nonce(16)
        recovery_state = ManagementRecoveryOAuthStateRecord(
            state=state,
            agent_id=agent_id,
            provider=normalized_provider,
            expires_at=now + self.oauth_state_ttl_seconds,
        )
        self.management_recovery_oauth_states.set(
            key=state,
            value=recovery_state,
            expires_at=recovery_state.expires_at,
            now=now,
        )
        adapter = self.social_provider_adapters.get(normalized_provider)
        if adapter is None:
            raise TokenValidationError(f"provider {normalized_provider} is not enabled")
        authorize_url = adapter.build_authorize_url(state=state)
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="hosted_management_token_recovery_social_start",
            resource_type="hosted_management_token",
            resource_id=agent_id,
            metadata={"provider": normalized_provider},
        )
        return {
            "agent_id": agent_id,
            "provider": normalized_provider,
            "recovery_factor": "social",
            "state": state,
            "authorize_url": authorize_url,
            "callback_url": self._build_social_callback_url(provider=normalized_provider),
            "expires_at": recovery_state.expires_at,
        }

    def _complete_hosted_management_recovery_social(
        self,
        *,
        agent_id: str,
        provider: str,
        provider_user_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        record = self._require_hosted_management_recovery_agent(agent_id=agent_id)
        linked_snapshot = record.social_accounts.get(provider)
        if linked_snapshot is None:
            raise PermissionError(f"{provider} recovery is not linked for this agent")
        linked_provider_user_id, linked_username = self._social_snapshot_identity(linked_snapshot)
        provider_user_id, username_or_handle = self._social_snapshot_identity(provider_user_snapshot)
        if linked_provider_user_id and provider_user_id and linked_provider_user_id != provider_user_id:
            raise PermissionError("social recovery subject mismatch")
        if linked_username and username_or_handle and linked_username.lower() != username_or_handle.lower():
            raise PermissionError("social recovery subject mismatch")
        return self._issue_recovered_hosted_management_token(
            agent_id=agent_id,
            factor=f"social:{provider}",
            metadata={"provider": provider},
        )

    def complete_hosted_management_recovery_social_callback(
        self,
        *,
        provider: str,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        self._sync_state()
        now = now_ts()
        self._cleanup_management_recovery_oauth_states(now)
        recovery_state = self.management_recovery_oauth_states.get(state)
        if recovery_state is None:
            raise KeyError("management recovery oauth state not found")
        if recovery_state.used_at is not None:
            raise TokenValidationError("management recovery oauth state already used")
        if recovery_state.expires_at < now - 30:
            raise TokenValidationError("management recovery oauth state expired")
        normalized_provider = provider.strip().lower()
        if recovery_state.provider != normalized_provider:
            raise TokenValidationError("management recovery provider mismatch")
        adapter = self.social_provider_adapters.get(normalized_provider)
        if adapter is None:
            raise TokenValidationError(f"provider {normalized_provider} is not enabled")
        provider_user_snapshot = adapter.exchange_code(code=code, state=state)
        recovery_state.used_at = now
        return self._complete_hosted_management_recovery_social(
            agent_id=recovery_state.agent_id,
            provider=normalized_provider,
            provider_user_snapshot=provider_user_snapshot,
        )

    def complete_hosted_management_recovery_social(
        self,
        *,
        agent_id: str,
        provider: str,
        provider_user_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        self._sync_state()
        if not self.allow_local_upgrade_shortcuts:
            raise PermissionError("local management recovery social shortcut is disabled")
        normalized_provider = provider.strip().lower()
        return self._complete_hosted_management_recovery_social(
            agent_id=agent_id,
            provider=normalized_provider,
            provider_user_snapshot=provider_user_snapshot,
        )

    def has_hosted_management_recovery_oauth_state(self, *, state: str) -> bool:
        self._sync_state()
        now = now_ts()
        self._cleanup_management_recovery_oauth_states(now)
        return self.management_recovery_oauth_states.get(state) is not None

    def authorize_hosted_management(self, *, agent_id: str, token: str) -> None:
        self.require_agent(agent_id)
        self._require_hosted_agent_private_key(agent_id)
        token_record = self.hosted_management_tokens.get(agent_id)
        if token_record is None:
            raise PermissionError("hosted management token not provisioned")
        now = now_ts()
        if token_record.expires_at < now:
            self.hosted_management_tokens.pop(agent_id, None)
            raise PermissionError("hosted management token expired")
        if not hmac.compare_digest(token_record.token_hash, self._hash_token(token)):
            raise PermissionError("invalid hosted management token")

    def authorize_self_hosted_management_proof(
        self,
        *,
        agent_id: str,
        operation: str,
        resource_id: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_agent: str,
    ) -> None:
        self.require_agent(agent_id)
        if agent_id in self.hosted_agent_private_keys:
            raise PermissionError("hosted-signer agent must use hosted management token")
        now = now_ts()
        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="agent auth",
        )
        cache_key = (agent_id, nonce)
        self.used_agent_auth_nonces.cleanup(now=now)
        if self.used_agent_auth_nonces.contains(cache_key):
            raise TokenValidationError("nonce already used")
        self.used_agent_auth_nonces.add(
            key=cache_key,
            expires_at=expires_at,
            now=now,
        )
        payload = build_agent_auth_payload(
            agent_id=agent_id,
            operation=operation,
            resource_id=resource_id,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        verify_detached(payload, signature_by_agent, load_public_key(agent_id))
        self._persist_state()

    def rotate_hosted_management_token(self, *, agent_id: str, token: str) -> dict[str, Any]:
        self._sync_state()
        self.authorize_hosted_management(agent_id=agent_id, token=token)
        next_token, expires_at = self._issue_hosted_management_token(agent_id=agent_id)
        result = {
            "agent_id": agent_id,
            "hosted_management_token": next_token,
            "hosted_management_token_expires_at": expires_at,
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="hosted_management_token_rotate",
            resource_type="hosted_management_token",
            resource_id=agent_id,
            metadata={"expires_at": expires_at},
        )
        return result

    def revoke_hosted_management_token(self, *, agent_id: str, token: str) -> dict[str, Any]:
        self._sync_state()
        self.authorize_hosted_management(agent_id=agent_id, token=token)
        existing = self.hosted_management_tokens.get(agent_id)
        if existing is not None:
            existing.revoked_at = now_ts()
        self.hosted_management_tokens.pop(agent_id, None)
        now = now_ts()
        self.hosted_session_keys.cleanup(now=now)
        for session_key, session in list(self.hosted_session_keys.items()):
            if session.agent_id == agent_id:
                self.hosted_session_keys.discard(session_key)
        result = {
            "agent_id": agent_id,
            "revoked": True,
            "revoked_at": now,
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="hosted_management_token_revoke",
            resource_type="hosted_management_token",
            resource_id=agent_id,
            metadata={"revoked_at": now},
        )
        return result

    def is_admin_token(self, *, token: str) -> bool:
        if not self._admin_token:
            return False
        return hmac.compare_digest(self._admin_token, token)

    def authorize_admin_or_hosted(self, *, agent_id: str, token: str) -> None:
        if self.is_admin_token(token=token):
            return
        self.authorize_hosted_management(agent_id=agent_id, token=token)

    def authorize_admin_or_hosted_or_agent_proof(
        self,
        *,
        agent_id: str,
        token: str | None,
        operation: str,
        resource_id: str,
        proof_agent_id: str | None,
        proof_nonce: str | None,
        proof_issued_at: int | None,
        proof_expires_at: int | None,
        proof_signature_by_agent: str | None,
    ) -> None:
        if token is not None:
            self.authorize_admin_or_hosted(agent_id=agent_id, token=token)
            return
        if not proof_agent_id:
            raise PermissionError("agent proof agent_id is required")
        if proof_agent_id != agent_id:
            raise PermissionError("agent proof subject mismatch")
        if not proof_nonce:
            raise PermissionError("agent proof nonce is required")
        if proof_issued_at is None or proof_expires_at is None:
            raise PermissionError("agent proof signed window is required")
        if not proof_signature_by_agent:
            raise PermissionError("agent proof signature is required")
        self.authorize_self_hosted_management_proof(
            agent_id=agent_id,
            operation=operation,
            resource_id=resource_id,
            nonce=proof_nonce,
            issued_at=proof_issued_at,
            expires_at=proof_expires_at,
            signature_by_agent=proof_signature_by_agent,
        )

    def authorize_admin(self, *, token: str) -> None:
        if not self._admin_token:
            raise PermissionError("RARE_ADMIN_TOKEN is not configured")
        if not self.is_admin_token(token=token):
            raise PermissionError("invalid admin token")

    def _require_hosted_agent_private_key(self, agent_id: str) -> Ed25519PrivateKey:
        private_key = self.hosted_agent_private_keys.get(agent_id)
        if private_key is None:
            raise PermissionError("agent does not use hosted signer")
        return private_key

    def _check_name_rate_limit(self, *, agent_id: str, now: int) -> int | None:
        events = self.name_change_events.setdefault(agent_id, [])
        window_start = now - 24 * 3600
        events[:] = [ts for ts in events if ts >= window_start]
        if len(events) >= 3:
            retry_after = min(events) + 24 * 3600
            return retry_after
        return None

    def set_name(
        self,
        *,
        agent_id: str,
        name: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_agent: str,
    ) -> dict:
        self._sync_state()
        record = self.require_agent(agent_id)
        now = now_ts()

        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="set_name",
        )

        self.used_name_nonces.cleanup(now=now)
        if self.used_name_nonces.contains(nonce):
            raise TokenValidationError("nonce already used")
        self.used_name_nonces.add(key=nonce, expires_at=expires_at, now=now)

        payload = build_set_name_payload(
            agent_id=agent_id,
            name=name,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        agent_public_key = load_public_key(agent_id)
        verify_detached(payload, signature_by_agent, agent_public_key)

        normalized_name = validate_name(name)

        retry_after = self._check_name_rate_limit(agent_id=agent_id, now=now)
        if retry_after is not None:
            raise TokenValidationError(f"name update rate limit exceeded; retry_after={retry_after}")

        record.name = normalized_name
        record.name_updated_at = now
        self.name_change_events.setdefault(agent_id, []).append(now)

        profile = self._ensure_identity_profile(agent_id)
        profile.summary = f"display_name={normalized_name}"
        profile.version += 1
        profile.updated_at = now

        result = {
            "name": record.name,
            "updated_at": record.name_updated_at,
            "public_identity_attestation": self._issue_public_identity_attestation(record),
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="set_name",
            resource_type="agent",
            resource_id=agent_id,
            metadata={"name": normalized_name},
        )
        return result

    def sign_set_name(
        self,
        *,
        agent_id: str,
        name: str,
        ttl_seconds: int = 120,
    ) -> dict:
        self.require_agent(agent_id)
        private_key = self._require_hosted_agent_private_key(agent_id)
        self._validate_signer_ttl(ttl_seconds=ttl_seconds, prefix="set_name signer")

        issued_at = now_ts()
        expires_at = issued_at + ttl_seconds
        nonce = generate_nonce(10)

        sign_input = build_set_name_payload(
            agent_id=agent_id,
            name=name,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        signature = sign_detached(sign_input, private_key)

        return {
            "agent_id": agent_id,
            "name": name,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        }

    def _cleanup_session_cache(self, now: int) -> None:
        self.hosted_session_keys.cleanup(now=now)

    def _cleanup_action_nonce_cache(self, now: int) -> None:
        self.used_action_nonces.cleanup(now=now)

    def _cleanup_full_issue_nonce_cache(self, now: int) -> None:
        self.used_full_issue_nonces.cleanup(now=now)

    def _cleanup_upgrade_nonce_cache(self, now: int) -> None:
        self.seen_upgrade_nonces.cleanup(now=now)

    def prepare_auth(
        self,
        *,
        agent_id: str,
        aud: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        scope: Iterable[str],
        delegation_ttl_seconds: int = 3600,
    ) -> dict:
        self._sync_state()
        self.require_agent(agent_id)
        self._validate_delegation_ttl(ttl_seconds=delegation_ttl_seconds, prefix="prepare_auth")

        now = now_ts()
        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="challenge",
        )

        session_private_b64, session_pubkey = generate_ed25519_keypair()
        session_private_key = load_private_key(session_private_b64)

        sign_input = build_auth_challenge_payload(
            aud=aud,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        signature = sign_detached(sign_input, session_private_key)

        delegation = self._issue_rare_delegation_token(
            agent_id=agent_id,
            session_pubkey=session_pubkey,
            aud=aud,
            scope=scope,
            ttl_seconds=delegation_ttl_seconds,
            jti=generate_nonce(12),
        )

        session_exp = now + delegation_ttl_seconds
        self.hosted_session_keys.set(
            key=session_pubkey,
            value=HostedSessionRecord(
                session_pubkey=session_pubkey,
                agent_id=agent_id,
                aud=aud,
                private_key=session_private_key,
                created_at=now,
                expires_at=session_exp,
            ),
            expires_at=session_exp,
            now=now,
        )

        result = {
            "agent_id": agent_id,
            "session_pubkey": session_pubkey,
            "delegation_token": delegation,
            "signature_by_session": signature,
            "session_expires_at": session_exp,
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="hosted_prepare_auth",
            resource_type="hosted_session",
            resource_id=session_pubkey,
            metadata={"aud": aud, "expires_at": session_exp},
        )
        return result

    def sign_action(
        self,
        *,
        agent_id: str,
        session_pubkey: str,
        session_token: str,
        aud: str,
        action: str,
        action_payload: dict[str, Any],
        nonce: str,
        issued_at: int,
        expires_at: int,
    ) -> dict:
        self._sync_state()
        self.require_agent(agent_id)

        now = now_ts()
        self._cleanup_session_cache(now)
        self._cleanup_action_nonce_cache(now)

        session = self.hosted_session_keys.get(session_pubkey)
        if session is None:
            raise TokenValidationError("unknown hosted session key")
        if session.agent_id != agent_id:
            raise TokenValidationError("session not owned by agent")
        if session.aud != aud:
            raise TokenValidationError("session aud mismatch")
        if session.expires_at < now - 30:
            raise TokenValidationError("session key expired")

        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="action",
        )

        nonce_key = (session_pubkey, nonce)
        if self.used_action_nonces.contains(nonce_key):
            raise TokenValidationError("action nonce already used")
        self.used_action_nonces.add(key=nonce_key, expires_at=expires_at, now=now)

        sign_input = build_action_payload(
            aud=aud,
            session_token=session_token,
            action=action,
            action_payload=action_payload,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        signature = sign_detached(sign_input, session.private_key)

        result = {
            "agent_id": agent_id,
            "session_pubkey": session_pubkey,
            "session_token": session_token,
            "aud": aud,
            "action": action,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_session": signature,
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="hosted_sign_action",
            resource_type="hosted_session",
            resource_id=session_pubkey,
            metadata={"aud": aud, "action": action},
        )
        return result

    def sign_delegation(
        self,
        *,
        agent_id: str,
        session_pubkey: str,
        aud: str,
        scope: Iterable[str],
        ttl_seconds: int,
    ) -> dict:
        self._sync_state()
        self.require_agent(agent_id)
        load_public_key(session_pubkey)
        self._validate_delegation_ttl(ttl_seconds=ttl_seconds, prefix="sign_delegation")

        token = self._issue_rare_delegation_token(
            agent_id=agent_id,
            session_pubkey=session_pubkey,
            aud=aud,
            scope=scope,
            ttl_seconds=ttl_seconds,
            jti=generate_nonce(12),
        )
        return {"delegation_token": token}

    def sign_full_attestation_issue(
        self,
        *,
        agent_id: str,
        platform_aud: str,
        ttl_seconds: int = 120,
    ) -> dict[str, Any]:
        self._sync_state()
        self.require_agent(agent_id)
        private_key = self._require_hosted_agent_private_key(agent_id)
        self._validate_signer_ttl(ttl_seconds=ttl_seconds, prefix="sign_full_attestation_issue")
        issued_at = now_ts()
        expires_at = issued_at + ttl_seconds
        nonce = generate_nonce(10)
        sign_input = build_full_attestation_issue_payload(
            agent_id=agent_id,
            platform_aud=platform_aud,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        signature = sign_detached(sign_input, private_key)
        return {
            "agent_id": agent_id,
            "platform_aud": platform_aud,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        }

    def sign_upgrade_request(
        self,
        *,
        agent_id: str,
        target_level: str,
        request_id: str,
        ttl_seconds: int = 120,
    ) -> dict[str, Any]:
        self._sync_state()
        if target_level not in {"L1", "L2"}:
            raise TokenValidationError("target_level must be L1 or L2")
        self.require_agent(agent_id)
        private_key = self._require_hosted_agent_private_key(agent_id)
        self._validate_signer_ttl(ttl_seconds=ttl_seconds, prefix="sign_upgrade_request")
        issued_at = now_ts()
        expires_at = issued_at + ttl_seconds
        nonce = generate_nonce(10)
        sign_input = build_upgrade_request_payload(
            agent_id=agent_id,
            target_level=target_level,
            request_id=request_id,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        signature = sign_detached(sign_input, private_key)
        return {
            "agent_id": agent_id,
            "target_level": target_level,
            "request_id": request_id,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        }

    def _consume_upgrade_nonce(
        self,
        *,
        agent_id: str,
        nonce: str,
        expires_at: int,
        now: int,
    ) -> None:
        self._cleanup_upgrade_nonce_cache(now)
        nonce_key = (agent_id, nonce)
        if self.seen_upgrade_nonces.contains(nonce_key):
            raise TokenValidationError("upgrade nonce already used")
        self.seen_upgrade_nonces.add(key=nonce_key, expires_at=expires_at, now=now)

    def create_upgrade_request(
        self,
        *,
        agent_id: str,
        target_level: str,
        request_id: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_agent: str,
        contact_email: str | None,
        send_email: bool = True,
    ) -> dict[str, Any]:
        self._sync_state()
        record = self.require_agent(agent_id)
        if target_level not in {"L1", "L2"}:
            raise TokenValidationError("target_level must be L1 or L2")
        if not request_id.strip():
            raise TokenValidationError("request_id is required")
        now = now_ts()
        self._cleanup_upgrade_requests(now)
        if request_id in self.upgrade_requests:
            raise TokenValidationError("request_id already exists")

        if target_level == "L2" and record.level not in {"L1", "L2"}:
            raise PermissionError("L2 upgrade requires current level L1 or higher")

        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="upgrade request",
        )
        self._consume_upgrade_nonce(
            agent_id=agent_id,
            nonce=nonce,
            expires_at=expires_at,
            now=now,
        )

        sign_input = build_upgrade_request_payload(
            agent_id=agent_id,
            target_level=target_level,
            request_id=request_id,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        verify_detached(sign_input, signature_by_agent, load_public_key(agent_id))

        contact_email_hash: str | None = None
        contact_email_masked: str | None = None
        contact_email_ciphertext: str | None = None
        if target_level == "L1":
            if not isinstance(contact_email, str) or not contact_email.strip():
                raise TokenValidationError("contact_email is required for L1 upgrade")
            normalized_email, contact_email_hash, contact_email_masked = self._validate_contact_email(contact_email)
            contact_email_ciphertext = self.hosted_key_cipher.encrypt_text(normalized_email)

        request_ttl = now + self.upgrade_request_ttl_seconds
        request = UpgradeRequestRecord(
            upgrade_request_id=request_id,
            agent_id=agent_id,
            target_level=target_level,
            status="human_pending",
            requested_at=now,
            expires_at=request_ttl,
            contact_email_hash=contact_email_hash,
            contact_email_masked=contact_email_masked,
            contact_email_ciphertext=contact_email_ciphertext,
            last_transition_at=now,
        )
        self._ensure_capacity(
            self.upgrade_requests,
            key=request_id,
            max_items=self.max_upgrade_requests,
            resource_name="upgrade request",
        )
        self.upgrade_requests[request_id] = request
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="upgrade_request_create",
            resource_type="upgrade_request",
            resource_id=request_id,
            metadata={"target_level": target_level, "send_email": bool(send_email and target_level == "L1")},
        )
        result = self._upgrade_status_payload(request)
        if target_level == "L1" and send_email:
            try:
                delivery = self._send_upgrade_l1_email_link_internal(request=request)
            except Exception as exc:
                self._append_audit_event(
                    actor_type="agent",
                    actor_id=agent_id,
                    agent_id=agent_id,
                    event_type="upgrade_l1_send_link",
                    resource_type="upgrade_request",
                    resource_id=request_id,
                    status="error",
                    metadata={"error_code": request.email_delivery_last_error_code, "detail": str(exc)},
                )
            else:
                self._append_audit_event(
                    actor_type="agent",
                    actor_id=agent_id,
                    agent_id=agent_id,
                    event_type="upgrade_l1_send_link",
                    resource_type="upgrade_request",
                    resource_id=request_id,
                    metadata={"provider": delivery.get("delivery", {}).get("provider", "unknown"), "auto": True},
                )
                result = self._upgrade_status_payload(request)
                result["delivery"] = delivery.get("delivery")
                for key in ("magic_link", "verify_endpoint", "token"):
                    if key in delivery:
                        result[key] = delivery[key]
            if "delivery" not in result:
                result = self._upgrade_status_payload(request)
        return result

    def get_upgrade_request(self, *, upgrade_request_id: str) -> dict[str, Any]:
        self._sync_state()
        request = self._require_upgrade_request(upgrade_request_id)
        return self._upgrade_status_payload(request)

    def get_upgrade_request_authorized(
        self,
        *,
        upgrade_request_id: str,
        token: str | None,
        proof_agent_id: str | None,
        proof_nonce: str | None,
        proof_issued_at: int | None,
        proof_expires_at: int | None,
        proof_signature_by_agent: str | None,
    ) -> dict[str, Any]:
        self._sync_state()
        request = self._require_upgrade_request(upgrade_request_id)
        self.authorize_admin_or_hosted_or_agent_proof(
            agent_id=request.agent_id,
            token=token,
            operation="upgrade_status",
            resource_id=upgrade_request_id,
            proof_agent_id=proof_agent_id,
            proof_nonce=proof_nonce,
            proof_issued_at=proof_issued_at,
            proof_expires_at=proof_expires_at,
            proof_signature_by_agent=proof_signature_by_agent,
        )
        return self._upgrade_status_payload(request)

    def authorize_upgrade_request_operation(
        self,
        *,
        upgrade_request_id: str,
        token: str | None,
        operation: str,
        resource_id: str,
        proof_agent_id: str | None,
        proof_nonce: str | None,
        proof_issued_at: int | None,
        proof_expires_at: int | None,
        proof_signature_by_agent: str | None,
    ) -> None:
        self._sync_state()
        request = self._require_upgrade_request(upgrade_request_id)
        self.authorize_admin_or_hosted_or_agent_proof(
            agent_id=request.agent_id,
            token=token,
            operation=operation,
            resource_id=resource_id,
            proof_agent_id=proof_agent_id,
            proof_nonce=proof_nonce,
            proof_issued_at=proof_issued_at,
            proof_expires_at=proof_expires_at,
            proof_signature_by_agent=proof_signature_by_agent,
        )

    def send_upgrade_l1_email_link(self, *, upgrade_request_id: str) -> dict[str, Any]:
        self._sync_state()
        request = self._require_upgrade_request(upgrade_request_id)
        response = self._send_upgrade_l1_email_link_internal(request=request)
        self._append_audit_event(
            actor_type="agent",
            actor_id=request.agent_id,
            agent_id=request.agent_id,
            event_type="upgrade_l1_send_link",
            resource_type="upgrade_request",
            resource_id=upgrade_request_id,
            metadata={"provider": response.get("delivery", {}).get("provider", "unknown"), "auto": False},
        )
        return response

    def _apply_upgraded_level(self, request: UpgradeRequestRecord) -> dict[str, Any]:
        record = self.require_agent(request.agent_id)
        profile = self._ensure_identity_profile(request.agent_id)
        now = now_ts()

        if request.target_level == "L1":
            if not request.contact_email_hash:
                raise TokenValidationError("L1 upgrade missing email verification proof")
            record.owner_id = f"email:{request.contact_email_hash}"
            record.recovery_email_masked = request.contact_email_masked
            record.recovery_email_ciphertext = request.contact_email_ciphertext
            if record.level == "L0":
                record.level = "L1"
            labels = set(profile.labels)
            labels.add("owner-linked")
            labels.add("level-l1")
            profile.labels = sorted(labels)
        else:
            if record.level not in {"L1", "L2"}:
                raise PermissionError("L2 upgrade requires L1")
            if not request.social_provider or request.social_provider not in SOCIAL_PROVIDERS:
                raise TokenValidationError("L2 upgrade missing social provider verification")
            social_account = request.social_account or {}
            provider_user_id = str(
                social_account.get("provider_user_id")
                or social_account.get("id")
                or social_account.get("user_id")
                or ""
            ).strip()
            username_or_handle = str(
                social_account.get("username_or_handle")
                or social_account.get("handle")
                or social_account.get("login")
                or social_account.get("vanity_name")
                or ""
            ).strip()
            if not provider_user_id or not username_or_handle:
                raise TokenValidationError(f"{request.social_provider} social account data missing")
            normalized_snapshot = {
                "provider": request.social_provider,
                "provider_user_id": provider_user_id,
                "username_or_handle": username_or_handle,
                "display_name": str(social_account.get("display_name") or username_or_handle),
                "profile_url": str(social_account.get("profile_url") or ""),
                "raw_snapshot": social_account.get("raw_snapshot") if isinstance(social_account.get("raw_snapshot"), dict) else social_account,
            }
            record.social_accounts[request.social_provider] = normalized_snapshot
            if request.social_provider == "x":
                record.twitter = {"user_id": provider_user_id, "handle": username_or_handle}
            elif request.social_provider == "github":
                record.github = {"id": provider_user_id, "login": username_or_handle}
            elif request.social_provider == "linkedin":
                record.linkedin = {"id": provider_user_id, "vanity_name": username_or_handle}
            record.level = "L2"
            labels = set(profile.labels)
            if request.social_provider == "x":
                labels.add("twitter-linked")
            if request.social_provider == "github":
                labels.add("github-linked")
            if request.social_provider == "linkedin":
                labels.add("linkedin-linked")
            labels.add("level-l2")
            profile.labels = sorted(labels)

        request.status = "upgraded"
        request.last_transition_at = now
        profile.version += 1
        profile.updated_at = now
        return {
            **self._upgrade_status_payload(request),
            "level": record.level,
            "public_identity_attestation": self._issue_public_identity_attestation(record),
        }

    def verify_upgrade_l1_email(self, *, token: str) -> dict[str, Any]:
        self._sync_state()
        now = now_ts()
        self._cleanup_upgrade_magic_links(now)
        token_hash = self._sha256_hex(token)
        link = self.upgrade_magic_links.get(token_hash)
        if link is None:
            raise KeyError("upgrade magic link not found")
        if link.used_at is not None:
            raise TokenValidationError("upgrade magic link already used")
        if link.expires_at < now - 30:
            raise TokenValidationError("upgrade magic link expired")

        request = self._require_upgrade_request(link.upgrade_request_id)
        if request.target_level != "L1":
            raise TokenValidationError("upgrade request target is not L1")
        request.email_verified_at = now
        request.email_delivery_state = "verified"
        request.email_delivery_last_error_code = None
        request.email_delivery_last_error_detail = None
        request.status = "verified"
        request.last_transition_at = now
        link.used_at = now
        result = self._apply_upgraded_level(request)
        self._append_audit_event(
            actor_type="system",
            actor_id="email",
            agent_id=request.agent_id,
            event_type="upgrade_l1_verify",
            resource_type="upgrade_request",
            resource_id=request.upgrade_request_id,
        )
        return result

    def start_upgrade_l2_social(self, *, upgrade_request_id: str, provider: str) -> dict[str, Any]:
        self._sync_state()
        normalized_provider = provider.strip().lower()
        if normalized_provider not in self.enabled_social_providers:
            raise TokenValidationError(f"provider {normalized_provider} is not enabled")
        now = now_ts()
        self._cleanup_upgrade_oauth_states(now)
        request = self._require_upgrade_request(upgrade_request_id)
        if request.target_level != "L2":
            raise TokenValidationError("social auth is only available for L2 upgrade")
        if request.status not in {"human_pending", "requested"}:
            raise TokenValidationError("upgrade request is not waiting for social verification")

        state = generate_nonce(16)
        state_record = UpgradeOAuthStateRecord(
            state=state,
            upgrade_request_id=upgrade_request_id,
            provider=normalized_provider,
            expires_at=now + self.oauth_state_ttl_seconds,
        )
        self.upgrade_oauth_states.set(
            key=state,
            value=state_record,
            expires_at=state_record.expires_at,
            now=now,
        )
        adapter = self.social_provider_adapters.get(normalized_provider)
        if adapter is None:
            raise TokenValidationError("unsupported social provider")
        authorize_url = adapter.build_authorize_url(state=state)
        result = {
            "upgrade_request_id": upgrade_request_id,
            "provider": normalized_provider,
            "state": state,
            "expires_at": state_record.expires_at,
            "authorize_url": authorize_url,
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=request.agent_id,
            agent_id=request.agent_id,
            event_type="upgrade_l2_start_social",
            resource_type="upgrade_request",
            resource_id=upgrade_request_id,
            metadata={"provider": normalized_provider},
        )
        return result

    def social_callback_upgrade_l2(
        self,
        *,
        provider: str,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        self._sync_state()
        now = now_ts()
        self._cleanup_upgrade_oauth_states(now)

        normalized_provider = provider.strip().lower()
        state_record = self.upgrade_oauth_states.get(state)
        if state_record is None:
            raise KeyError("oauth state not found")
        if state_record.used_at is not None:
            raise TokenValidationError("oauth state already used")
        if state_record.expires_at < now - 30:
            raise TokenValidationError("oauth state expired")
        if state_record.provider != normalized_provider:
            raise TokenValidationError("oauth provider mismatch")
        if normalized_provider not in self.enabled_social_providers:
            raise TokenValidationError(f"provider {normalized_provider} is not enabled")
        if not code.strip():
            raise TokenValidationError("oauth code is required")

        request = self._require_upgrade_request(state_record.upgrade_request_id)
        if request.target_level != "L2":
            raise TokenValidationError("upgrade request target is not L2")
        state_record.used_at = now

        adapter = self.social_provider_adapters.get(normalized_provider)
        if adapter is None:
            raise TokenValidationError("unsupported social provider")
        request.social_account = adapter.exchange_code(code=code, state=state)
        request.social_provider = normalized_provider
        request.social_verified_at = now
        request.status = "verified"
        request.last_transition_at = now
        result = self._apply_upgraded_level(request)
        self._append_audit_event(
            actor_type="system",
            actor_id=normalized_provider,
            agent_id=request.agent_id,
            event_type="upgrade_l2_callback",
            resource_type="upgrade_request",
            resource_id=request.upgrade_request_id,
            metadata={"provider": normalized_provider},
        )
        return result

    def complete_upgrade_l2_social(
        self,
        *,
        upgrade_request_id: str,
        provider: str,
        provider_user_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        self._sync_state()
        if not self.allow_local_upgrade_shortcuts:
            raise PermissionError("local social complete shortcut is disabled")
        normalized_provider = provider.strip().lower()
        if normalized_provider not in self.enabled_social_providers:
            raise TokenValidationError(f"provider {normalized_provider} is not enabled")
        request = self._require_upgrade_request(upgrade_request_id)
        if request.target_level != "L2":
            raise TokenValidationError("upgrade request target is not L2")
        if not isinstance(provider_user_snapshot, dict):
            raise TokenValidationError("provider_user_snapshot must be object")

        now = now_ts()
        request.social_provider = normalized_provider
        request.social_verified_at = now
        request.social_account = provider_user_snapshot
        request.status = "verified"
        request.last_transition_at = now
        result = self._apply_upgraded_level(request)
        self._append_audit_event(
            actor_type="system",
            actor_id=normalized_provider,
            agent_id=request.agent_id,
            event_type="upgrade_l2_complete",
            resource_type="upgrade_request",
            resource_id=request.upgrade_request_id,
            metadata={"provider": normalized_provider},
        )
        return result

    def _cleanup_platform_register_challenges(self, now: int) -> None:
        self.platform_register_challenges.cleanup(now=now)

    def issue_platform_register_challenge(self, *, platform_aud: str, domain: str) -> dict[str, Any]:
        self._sync_state()
        if not platform_aud.strip():
            raise TokenValidationError("platform_aud cannot be empty")
        if not domain.strip():
            raise TokenValidationError("domain cannot be empty")

        now = now_ts()
        self._cleanup_platform_register_challenges(now)

        challenge_id = generate_nonce(10)
        txt_name = f"_rare-challenge.{domain}"
        txt_value = f"rare-platform-register-v1:{platform_aud}:{challenge_id}"
        expires_at = now + self.platform_register_challenge_ttl_seconds

        challenge = PlatformRegisterChallenge(
            challenge_id=challenge_id,
            platform_aud=platform_aud,
            domain=domain,
            txt_name=txt_name,
            txt_value=txt_value,
            expires_at=expires_at,
        )
        self.platform_register_challenges.set(
            key=challenge_id,
            value=challenge,
            expires_at=expires_at,
            now=now,
        )
        result = {
            "challenge_id": challenge.challenge_id,
            "txt_name": challenge.txt_name,
            "txt_value": challenge.txt_value,
            "expires_at": challenge.expires_at,
        }
        self._append_audit_event(
            actor_type="platform",
            actor_id=platform_aud,
            agent_id=None,
            event_type="platform_register_challenge_issue",
            resource_type="platform_register_challenge",
            resource_id=challenge_id,
            metadata={"domain": domain},
        )
        return result

    def _parse_platform_keys(self, keys: list[dict[str, Any]]) -> dict[str, PlatformKeyRecord]:
        if not keys:
            raise TokenValidationError("at least one platform key required")

        parsed: dict[str, PlatformKeyRecord] = {}
        for item in keys:
            kid = item.get("kid")
            public_key = item.get("public_key")
            if not isinstance(kid, str) or not kid.strip():
                raise TokenValidationError("platform key kid is required")
            if not isinstance(public_key, str) or not public_key.strip():
                raise TokenValidationError("platform key public_key is required")
            if kid in parsed:
                raise TokenValidationError("duplicate platform key kid")
            load_public_key(public_key)
            parsed[kid] = PlatformKeyRecord(kid=kid, public_key_b64=public_key)
        return parsed

    def complete_platform_register(
        self,
        *,
        challenge_id: str,
        platform_id: str,
        platform_aud: str,
        domain: str,
        keys: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._sync_state()
        now = now_ts()
        self._cleanup_platform_register_challenges(now)
        challenge = self.platform_register_challenges.get(challenge_id)
        if challenge is None:
            raise KeyError("platform register challenge not found")
        if challenge.status != "issued":
            raise TokenValidationError("platform register challenge already consumed")
        if challenge.expires_at < now - 30:
            challenge.status = "expired"
            raise TokenValidationError("platform register challenge expired")
        if challenge.platform_aud != platform_aud:
            raise TokenValidationError("platform_aud mismatch with challenge")
        if challenge.domain != domain:
            raise TokenValidationError("domain mismatch with challenge")

        txt_values = self.dns_txt_resolver(challenge.txt_name)
        if challenge.txt_value not in txt_values:
            raise TokenValidationError("platform DNS TXT proof mismatch")

        key_records = self._parse_platform_keys(keys)
        for kid in key_records:
            for existing_aud, platform in self.platforms.items():
                if existing_aud != platform_aud and kid in platform.keys:
                    raise TokenValidationError("platform key kid already used by another platform")
        existing = self.platforms.get(platform_aud)
        if existing is not None and existing.platform_id != platform_id:
            raise TokenValidationError("platform_aud already registered by another platform_id")

        record = PlatformRecord(
            platform_id=platform_id,
            platform_aud=platform_aud,
            domain=domain,
            keys=key_records,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._ensure_capacity(
            self.platforms,
            key=platform_aud,
            max_items=self.max_platform_records,
            resource_name="platform",
        )
        self.platforms[platform_aud] = record
        challenge.status = "consumed"

        result = {
            "platform_id": record.platform_id,
            "platform_aud": record.platform_aud,
            "domain": record.domain,
            "status": record.status,
        }
        self._append_audit_event(
            actor_type="platform",
            actor_id=platform_id,
            agent_id=None,
            event_type="platform_register_complete",
            resource_type="platform",
            resource_id=platform_aud,
            metadata={"domain": domain},
        )
        return result

    def _validate_signed_window(self, *, issued_at: int, expires_at: int, now: int, prefix: str) -> None:
        if issued_at > now + 30:
            raise TokenValidationError(f"{prefix} issued_at too far in future")
        if expires_at < now - 30:
            raise TokenValidationError(f"{prefix} request expired")
        if expires_at <= issued_at:
            raise TokenValidationError(f"{prefix} expires_at must be greater than issued_at")
        if expires_at - issued_at > self.max_signed_ttl_seconds:
            raise TokenValidationError(
                f"{prefix} ttl exceeds max {self.max_signed_ttl_seconds} seconds"
            )

    def _validate_signer_ttl(self, *, ttl_seconds: int, prefix: str) -> None:
        if ttl_seconds <= 0:
            raise TokenValidationError(f"{prefix} ttl_seconds must be greater than 0")
        if ttl_seconds > self.max_signed_ttl_seconds:
            raise TokenValidationError(
                f"{prefix} ttl_seconds exceeds max {self.max_signed_ttl_seconds} seconds"
            )

    def _validate_delegation_ttl(self, *, ttl_seconds: int, prefix: str) -> None:
        if ttl_seconds <= 0:
            raise TokenValidationError(f"{prefix} ttl_seconds must be greater than 0")
        if ttl_seconds > self.max_delegation_ttl_seconds:
            raise TokenValidationError(
                f"{prefix} ttl_seconds exceeds max {self.max_delegation_ttl_seconds} seconds"
            )

    def _consume_signed_nonce(
        self,
        *,
        agent_id: str,
        nonce: str,
        expires_at: int,
        now: int,
        cache: ExpiringSet[tuple[str, str]],
    ) -> None:
        cache.cleanup(now=now)
        nonce_key = (agent_id, nonce)
        if cache.contains(nonce_key):
            raise TokenValidationError("nonce already used")
        cache.add(key=nonce_key, expires_at=expires_at, now=now)

    def _require_registered_platform(self, platform_aud: str) -> PlatformRecord:
        platform = self.platforms.get(platform_aud)
        if platform is None or platform.status != "active":
            raise PermissionError("platform is not registered")
        return platform

    def issue_full_attestation(
        self,
        *,
        agent_id: str,
        platform_aud: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_agent: str,
    ) -> dict[str, Any]:
        self._sync_state()
        record = self.require_agent(agent_id)
        self._require_registered_platform(platform_aud)

        now = now_ts()
        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="full attestation issue",
        )
        self._consume_signed_nonce(
            agent_id=agent_id,
            nonce=nonce,
            expires_at=expires_at,
            now=now,
            cache=self.used_full_issue_nonces,
        )

        payload = build_full_attestation_issue_payload(
            agent_id=agent_id,
            platform_aud=platform_aud,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        verify_detached(payload, signature_by_agent, load_public_key(agent_id))

        result = {
            "agent_id": agent_id,
            "platform_aud": platform_aud,
            "full_identity_attestation": self._issue_full_identity_attestation(record, aud=platform_aud),
        }
        self._append_audit_event(
            actor_type="agent",
            actor_id=agent_id,
            agent_id=agent_id,
            event_type="full_attestation_issue",
            resource_type="platform",
            resource_id=platform_aud,
        )
        return result

    def _resolve_platform_key(self, *, kid: str) -> tuple[PlatformRecord, PlatformKeyRecord]:
        for platform in self.platforms.values():
            key = platform.keys.get(kid)
            if key is not None and key.status == "active":
                return platform, key
        raise TokenValidationError("unknown platform key id")

    def _cleanup_seen_platform_jtis(self, now: int) -> None:
        self.seen_platform_jtis.cleanup(now=now)

    def _cleanup_platform_events(self, now: int) -> None:
        delete_before = now - self.platform_event_retention_seconds
        for event_key, record in list(self.platform_events.items()):
            if record.ingested_at < delete_before:
                self.platform_events.pop(event_key, None)

    def _apply_negative_event_to_profile(self, event: PlatformNegativeEvent) -> None:
        profile = self._ensure_identity_profile(event.agent_id)
        now = now_ts()

        severity_weight = min(max(event.severity, 1), 5) / 5.0
        next_risk = min(1.0, profile.risk_score + 0.1 * severity_weight)
        profile.risk_score = round(next_risk, 4)

        labels = set(profile.labels)
        labels.add("abuse-reported")
        if event.category == "fraud":
            labels.add("fraud-risk")
        if event.category == "spam":
            labels.add("spam-risk")
        if event.category == "policy_violation":
            labels.add("policy-risk")
        profile.labels = sorted(labels)

        counts = profile.metadata.get("platform_event_counts")
        if not isinstance(counts, dict):
            counts = {}
        current_value = counts.get(event.category, 0)
        counts[event.category] = int(current_value) + 1
        counts["total"] = int(counts.get("total", 0)) + 1
        profile.metadata["platform_event_counts"] = counts

        profile.summary = (
            f"negative events={counts['total']},"
            f" latest={event.category}@{event.platform_aud}"
        )
        profile.version += 1
        profile.updated_at = now

    def ingest_platform_events(self, *, event_token: str) -> dict[str, Any]:
        self._sync_state()
        decoded = decode_jws(event_token)
        header_typ = decoded.header.get("typ")
        if header_typ != "rare.platform-event+jws":
            raise TokenValidationError("invalid platform event token typ")
        kid = decoded.header.get("kid")
        if not isinstance(kid, str):
            raise TokenValidationError("platform event key id missing")

        platform, platform_key = self._resolve_platform_key(kid=kid)
        public_key = load_public_key(platform_key.public_key_b64)
        verified = verify_jws(event_token, public_key)
        payload = verified.payload

        if payload.get("typ") != "rare.platform-event":
            raise TokenValidationError("invalid platform event payload typ")
        if payload.get("ver") != 1:
            raise TokenValidationError("unsupported platform event version")
        if payload.get("aud") != "rare.identity-library":
            raise TokenValidationError("platform event aud mismatch")
        if payload.get("iss") != platform.platform_id:
            raise TokenValidationError("platform event issuer mismatch")

        now = now_ts()
        self._cleanup_platform_events(now)
        iat = payload.get("iat")
        exp = payload.get("exp")
        if not isinstance(iat, int) or not isinstance(exp, int):
            raise TokenValidationError("platform event timestamps must be integers")
        if iat > now + 30:
            raise TokenValidationError("platform event iat too far in future")
        if exp < now - 30:
            raise TokenValidationError("platform event expired")

        jti = payload.get("jti")
        if not isinstance(jti, str):
            raise TokenValidationError("platform event jti missing")
        self._cleanup_seen_platform_jtis(now)
        replay_key = (platform.platform_id, jti)
        if self.seen_platform_jtis.contains(replay_key):
            raise TokenValidationError("platform event jti replay detected")
        self.seen_platform_jtis.add(key=replay_key, expires_at=exp, now=now)

        events = payload.get("events")
        if not isinstance(events, list):
            raise TokenValidationError("platform event events must be a list")

        ingested = 0
        deduped = 0
        for item in events:
            if not isinstance(item, dict):
                raise TokenValidationError("platform event item must be object")
            event_id = item.get("event_id")
            agent_id = item.get("agent_id")
            category = item.get("category")
            if not isinstance(event_id, str) or not event_id:
                raise TokenValidationError("platform event_id required")
            if not isinstance(agent_id, str) or not agent_id:
                raise TokenValidationError("platform agent_id required")
            if category not in NEGATIVE_EVENT_CATEGORIES:
                raise TokenValidationError("unsupported platform event category")

            self.require_agent(agent_id)
            event_key = (platform.platform_id, event_id)
            if event_key in self.platform_events:
                deduped += 1
                continue

            severity = item.get("severity", 1)
            if not isinstance(severity, int) or severity < 1 or severity > 5:
                raise TokenValidationError("platform event severity must be integer 1..5")
            outcome = item.get("outcome", "")
            if not isinstance(outcome, str):
                raise TokenValidationError("platform event outcome must be string")
            occurred_at = item.get("occurred_at", now)
            if not isinstance(occurred_at, int):
                raise TokenValidationError("platform event occurred_at must be integer")
            evidence_hash = item.get("evidence_hash")
            if evidence_hash is not None and not isinstance(evidence_hash, str):
                raise TokenValidationError("platform event evidence_hash must be string")

            record = PlatformNegativeEvent(
                platform_id=platform.platform_id,
                platform_aud=platform.platform_aud,
                event_id=event_id,
                agent_id=agent_id,
                category=category,
                severity=severity,
                outcome=outcome,
                occurred_at=occurred_at,
                evidence_hash=evidence_hash,
                ingested_at=now,
            )
            self._ensure_capacity(
                self.platform_events,
                key=event_key,
                max_items=self.max_platform_events,
                resource_name="platform event",
            )
            self.platform_events[event_key] = record
            self._apply_negative_event_to_profile(record)
            ingested += 1
        self._append_audit_event(
            actor_type="platform",
            actor_id=platform.platform_id,
            agent_id=None,
            event_type="platform_events_ingest",
            resource_type="platform",
            resource_id=platform.platform_aud,
            metadata={"ingested": ingested, "deduped": deduped},
        )

        return {
            "platform_id": platform.platform_id,
            "platform_aud": platform.platform_aud,
            "accepted_count": ingested,
            "deduped_count": deduped,
        }
