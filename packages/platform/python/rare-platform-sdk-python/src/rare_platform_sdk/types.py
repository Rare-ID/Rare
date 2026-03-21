from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


IdentityMode = Literal["public", "full"]
IdentityLevel = Literal["L0", "L1", "L2"]
EffectiveLevel = Literal["L0", "L1", "L2"]
KeyResolver = Callable[[str], Ed25519PublicKey | None]


@dataclass(frozen=True)
class AuthChallenge:
    nonce: str
    aud: str
    issued_at: int
    expires_at: int


@dataclass(frozen=True)
class PlatformSession:
    session_token: str
    agent_id: str
    session_pubkey: str
    identity_mode: IdentityMode
    raw_level: IdentityLevel
    effective_level: EffectiveLevel
    display_name: str
    aud: str
    created_at: int
    expires_at: int


@dataclass(frozen=True)
class AuthCompleteInput:
    nonce: str
    agent_id: str
    session_pubkey: str
    delegation_token: str
    signature_by_session: str
    public_identity_attestation: str | None = None
    full_identity_attestation: str | None = None


@dataclass(frozen=True)
class AuthCompleteResult:
    session_token: str
    agent_id: str
    level: EffectiveLevel
    raw_level: IdentityLevel
    identity_mode: IdentityMode
    display_name: str
    session_pubkey: str


@dataclass(frozen=True)
class VerifyActionInput:
    session_token: str
    action: str
    action_payload: dict[str, Any]
    nonce: str
    issued_at: int
    expires_at: int
    signature_by_session: str


@dataclass(frozen=True)
class VerifiedActionContext:
    session: PlatformSession
    action: str
    action_payload: dict[str, Any]


@dataclass(frozen=True)
class RarePlatformEventItem:
    event_id: str
    agent_id: str
    category: Literal["spam", "fraud", "abuse", "policy_violation"]
    severity: int
    outcome: str
    occurred_at: int
    evidence_hash: str | None = None


@dataclass(frozen=True)
class IngestEventsInput:
    event_token: str | None = None
    platform_id: str | None = None
    kid: str | None = None
    private_key_pem: str | None = None
    jti: str | None = None
    events: list[RarePlatformEventItem] | None = None
    issued_at: int | None = None
    expires_at: int | None = None


@dataclass(frozen=True)
class IngestEventsResult:
    event_token: str
    response: dict[str, Any]


class ChallengeStore(Protocol):
    async def set(self, challenge: AuthChallenge) -> None:
        ...

    async def consume(self, nonce: str) -> AuthChallenge | None:
        ...


class ReplayStore(Protocol):
    async def claim(self, key: str, expires_at: int) -> bool:
        ...


class SessionStore(Protocol):
    async def save(self, session: PlatformSession) -> None:
        ...

    async def get(self, session_token: str) -> PlatformSession | None:
        ...


class RarePlatformKit(Protocol):
    async def issue_challenge(self, aud: str | None = None) -> AuthChallenge:
        ...

    async def complete_auth(self, input: AuthCompleteInput) -> AuthCompleteResult:
        ...

    async def verify_action(self, input: VerifyActionInput) -> VerifiedActionContext:
        ...

    async def ingest_negative_events(self, input: IngestEventsInput) -> IngestEventsResult:
        ...


@dataclass(frozen=True)
class RarePlatformKitConfig:
    aud: str
    challenge_store: ChallengeStore
    replay_store: ReplayStore
    session_store: SessionStore
    rare_api_client: Any | None = None
    key_resolver: KeyResolver | None = None
    initial_jwks: dict[str, Any] | None = None
    rare_signer_public_key_b64: str | None = None
    challenge_ttl_seconds: int = 120
    session_ttl_seconds: int = 3600
    max_signed_ttl_seconds: int = 300
    clock_skew_seconds: int = 30
