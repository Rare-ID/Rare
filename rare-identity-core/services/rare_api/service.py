from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from rare_identity_protocol import (
    TokenValidationError,
    ExpiringMap,
    ExpiringSet,
    build_action_payload,
    build_agent_auth_payload,
    build_auth_challenge_payload,
    build_full_attestation_issue_payload,
    build_platform_grant_payload,
    build_register_payload,
    build_set_name_payload,
    build_upgrade_request_payload,
    decode_jws,
    generate_ed25519_keypair,
    generate_nonce,
    issue_full_identity_attestation,
    issue_public_identity_attestation,
    issue_rare_delegation,
    load_private_key,
    load_public_key,
    now_ts,
    public_key_to_b64,
    sign_detached,
    validate_name,
    verify_detached,
    verify_jws,
)


LEVELS = {"L0", "L1", "L2"}
NEGATIVE_EVENT_CATEGORIES = {"spam", "fraud", "abuse", "policy_violation"}
SOCIAL_PROVIDERS = {"x", "github"}
MAX_SIGNED_TTL_SECONDS = 300
MAX_DELEGATION_TTL_SECONDS = 3600
DEFAULT_REPLAY_CACHE_CAPACITY = 50_000
DEFAULT_SESSION_CACHE_CAPACITY = 20_000
DEFAULT_CHALLENGE_CACHE_CAPACITY = 10_000
DEFAULT_HOSTED_MANAGEMENT_TOKEN_TTL_SECONDS = 30 * 24 * 3600


