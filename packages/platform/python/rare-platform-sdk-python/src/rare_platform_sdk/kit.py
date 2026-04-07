from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, cast

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from rare_identity_protocol import (
    SignatureError,
    TokenValidationError,
    build_action_payload,
    build_auth_challenge_payload,
    generate_nonce,
    load_public_key,
    now_ts,
    sign_jws,
    verify_detached,
)
from rare_identity_verifier import parse_rare_jwks, verify_delegation_token, verify_identity_attestation

from rare_platform_sdk.client import RareApiClient
from rare_platform_sdk.client import RareApiClientError
from rare_platform_sdk.client import extract_rare_signer_public_key_b64_from_jwks
from rare_platform_sdk.env import read_rare_platform_env
from rare_platform_sdk.types import (
    AuthChallenge,
    AuthCompleteInput,
    AuthCompleteResult,
    EffectiveLevel,
    IdentityMode,
    IngestEventsInput,
    IngestEventsResult,
    PlatformSession,
    RarePlatformEventItem,
    RarePlatformKitConfig,
    VerifiedActionContext,
    VerifyActionInput,
)


def _extract_display_name(identity_payload: dict[str, Any]) -> str:
    claims = identity_payload.get("claims")
    if isinstance(claims, dict):
        profile = claims.get("profile")
        if isinstance(profile, dict):
            maybe_name = profile.get("name")
            if isinstance(maybe_name, str) and maybe_name.strip():
                return maybe_name
    return "unknown"


def sign_platform_event_token(
    *,
    platform_id: str,
    kid: str,
    private_key_pem: str,
    jti: str,
    events: list[RarePlatformEventItem],
    issued_at: int | None = None,
    expires_at: int | None = None,
) -> str:
    resolved_issued_at = now_ts() if issued_at is None else issued_at
    resolved_expires_at = (
        resolved_issued_at + 300 if expires_at is None else expires_at
    )
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("private_key_pem must contain an Ed25519 private key")
    payload = {
        "typ": "rare.platform-event",
        "ver": 1,
        "iss": platform_id,
        "aud": "rare.identity-library",
        "iat": resolved_issued_at,
        "exp": resolved_expires_at,
        "jti": jti,
        "events": [asdict(event) for event in events],
    }
    return sign_jws(
        payload=payload,
        private_key=private_key,
        kid=kid,
        typ="rare.platform-event+jws",
    )


