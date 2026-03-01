from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from rare_identity_protocol import (
    TokenValidationError,
    build_action_payload,
    build_auth_challenge_payload,
    decode_jws,
    generate_nonce,
    load_public_key,
    now_ts,
    verify_detached,
)
from rare_identity_verifier import (
    verify_delegation_token,
    verify_identity_attestation,
)


LEVEL_RATE_LIMITS = {
    "L0": {
        "post": (2, 60),
        "comment": (5, 60),
    },
    "L1": {
        "post": (10, 60),
        "comment": (20, 60),
    },
    "L2": {
        "post": (30, 60),
        "comment": (60, 60),
    },
}


@dataclass
class ChallengeRecord:
    nonce: str
    aud: str
    issued_at: int
    expires_at: int
    status: str = "issued"


@dataclass
class SessionRecord:
    token: str
    agent_id: str
    session_pubkey: str
    level: str
    display_name: str
    created_at: int
    expires_at: int


@dataclass
class MoltbookService:
    aud: str
    identity_key_resolver: Callable[[str], Ed25519PublicKey | None]
    rare_signer_public_key_provider: Callable[[], Ed25519PublicKey | None]
    challenge_ttl_seconds: int = 120
    session_ttl_seconds: int = 3600
    challenges: dict[str, ChallengeRecord] = field(default_factory=dict)
    seen_delegation_jtis: dict[str, int] = field(default_factory=dict)
    sessions: dict[str, SessionRecord] = field(default_factory=dict)
    action_events: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    used_action_nonces: dict[tuple[str, str], int] = field(default_factory=dict)
    posts: list[dict] = field(default_factory=list)
    comments: list[dict] = field(default_factory=list)

    def issue_challenge(self) -> dict:
        nonce = generate_nonce(18)
        now = now_ts()
        record = ChallengeRecord(
            nonce=nonce,
            aud=self.aud,
            issued_at=now,
            expires_at=now + self.challenge_ttl_seconds,
        )
        self.challenges[nonce] = record
        return {
            "nonce": record.nonce,
            "aud": record.aud,
            "issued_at": record.issued_at,
            "expires_at": record.expires_at,
        }

    def _consume_challenge(self, nonce: str) -> ChallengeRecord:
        record = self.challenges.get(nonce)
        if record is None:
            raise TokenValidationError("unknown challenge nonce")

        if record.status != "issued":
            raise TokenValidationError("challenge nonce already consumed")

        record.status = "consumed"
        now = now_ts()
        if record.expires_at < now - 30:
            record.status = "expired"
            raise TokenValidationError("challenge expired")
        return record

    def _cleanup_seen_jtis(self, now: int) -> None:
        expired = [jti for jti, exp in self.seen_delegation_jtis.items() if exp + 30 < now]
        for jti in expired:
            del self.seen_delegation_jtis[jti]

    def _cleanup_action_nonces(self, now: int) -> None:
        expired = [key for key, exp in self.used_action_nonces.items() if exp + 30 < now]
        for key in expired:
            del self.used_action_nonces[key]

    def complete_auth(
        self,
        *,
        nonce: str,
        agent_id: str,
        session_pubkey: str,
        delegation_token: str,
        signature_by_session: str,
        public_identity_attestation: str | None = None,
        full_identity_attestation: str | None = None,
    ) -> dict:
        challenge = self._consume_challenge(nonce)
        payload = build_auth_challenge_payload(
            aud=challenge.aud,
            nonce=challenge.nonce,
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
        )

        session_public_key = load_public_key(session_pubkey)
        verify_detached(payload, signature_by_session, session_public_key)

        delegation_result = verify_delegation_token(
            delegation_token,
            expected_aud=self.aud,
            required_scope="login",
            rare_signer_public_key=self.rare_signer_public_key_provider(),
        )

        identity_token = full_identity_attestation or public_identity_attestation
        if not identity_token:
            raise TokenValidationError("missing identity attestation")

        decoded_identity = decode_jws(identity_token)
        expected_aud = self.aud if decoded_identity.header.get("typ") == "rare.identity.full+jws" else None
        identity_result = verify_identity_attestation(
            identity_token,
            key_resolver=self.identity_key_resolver,
            expected_aud=expected_aud,
        )

        delegation_payload = delegation_result.payload
        identity_payload = identity_result.payload

        if delegation_payload.get("session_pubkey") != session_pubkey:
            raise TokenValidationError("session pubkey mismatch")

        delegated_agent = delegation_payload.get("agent_id")
        identity_sub = identity_payload.get("sub")
        if agent_id != delegated_agent or agent_id != identity_sub:
            raise TokenValidationError("agent identity triad mismatch")

        now = now_ts()
        self._cleanup_seen_jtis(now)
        jti = delegation_payload.get("jti")
        if isinstance(jti, str):
            if jti in self.seen_delegation_jtis:
                raise TokenValidationError("delegation token replay detected")
            exp = delegation_payload.get("exp")
            if isinstance(exp, int):
                self.seen_delegation_jtis[jti] = exp

        level = identity_payload.get("lvl")
        if level not in LEVEL_RATE_LIMITS:
            raise TokenValidationError("unsupported identity level")

        claims = identity_payload.get("claims")
        display_name = "unknown"
        if isinstance(claims, dict):
            profile = claims.get("profile")
            if isinstance(profile, dict):
                maybe_name = profile.get("name")
                if isinstance(maybe_name, str) and maybe_name.strip():
                    display_name = maybe_name

        session_token = generate_nonce(24)
        session = SessionRecord(
            token=session_token,
            agent_id=agent_id,
            session_pubkey=session_pubkey,
            level=level,
            display_name=display_name,
            created_at=now,
            expires_at=now + self.session_ttl_seconds,
        )
        self.sessions[session_token] = session

        return {
            "session_token": session_token,
            "agent_id": session.agent_id,
            "level": session.level,
            "display_name": session.display_name,
            "session_pubkey": session.session_pubkey,
        }

    def _require_session(self, token: str) -> SessionRecord:
        session = self.sessions.get(token)
        if session is None:
            raise PermissionError("invalid session token")
        now = now_ts()
        if session.expires_at < now:
            del self.sessions[token]
            raise PermissionError("session expired")
        return session

    def _enforce_rate_limit(self, *, agent_id: str, level: str, action: str) -> None:
        limit, window_seconds = LEVEL_RATE_LIMITS[level][action]
        now = now_ts()
        key = (agent_id, action)
        events = self.action_events.setdefault(key, [])
        threshold = now - window_seconds
        events[:] = [ts for ts in events if ts >= threshold]
        if len(events) >= limit:
            raise PermissionError(f"rate limit exceeded for {action} at level {level}")
        events.append(now)

    def _verify_action_signature(
        self,
        *,
        session: SessionRecord,
        action: str,
        action_payload: dict,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_session: str,
    ) -> None:
        now = now_ts()
        self._cleanup_action_nonces(now)

        if issued_at > now + 30:
            raise TokenValidationError("action issued_at too far in future")
        if expires_at < now - 30:
            raise TokenValidationError("action expired")
        if expires_at <= issued_at:
            raise TokenValidationError("action expires_at must be greater than issued_at")

        nonce_key = (session.token, nonce)
        if nonce_key in self.used_action_nonces:
            raise TokenValidationError("action nonce already consumed")
        self.used_action_nonces[nonce_key] = expires_at

        signing_input = build_action_payload(
            aud=self.aud,
            session_token=session.token,
            action=action,
            action_payload=action_payload,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )

        session_public_key = load_public_key(session.session_pubkey)
        verify_detached(signing_input, signature_by_session, session_public_key)

    def create_post(
        self,
        *,
        session_token: str,
        content: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_session: str,
    ) -> dict:
        session = self._require_session(session_token)
        self._verify_action_signature(
            session=session,
            action="post",
            action_payload={"content": content},
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
            signature_by_session=signature_by_session,
        )
        self._enforce_rate_limit(agent_id=session.agent_id, level=session.level, action="post")

        post = {
            "id": f"post-{len(self.posts) + 1}",
            "agent_id": session.agent_id,
            "display_name": session.display_name,
            "level": session.level,
            "content": content,
            "visibility": "downranked" if session.level == "L0" else "normal",
            "created_at": now_ts(),
        }
        self.posts.append(post)
        return post

    def create_comment(
        self,
        *,
        session_token: str,
        post_id: str,
        content: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
        signature_by_session: str,
    ) -> dict:
        session = self._require_session(session_token)
        self._verify_action_signature(
            session=session,
            action="comment",
            action_payload={"post_id": post_id, "content": content},
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
            signature_by_session=signature_by_session,
        )
        self._enforce_rate_limit(agent_id=session.agent_id, level=session.level, action="comment")

        if not any(post["id"] == post_id for post in self.posts):
            raise KeyError("post not found")

        comment = {
            "id": f"comment-{len(self.comments) + 1}",
            "post_id": post_id,
            "agent_id": session.agent_id,
            "display_name": session.display_name,
            "level": session.level,
            "content": content,
            "created_at": now_ts(),
        }
        self.comments.append(comment)
        return comment