@dataclass
class AgentRecord:
    agent_id: str
    name: str
    level: str = "L0"
    owner_id: str | None = None
    org_id: str | None = None
    twitter: dict[str, str] | None = None
    github: dict[str, str] | None = None
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
class AgentPlatformGrant:
    agent_id: str
    platform_aud: str
    granted_at: int
    revoked_at: int | None = None


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
    email_verified_at: int | None = None
    social_provider: str | None = None
    social_verified_at: int | None = None
    social_account: dict[str, Any] | None = None
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
        allow_local_upgrade_shortcuts: bool = False,
        admin_token: str | None = None,
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
        self.allow_local_upgrade_shortcuts = allow_local_upgrade_shortcuts
        self.dns_txt_resolver = dns_txt_resolver or (lambda _name: [])
        self._admin_token = admin_token

        self.agents: dict[str, AgentRecord] = {}
        self.hosted_agent_private_keys: dict[str, Ed25519PrivateKey] = {}
        self.hosted_management_tokens: dict[str, HostedManagementTokenRecord] = {}
        self.hosted_session_keys: ExpiringMap[str, HostedSessionRecord] = ExpiringMap(
            capacity=session_cache_capacity
        )

        self.name_change_events: dict[str, list[int]] = {}
        self.used_name_nonces: ExpiringSet[str] = ExpiringSet(capacity=replay_cache_capacity)
        self.used_action_nonces: ExpiringSet[tuple[str, str]] = ExpiringSet(capacity=replay_cache_capacity)
        self.used_agent_auth_nonces: ExpiringSet[tuple[str, str]] = ExpiringSet(capacity=replay_cache_capacity)
        self.used_platform_grant_nonces: ExpiringSet[tuple[str, str]] = ExpiringSet(
            capacity=replay_cache_capacity
        )
        self.used_full_issue_nonces: ExpiringSet[tuple[str, str]] = ExpiringSet(
            capacity=replay_cache_capacity
        )
        self.seen_upgrade_nonces: ExpiringSet[tuple[str, str]] = ExpiringSet(capacity=replay_cache_capacity)

        self.identity_profiles: dict[str, IdentityProfileRecord] = {}
        self.identity_subscriptions: dict[str, dict[str, Any]] = {}
        self.platforms: dict[str, PlatformRecord] = {}
        self.platform_register_challenges: ExpiringMap[str, PlatformRegisterChallenge] = ExpiringMap(
            capacity=challenge_cache_capacity
        )
        self.agent_platform_grants: dict[tuple[str, str], AgentPlatformGrant] = {}
        self.platform_events: dict[tuple[str, str], PlatformNegativeEvent] = {}
        self.seen_platform_jtis: ExpiringSet[tuple[str, str]] = ExpiringSet(capacity=replay_cache_capacity)
        self.upgrade_requests: dict[str, UpgradeRequestRecord] = {}
        self.upgrade_magic_links: ExpiringMap[str, UpgradeMagicLinkRecord] = ExpiringMap(
            capacity=challenge_cache_capacity
        )
        self.upgrade_oauth_states: ExpiringMap[str, UpgradeOAuthStateRecord] = ExpiringMap(
            capacity=challenge_cache_capacity
        )

        self.identity_keys: dict[str, SigningKey] = {}
        self.active_identity_kid = self._generate_identity_signing_key()

        signer_priv_b64, _ = generate_ed25519_keypair()
        signer_kid = f"rare-signer-{datetime.now(UTC).strftime('%Y-%m')}"
        signer_now = now_ts()
        self.rare_signer_key = SigningKey(
            kid=signer_kid,
            private_key=load_private_key(signer_priv_b64),
            created_at=signer_now,
            retire_at=signer_now + 365 * 24 * 3600,
        )

    def _generate_identity_signing_key(self) -> str:
        private_b64, _ = generate_ed25519_keypair()
        kid = f"rare-{datetime.now(UTC).strftime('%Y-%m')}"
        created_at = now_ts()
        self.identity_keys[kid] = SigningKey(
            kid=kid,
            private_key=load_private_key(private_b64),
            created_at=created_at,
            retire_at=created_at + 365 * 24 * 3600,
        )
        return kid

    def get_jwks(self) -> dict:
        keys = []
        for key in self.identity_keys.values():
            keys.append(
                {
                    "kid": key.kid,
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": public_key_to_b64(key.private_key.public_key()),
                    "retire_at": key.retire_at,
                }
            )
        return {"issuer": self.issuer, "keys": keys}

    def get_identity_public_key(self, kid: str) -> Ed25519PublicKey | None:
        key = self.identity_keys.get(kid)
        return key.private_key.public_key() if key else None

    def get_rare_signer_public_key(self) -> Ed25519PublicKey:
        return self.rare_signer_key.private_key.public_key()

    def _issue_public_identity_attestation(self, record: AgentRecord) -> str:
        return issue_public_identity_attestation(
            agent_id=record.agent_id,
            level=record.level,
            name=record.name,
            kid=self.active_identity_kid,
            signer_private_key=self.identity_keys[self.active_identity_kid].private_key,
            ttl_seconds=self.attestation_ttl_seconds,
            jti=generate_nonce(12),
            name_updated_at=record.name_updated_at,
            owner_id=record.owner_id,
            org_id=record.org_id,
            twitter=record.twitter,
            github=record.github,
        )

    def _issue_full_identity_attestation(self, record: AgentRecord, *, aud: str) -> str:
        return issue_full_identity_attestation(
            agent_id=record.agent_id,
            level=record.level,
            name=record.name,
            aud=aud,
            kid=self.active_identity_kid,
            signer_private_key=self.identity_keys[self.active_identity_kid].private_key,
            ttl_seconds=self.attestation_ttl_seconds,
            jti=generate_nonce(12),
            name_updated_at=record.name_updated_at,
            owner_id=record.owner_id,
            org_id=record.org_id,
            twitter=record.twitter,
            github=record.github,
        )

    def _ensure_identity_profile(self, agent_id: str) -> IdentityProfileRecord:
        profile = self.identity_profiles.get(agent_id)
        if profile is None:
            profile = IdentityProfileRecord(agent_id=agent_id)
            self.identity_profiles[agent_id] = profile
        return profile

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

    def get_identity_profile(self, *, agent_id: str) -> dict[str, Any]:
        self.require_agent(agent_id)
        return self._profile_to_dict(self._ensure_identity_profile(agent_id))

    def upsert_identity_profile(self, *, agent_id: str, patch: dict[str, Any]) -> dict[str, Any]:
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
        return self._profile_to_dict(profile)

    def create_identity_subscription(
        self,
        *,
        name: str,
        webhook_url: str,
        fields: list[str],
        event_types: list[str],
    ) -> dict[str, Any]:
        if not name.strip():
            raise TokenValidationError("subscription name cannot be empty")
        if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
            raise TokenValidationError("webhook_url must be http/https")

        subscription_id = generate_nonce(8)
        record = {
            "subscription_id": subscription_id,
            "name": name,
            "webhook_url": webhook_url,
            "fields": fields,
            "event_types": event_types,
            "created_at": now_ts(),
        }
        self.identity_subscriptions[subscription_id] = record
        return record

    def list_identity_subscriptions(self) -> list[dict[str, Any]]:
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
        normalized_name = validate_name(name) if name else f"Agent-{generate_nonce(5)[:8]}"
        hosted_management_token: str | None = None
        hosted_management_token_expires_at: int | None = None

        if key_mode == "hosted-signer":
            if agent_public_key is not None:
                raise TokenValidationError("agent_public_key is not allowed in hosted-signer mode")
            generated_private_key, generated_public_key = generate_ed25519_keypair()
            agent_id = generated_public_key
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
            existing = AgentRecord(agent_id=agent_id, name=normalized_name)
            self.agents[agent_id] = existing

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
        return response

    def issue_public_attestation(self, *, agent_id: str) -> dict:
        record = self.require_agent(agent_id)
        return {
            "agent_id": record.agent_id,
            "profile": {"name": record.name},
            "public_identity_attestation": self._issue_public_identity_attestation(record),
        }

    def refresh_attestation(self, *, agent_id: str) -> dict:
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
        for request in self.upgrade_requests.values():
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
        return {
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
        self.hosted_management_tokens[agent_id] = HostedManagementTokenRecord(
            token_hash=self._hash_token(token),
            issued_at=now,
            expires_at=expires_at,
        )
        return token, expires_at

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

    def rotate_hosted_management_token(self, *, agent_id: str, token: str) -> dict[str, Any]:
        self.authorize_hosted_management(agent_id=agent_id, token=token)
        next_token, expires_at = self._issue_hosted_management_token(agent_id=agent_id)
        return {
            "agent_id": agent_id,
            "hosted_management_token": next_token,
            "hosted_management_token_expires_at": expires_at,
        }

    def revoke_hosted_management_token(self, *, agent_id: str, token: str) -> dict[str, Any]:
        self.authorize_hosted_management(agent_id=agent_id, token=token)
        self.hosted_management_tokens.pop(agent_id, None)
        now = now_ts()
        self.hosted_session_keys.cleanup(now=now)
        for session_key, session in list(self.hosted_session_keys.items()):
            if session.agent_id == agent_id:
                self.hosted_session_keys.discard(session_key)
        return {
            "agent_id": agent_id,
            "revoked": True,
            "revoked_at": now,
        }

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

        return {
            "name": record.name,
            "updated_at": record.name_updated_at,
            "public_identity_attestation": self._issue_public_identity_attestation(record),
        }

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

    def _cleanup_platform_grant_nonce_cache(self, now: int) -> None:
        self.used_platform_grant_nonces.cleanup(now=now)

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

        delegation = issue_rare_delegation(
            agent_id=agent_id,
            session_pubkey=session_pubkey,
            aud=aud,
            scope=scope,
            signer_private_key=self.rare_signer_key.private_key,
            kid=self.rare_signer_key.kid,
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

        return {
            "agent_id": agent_id,
            "session_pubkey": session_pubkey,
            "delegation_token": delegation,
            "signature_by_session": signature,
            "session_expires_at": session_exp,
        }

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

        return {
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

    def sign_delegation(
        self,
        *,
        agent_id: str,
        session_pubkey: str,
        aud: str,
        scope: Iterable[str],
        ttl_seconds: int,
    ) -> dict:
        self.require_agent(agent_id)
        load_public_key(session_pubkey)
        self._validate_delegation_ttl(ttl_seconds=ttl_seconds, prefix="sign_delegation")

        token = issue_rare_delegation(
            agent_id=agent_id,
            session_pubkey=session_pubkey,
            aud=aud,
            scope=scope,
            ttl_seconds=ttl_seconds,
            signer_private_key=self.rare_signer_key.private_key,
            kid=self.rare_signer_key.kid,
            jti=generate_nonce(12),
        )
        return {"delegation_token": token}

    def sign_platform_grant(
        self,
        *,
        agent_id: str,
        platform_aud: str,
        ttl_seconds: int = 120,
    ) -> dict[str, Any]:
        self.require_agent(agent_id)
        private_key = self._require_hosted_agent_private_key(agent_id)
        self._validate_signer_ttl(ttl_seconds=ttl_seconds, prefix="sign_platform_grant")
        issued_at = now_ts()
        expires_at = issued_at + ttl_seconds
        nonce = generate_nonce(10)
        sign_input = build_platform_grant_payload(
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

    def sign_full_attestation_issue(
        self,
        *,
        agent_id: str,
        platform_aud: str,
        ttl_seconds: int = 120,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        record = self.require_agent(agent_id)
        if target_level not in {"L1", "L2"}:
            raise TokenValidationError("target_level must be L1 or L2")
        if not request_id.strip():
            raise TokenValidationError("request_id is required")
        if request_id in self.upgrade_requests:
            raise TokenValidationError("request_id already exists")

        if target_level == "L2" and record.level not in {"L1", "L2"}:
            raise PermissionError("L2 upgrade requires current level L1 or higher")

        now = now_ts()
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
        if target_level == "L1":
            if not isinstance(contact_email, str) or not contact_email.strip():
                raise TokenValidationError("contact_email is required for L1 upgrade")
            _, contact_email_hash, contact_email_masked = self._validate_contact_email(contact_email)

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
            last_transition_at=now,
        )
        self.upgrade_requests[request_id] = request
        return self._upgrade_status_payload(request)

    def get_upgrade_request(self, *, upgrade_request_id: str) -> dict[str, Any]:
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
        now = now_ts()
        self._cleanup_upgrade_magic_links(now)
        request = self._require_upgrade_request(upgrade_request_id)
        if request.target_level != "L1":
            raise TokenValidationError("email link is only available for L1 upgrade")
        if request.status not in {"human_pending", "requested"}:
            raise TokenValidationError("upgrade request is not waiting for email verification")
        if not request.contact_email_hash:
            raise TokenValidationError("contact_email missing in upgrade request")

        raw_token = generate_nonce(24)
        token_hash = self._sha256_hex(raw_token)
        record = UpgradeMagicLinkRecord(
            token_hash=token_hash,
            upgrade_request_id=upgrade_request_id,
            expires_at=now + self.magic_link_ttl_seconds,
        )
        self.upgrade_magic_links.set(
            key=token_hash,
            value=record,
            expires_at=record.expires_at,
            now=now,
        )
        response = {
            "upgrade_request_id": upgrade_request_id,
            "sent": True,
            "expires_at": record.expires_at,
        }
        if self.allow_local_upgrade_shortcuts:
            # local stub mode only: expose raw token for tests/dev integration
            response["token"] = raw_token
            response["magic_link"] = f"https://rare.local/v1/upgrades/l1/email/verify?token={raw_token}"
        return response

    def _apply_upgraded_level(self, request: UpgradeRequestRecord) -> dict[str, Any]:
        record = self.require_agent(request.agent_id)
        profile = self._ensure_identity_profile(request.agent_id)
        now = now_ts()

        if request.target_level == "L1":
            if not request.contact_email_hash:
                raise TokenValidationError("L1 upgrade missing email verification proof")
            record.owner_id = f"email:{request.contact_email_hash}"
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
            if request.social_provider == "x":
                user_id = str(social_account.get("id") or social_account.get("user_id") or "").strip()
                handle = str(social_account.get("handle") or social_account.get("login") or "").strip()
                if not user_id or not handle:
                    raise TokenValidationError("x social account data missing")
                record.twitter = {"user_id": user_id, "handle": handle}
            elif request.social_provider == "github":
                github_id = str(social_account.get("id") or "").strip()
                login = str(social_account.get("login") or "").strip()
                if not github_id or not login:
                    raise TokenValidationError("github social account data missing")
                record.github = {"id": github_id, "login": login}
            record.level = "L2"
            labels = set(profile.labels)
            if request.social_provider == "x":
                labels.add("twitter-linked")
            if request.social_provider == "github":
                labels.add("github-linked")
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
        request.status = "verified"
        request.last_transition_at = now
        link.used_at = now
        return self._apply_upgraded_level(request)

    def start_upgrade_l2_social(self, *, upgrade_request_id: str, provider: str) -> dict[str, Any]:
        normalized_provider = provider.strip().lower()
        if normalized_provider not in SOCIAL_PROVIDERS:
            raise TokenValidationError("provider must be x or github")
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
        return {
            "upgrade_request_id": upgrade_request_id,
            "provider": normalized_provider,
            "state": state,
            "expires_at": state_record.expires_at,
            "authorize_url": (
                f"https://oauth.{normalized_provider}.local/authorize"
                f"?state={state}&client_id=rare-dev"
            ),
        }

    def social_callback_upgrade_l2(
        self,
        *,
        provider: str,
        code: str,
        state: str,
    ) -> dict[str, Any]:
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
        if not code.strip():
            raise TokenValidationError("oauth code is required")

        request = self._require_upgrade_request(state_record.upgrade_request_id)
        if request.target_level != "L2":
            raise TokenValidationError("upgrade request target is not L2")
        state_record.used_at = now

        if normalized_provider == "x":
            request.social_account = {
                "id": self._sha256_hex(code)[:12],
                "handle": f"x_{self._sha256_hex(code)[:8]}",
            }
        else:
            request.social_account = {
                "id": self._sha256_hex(code)[:12],
                "login": f"gh_{self._sha256_hex(code)[:8]}",
            }
        request.social_provider = normalized_provider
        request.social_verified_at = now
        request.status = "verified"
        request.last_transition_at = now
        return self._apply_upgraded_level(request)

    def complete_upgrade_l2_social(
        self,
        *,
        upgrade_request_id: str,
        provider: str,
        provider_user_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.allow_local_upgrade_shortcuts:
            raise PermissionError("local social complete shortcut is disabled")
        normalized_provider = provider.strip().lower()
        if normalized_provider not in SOCIAL_PROVIDERS:
            raise TokenValidationError("provider must be x or github")
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
        return self._apply_upgraded_level(request)

    def _cleanup_platform_register_challenges(self, now: int) -> None:
        self.platform_register_challenges.cleanup(now=now)

    def issue_platform_register_challenge(self, *, platform_aud: str, domain: str) -> dict[str, Any]:
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
        return {
            "challenge_id": challenge.challenge_id,
            "txt_name": challenge.txt_name,
            "txt_value": challenge.txt_value,
            "expires_at": challenge.expires_at,
        }

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
        self.platforms[platform_aud] = record
        challenge.status = "consumed"

        return {
            "platform_id": record.platform_id,
            "platform_aud": record.platform_aud,
            "domain": record.domain,
            "status": record.status,
        }

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

    def _consume_platform_grant_nonce(
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

    def create_platform_grant(
        self,
        *,
        agent_id: str,
        platform_aud: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_agent: str,
    ) -> dict[str, Any]:
        self.require_agent(agent_id)
        self._require_registered_platform(platform_aud)
        now = now_ts()
        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="platform grant",
        )
        self._consume_platform_grant_nonce(
            agent_id=agent_id,
            nonce=nonce,
            expires_at=expires_at,
            now=now,
            cache=self.used_platform_grant_nonces,
        )

        payload = build_platform_grant_payload(
            agent_id=agent_id,
            platform_aud=platform_aud,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        verify_detached(payload, signature_by_agent, load_public_key(agent_id))

        grant_key = (agent_id, platform_aud)
        existing = self.agent_platform_grants.get(grant_key)
        if existing is None:
            grant = AgentPlatformGrant(
                agent_id=agent_id,
                platform_aud=platform_aud,
                granted_at=now,
                revoked_at=None,
            )
            self.agent_platform_grants[grant_key] = grant
        else:
            existing.granted_at = now
            existing.revoked_at = None
            grant = existing

        return {
            "agent_id": grant.agent_id,
            "platform_aud": grant.platform_aud,
            "status": "active",
            "granted_at": grant.granted_at,
            "revoked_at": grant.revoked_at,
        }

    def revoke_platform_grant(
        self,
        *,
        agent_id: str,
        platform_aud: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_agent: str,
    ) -> dict[str, Any]:
        self.require_agent(agent_id)
        now = now_ts()
        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="platform grant revoke",
        )
        self._consume_platform_grant_nonce(
            agent_id=agent_id,
            nonce=nonce,
            expires_at=expires_at,
            now=now,
            cache=self.used_platform_grant_nonces,
        )

        payload = build_platform_grant_payload(
            agent_id=agent_id,
            platform_aud=platform_aud,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        verify_detached(payload, signature_by_agent, load_public_key(agent_id))

        grant_key = (agent_id, platform_aud)
        grant = self.agent_platform_grants.get(grant_key)
        if grant is None:
            grant = AgentPlatformGrant(
                agent_id=agent_id,
                platform_aud=platform_aud,
                granted_at=now,
                revoked_at=now,
            )
            self.agent_platform_grants[grant_key] = grant
        else:
            grant.revoked_at = now

        return {
            "agent_id": grant.agent_id,
            "platform_aud": grant.platform_aud,
            "status": "revoked",
            "granted_at": grant.granted_at,
            "revoked_at": grant.revoked_at,
        }

    def list_platform_grants(self, *, agent_id: str) -> dict[str, Any]:
        self.require_agent(agent_id)
        grants: list[dict[str, Any]] = []
        for (grant_agent_id, platform_aud), grant in self.agent_platform_grants.items():
            if grant_agent_id != agent_id:
                continue
            status = "revoked" if grant.revoked_at is not None else "active"
            grants.append(
                {
                    "platform_aud": platform_aud,
                    "status": status,
                    "granted_at": grant.granted_at,
                    "revoked_at": grant.revoked_at,
                }
            )
        grants.sort(key=lambda item: item["platform_aud"])
        return {"agent_id": agent_id, "grants": grants}

    def _require_active_grant(self, *, agent_id: str, platform_aud: str) -> AgentPlatformGrant:
        grant = self.agent_platform_grants.get((agent_id, platform_aud))
        if grant is None or grant.revoked_at is not None:
            raise PermissionError("agent has not granted this platform")
        return grant

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
        record = self.require_agent(agent_id)
        self._require_registered_platform(platform_aud)
        self._require_active_grant(agent_id=agent_id, platform_aud=platform_aud)

        now = now_ts()
        self._validate_signed_window(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            prefix="full attestation issue",
        )
        self._consume_platform_grant_nonce(
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

        return {
            "agent_id": agent_id,
            "platform_aud": platform_aud,
            "full_identity_attestation": self._issue_full_identity_attestation(record, aud=platform_aud),
        }

    def _resolve_platform_key(self, *, kid: str) -> tuple[PlatformRecord, PlatformKeyRecord]:
        for platform in self.platforms.values():
            key = platform.keys.get(kid)
            if key is not None and key.status == "active":
                return platform, key
        raise TokenValidationError("unknown platform key id")

    def _cleanup_seen_platform_jtis(self, now: int) -> None:
        self.seen_platform_jtis.cleanup(now=now)

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
            self.platform_events[event_key] = record
            self._apply_negative_event_to_profile(record)
            ingested += 1

        return {
            "platform_id": platform.platform_id,
            "platform_aud": platform.platform_aud,
            "accepted_count": ingested,
            "deduped_count": deduped,
        }