class _RarePlatformKitImpl:
    def __init__(self, config: RarePlatformKitConfig) -> None:
        self._config = config
        self._rare_api_client = cast(RareApiClient | None, config.rare_api_client)
        self._key_cache = (
            parse_rare_jwks(config.initial_jwks) if config.initial_jwks is not None else {}
        )
        self._rare_signer_public_key = None
        if config.rare_signer_public_key_b64:
            self._rare_signer_public_key = load_public_key(config.rare_signer_public_key_b64)
        elif config.initial_jwks is not None:
            try:
                self._rare_signer_public_key = load_public_key(
                    extract_rare_signer_public_key_b64_from_jwks(config.initial_jwks)
                )
            except RareApiClientError:
                self._rare_signer_public_key = None

    def _lookup_identity_key(self, kid: str) -> Ed25519PublicKey | None:
        if self._config.key_resolver is not None:
            return self._config.key_resolver(kid)
        return self._key_cache.get(kid)

    async def _hydrate_jwks(self) -> None:
        if self._config.key_resolver is not None or self._rare_api_client is None:
            return
        if self._key_cache:
            return
        self._key_cache.update(parse_rare_jwks(await self._rare_api_client.get_jwks()))

    async def _hydrate_rare_signer_public_key(self) -> None:
        if self._rare_signer_public_key is not None or self._rare_api_client is None:
            return
        signer_b64 = await self._rare_api_client.get_rare_signer_public_key_b64()
        self._rare_signer_public_key = load_public_key(signer_b64)

    async def issue_challenge(self, aud: str | None = None) -> AuthChallenge:
        issued_at = now_ts()
        challenge = AuthChallenge(
            nonce=generate_nonce(18),
            aud=aud or self._config.aud,
            issued_at=issued_at,
            expires_at=issued_at + self._config.challenge_ttl_seconds,
        )
        await self._config.challenge_store.set(challenge)
        return challenge

    async def complete_auth(self, input: AuthCompleteInput) -> AuthCompleteResult:
        challenge = await self._config.challenge_store.consume(input.nonce)
        if challenge is None:
            raise TokenValidationError("unknown challenge nonce")

        now = now_ts()
        if challenge.expires_at < now - self._config.clock_skew_seconds:
            raise TokenValidationError("challenge expired")

        verify_detached(
            build_auth_challenge_payload(
                aud=challenge.aud,
                nonce=challenge.nonce,
                issued_at=challenge.issued_at,
                expires_at=challenge.expires_at,
            ),
            input.signature_by_session,
            load_public_key(input.session_pubkey),
        )

        await self._hydrate_rare_signer_public_key()

        delegation = verify_delegation_token(
            input.delegation_token,
            expected_aud=self._config.aud,
            required_scope="login",
            rare_signer_public_key=self._rare_signer_public_key,
            current_ts=now,
            clock_skew_seconds=self._config.clock_skew_seconds,
        ).payload

        delegated_session_pubkey = delegation.get("session_pubkey")
        if delegated_session_pubkey != input.session_pubkey:
            raise TokenValidationError("session pubkey mismatch")

        await self._hydrate_jwks()

        identity_mode: IdentityMode | None = None
        identity_payload: dict[str, Any] | None = None

        if input.full_identity_attestation:
            try:
                identity_payload = verify_identity_attestation(
                    input.full_identity_attestation,
                    key_resolver=self._lookup_identity_key,
                    expected_aud=self._config.aud,
                    current_ts=now,
                    clock_skew_seconds=self._config.clock_skew_seconds,
                ).payload
                identity_mode = "full"
            except (TokenValidationError, SignatureError):
                identity_payload = None

        if identity_payload is None and input.public_identity_attestation:
            identity_payload = verify_identity_attestation(
                input.public_identity_attestation,
                key_resolver=self._lookup_identity_key,
                current_ts=now,
                clock_skew_seconds=self._config.clock_skew_seconds,
            ).payload
            identity_mode = "public"

        if identity_payload is None or identity_mode is None:
            raise TokenValidationError("missing identity attestation")

        delegated_agent = delegation.get("agent_id")
        identity_sub = identity_payload.get("sub")
        if input.agent_id != delegated_agent or input.agent_id != identity_sub:
            raise TokenValidationError("agent identity triad mismatch")

        delegation_jti = delegation.get("jti")
        delegation_exp = delegation.get("exp")
        if not isinstance(delegation_jti, str) or not isinstance(delegation_exp, int):
            raise TokenValidationError("delegation replay fields missing")

        if not await self._config.replay_store.claim(
            f"delegation:{delegation_jti}", delegation_exp
        ):
            raise TokenValidationError("delegation token replay detected")

        raw_level = identity_payload.get("lvl")
        if raw_level not in {"L0", "L1", "L2"}:
            raise TokenValidationError("unsupported identity level")

        effective_level: EffectiveLevel = (
            "L1" if identity_mode == "public" and raw_level == "L2" else raw_level
        )

        session = PlatformSession(
            session_token=generate_nonce(24),
            agent_id=input.agent_id,
            session_pubkey=input.session_pubkey,
            identity_mode=identity_mode,
            raw_level=raw_level,
            effective_level=effective_level,
            display_name=_extract_display_name(identity_payload),
            aud=self._config.aud,
            created_at=now,
            expires_at=now + self._config.session_ttl_seconds,
        )
        await self._config.session_store.save(session)
        return AuthCompleteResult(
            session_token=session.session_token,
            agent_id=session.agent_id,
            level=session.effective_level,
            raw_level=session.raw_level,
            identity_mode=session.identity_mode,
            display_name=session.display_name,
            session_pubkey=session.session_pubkey,
        )

    async def verify_action(self, input: VerifyActionInput) -> VerifiedActionContext:
        session = await self._config.session_store.get(input.session_token)
        if session is None:
            raise PermissionError("invalid session token")

        now = now_ts()
        if session.expires_at < now:
            raise PermissionError("session expired")
        if input.issued_at > now + self._config.clock_skew_seconds:
            raise TokenValidationError("action issued_at too far in future")
        if input.expires_at < now - self._config.clock_skew_seconds:
            raise TokenValidationError("action expired")
        if input.expires_at <= input.issued_at:
            raise TokenValidationError("action expires_at must be greater than issued_at")
        if input.expires_at - input.issued_at > self._config.max_signed_ttl_seconds:
            raise TokenValidationError(
                f"action ttl exceeds max {self._config.max_signed_ttl_seconds} seconds"
            )
        if not await self._config.replay_store.claim(
            f"action:{session.session_token}:{input.nonce}",
            input.expires_at,
        ):
            raise TokenValidationError("action nonce already consumed")

        verify_detached(
            build_action_payload(
                aud=self._config.aud,
                session_token=session.session_token,
                action=input.action,
                action_payload=input.action_payload,
                nonce=input.nonce,
                issued_at=input.issued_at,
                expires_at=input.expires_at,
            ),
            input.signature_by_session,
            load_public_key(session.session_pubkey),
        )
        return VerifiedActionContext(
            session=session,
            action=input.action,
            action_payload=input.action_payload,
        )

    async def ingest_negative_events(self, input: IngestEventsInput) -> IngestEventsResult:
        if self._rare_api_client is None:
            raise RuntimeError("rare_api_client is required for event ingest")

        event_token = input.event_token
        if event_token is None:
            if (
                input.platform_id is None
                or input.kid is None
                or input.private_key_pem is None
                or input.jti is None
                or input.events is None
            ):
                raise ValueError("missing event signing input")
            event_token = sign_platform_event_token(
                platform_id=input.platform_id,
                kid=input.kid,
                private_key_pem=input.private_key_pem,
                jti=input.jti,
                events=input.events,
                issued_at=input.issued_at,
                expires_at=input.expires_at,
            )

        response = await self._rare_api_client.ingest_platform_events(event_token)
        return IngestEventsResult(event_token=event_token, response=response)


def create_rare_platform_kit(config: RarePlatformKitConfig) -> _RarePlatformKitImpl:
    return _RarePlatformKitImpl(config)


def create_rare_platform_kit_from_env(
    *,
    challenge_store: Any,
    replay_store: Any,
    session_store: Any,
    env: Mapping[str, str] | None = None,
    rare_api_client: RareApiClient | None = None,
    http_client: httpx.AsyncClient | None = None,
    default_headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
    key_resolver: Any | None = None,
    initial_jwks: dict[str, Any] | None = None,
    challenge_ttl_seconds: int = 120,
    session_ttl_seconds: int = 3600,
    max_signed_ttl_seconds: int = 300,
    clock_skew_seconds: int = 30,
) -> _RarePlatformKitImpl:
    resolved_env = read_rare_platform_env(env)
    resolved_client = rare_api_client or RareApiClient(
        rare_base_url=resolved_env.rare_base_url,
        http_client=http_client,
        default_headers=default_headers,
        timeout_seconds=timeout_seconds,
    )
    return create_rare_platform_kit(
        RarePlatformKitConfig(
            aud=resolved_env.platform_aud,
            challenge_store=challenge_store,
            replay_store=replay_store,
            session_store=session_store,
            rare_api_client=resolved_client,
            key_resolver=key_resolver,
            initial_jwks=initial_jwks,
            rare_signer_public_key_b64=resolved_env.rare_signer_public_key_b64,
            challenge_ttl_seconds=challenge_ttl_seconds,
            session_ttl_seconds=session_ttl_seconds,
            max_signed_ttl_seconds=max_signed_ttl_seconds,
            clock_skew_seconds=clock_skew_seconds,
        )
    )
