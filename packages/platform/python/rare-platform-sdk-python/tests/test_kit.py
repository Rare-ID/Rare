from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rare_identity_protocol import (
    build_action_payload,
    build_auth_challenge_payload,
    generate_ed25519_keypair,
    generate_nonce,
    load_private_key,
    now_ts,
    public_key_to_b64,
    sign_detached,
    sign_jws,
)
from rare_platform_sdk import (
    AuthChallenge,
    AuthCompleteInput,
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    IngestEventsInput,
    PlatformSession,
    RareApiClient,
    RarePlatformEventItem,
    RarePlatformKitConfig,
    RedisChallengeStore,
    RedisReplayStore,
    RedisSessionStore,
    VerifyActionInput,
    create_fastapi_rare_router,
    create_rare_platform_kit,
    sign_platform_event_token,
)


def run(coro):
    return asyncio.run(coro)


def new_agent_id() -> str:
    return generate_ed25519_keypair()[1]


def _issue_identity(
    *,
    signer_private_key: Ed25519PrivateKey,
    kid: str,
    typ: str,
    agent_id: str,
    level: str,
    jti: str,
    aud: str | None = None,
    name: str = "neo",
) -> str:
    now = now_ts()
    payload = {
        "typ": "rare.identity",
        "ver": 1,
        "iss": "rare",
        "sub": agent_id,
        "lvl": level,
        "iat": now,
        "exp": now + 3600,
        "jti": jti,
        "claims": {"profile": {"name": name}},
    }
    if aud is not None:
        payload["aud"] = aud
    return sign_jws(payload=payload, private_key=signer_private_key, kid=kid, typ=typ)


def _issue_delegation(
    *,
    signer_private_key: Ed25519PrivateKey,
    agent_id: str,
    session_pubkey: str,
    jti: str,
) -> str:
    now = now_ts()
    return sign_jws(
        payload={
            "typ": "rare.delegation",
            "ver": 1,
            "iss": "rare-signer",
            "act": "delegated_by_rare",
            "aud": "platform",
            "agent_id": agent_id,
            "session_pubkey": session_pubkey,
            "scope": ["login"],
            "iat": now,
            "exp": now + 300,
            "jti": jti,
        },
        private_key=signer_private_key,
        kid="rare-signer-k1",
        typ="rare.delegation+jws",
    )


def setup_kit():
    identity_private_key = Ed25519PrivateKey.generate()
    signer_private_key = Ed25519PrivateKey.generate()
    signer_public_key = public_key_to_b64(signer_private_key.public_key())
    kit = create_rare_platform_kit(
        RarePlatformKitConfig(
            aud="platform",
            challenge_store=InMemoryChallengeStore(),
            replay_store=InMemoryReplayStore(),
            session_store=InMemorySessionStore(),
            rare_signer_public_key_b64=signer_public_key,
            key_resolver=lambda kid: (
                identity_private_key.public_key() if kid == "rare-k1" else None
            ),
        )
    )
    return kit, identity_private_key, signer_private_key


def setup_kit_with_rare_api_client():
    identity_private_key = Ed25519PrivateKey.generate()
    signer_private_key = Ed25519PrivateKey.generate()
    identity_public_key = public_key_to_b64(identity_private_key.public_key())
    signer_public_key = public_key_to_b64(signer_private_key.public_key())

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://rare.example/.well-known/rare-keys.json":
            return httpx.Response(
                200,
                json={
                    "issuer": "rare",
                    "keys": [
                        {
                            "kid": "rare-k1",
                            "kty": "OKP",
                            "crv": "Ed25519",
                            "x": identity_public_key,
                            "rare_role": "identity",
                        },
                        {
                            "kid": "rare-signer-k1",
                            "kty": "OKP",
                            "crv": "Ed25519",
                            "x": signer_public_key,
                            "rare_role": "delegation",
                        },
                    ],
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    rare_api_client = RareApiClient(
        rare_base_url="https://rare.example",
        http_client=http_client,
    )
    kit = create_rare_platform_kit(
        RarePlatformKitConfig(
            aud="platform",
            challenge_store=InMemoryChallengeStore(),
            replay_store=InMemoryReplayStore(),
            session_store=InMemorySessionStore(),
            rare_api_client=rare_api_client,
        )
    )
    return kit, identity_private_key, signer_private_key, rare_api_client, http_client


def create_auth_payload(kit, identity_private_key, signer_private_key, *, agent_id: str, delegation_jti: str):
    challenge = run(kit.issue_challenge("platform"))
    session_private_b64, session_pubkey = generate_ed25519_keypair()
    session_private_key = load_private_key(session_private_b64)
    signature_by_session = sign_detached(
        build_auth_challenge_payload(
            aud=challenge.aud,
            nonce=challenge.nonce,
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
        ),
        session_private_key,
    )
    return {
        "challenge": challenge,
        "session_private_key": session_private_key,
        "session_pubkey": session_pubkey,
        "signature_by_session": signature_by_session,
        "delegation": _issue_delegation(
            signer_private_key=signer_private_key,
            agent_id=agent_id,
            session_pubkey=session_pubkey,
            jti=delegation_jti,
        ),
        "full_wrong_aud": _issue_identity(
            signer_private_key=identity_private_key,
            kid="rare-k1",
            typ="rare.identity.full+jws",
            agent_id=agent_id,
            level="L2",
            aud="other-platform",
            jti="id-full",
        ),
        "public_identity": _issue_identity(
            signer_private_key=identity_private_key,
            kid="rare-k1",
            typ="rare.identity.public+jws",
            agent_id=agent_id,
            level="L2",
            jti="id-public",
        ),
    }


def test_complete_auth_falls_back_from_full_to_public_and_caps_level() -> None:
    kit, identity_private_key, signer_private_key = setup_kit()
    agent_id = new_agent_id()
    auth = create_auth_payload(
        kit, identity_private_key, signer_private_key, agent_id=agent_id, delegation_jti="jti-1"
    )

    result = run(
        kit.complete_auth(
            AuthCompleteInput(
                nonce=auth["challenge"].nonce,
                agent_id=agent_id,
                session_pubkey=auth["session_pubkey"],
                delegation_token=auth["delegation"],
                signature_by_session=auth["signature_by_session"],
                full_identity_attestation=auth["full_wrong_aud"],
                public_identity_attestation=auth["public_identity"],
            )
        )
    )

    assert result.identity_mode == "public"
    assert result.raw_level == "L2"
    assert result.level == "L1"
    assert result.display_name == "neo"


def test_complete_auth_rejects_triad_mismatch() -> None:
    kit, identity_private_key, signer_private_key = setup_kit()
    agent_a = new_agent_id()
    agent_b = new_agent_id()
    auth = create_auth_payload(
        kit, identity_private_key, signer_private_key, agent_id=agent_a, delegation_jti="jti-2"
    )

    with pytest.raises(Exception, match="triad"):
        run(
            kit.complete_auth(
                AuthCompleteInput(
                    nonce=auth["challenge"].nonce,
                    agent_id=agent_b,
                    session_pubkey=auth["session_pubkey"],
                    delegation_token=auth["delegation"],
                    signature_by_session=auth["signature_by_session"],
                    full_identity_attestation=auth["full_wrong_aud"],
                    public_identity_attestation=auth["public_identity"],
                )
            )
        )


def test_complete_auth_rejects_delegation_replay() -> None:
    kit, identity_private_key, signer_private_key = setup_kit()
    agent_id = new_agent_id()
    auth = create_auth_payload(
        kit, identity_private_key, signer_private_key, agent_id=agent_id, delegation_jti="jti-replay"
    )

    run(
        kit.complete_auth(
            AuthCompleteInput(
                nonce=auth["challenge"].nonce,
                agent_id=agent_id,
                session_pubkey=auth["session_pubkey"],
                delegation_token=auth["delegation"],
                signature_by_session=auth["signature_by_session"],
                public_identity_attestation=auth["public_identity"],
            )
        )
    )


def test_complete_auth_hydrates_hosted_signer_key_from_rare_api() -> None:
    kit, identity_private_key, signer_private_key, rare_api_client, http_client = (
        setup_kit_with_rare_api_client()
    )
    agent_id = new_agent_id()
    auth = create_auth_payload(
        kit, identity_private_key, signer_private_key, agent_id=agent_id, delegation_jti="jti-jwks-1"
    )

    try:
        result = run(
            kit.complete_auth(
                AuthCompleteInput(
                    nonce=auth["challenge"].nonce,
                    agent_id=agent_id,
                    session_pubkey=auth["session_pubkey"],
                    delegation_token=auth["delegation"],
                    signature_by_session=auth["signature_by_session"],
                    public_identity_attestation=auth["public_identity"],
                )
            )
        )
    finally:
        run(http_client.aclose())
        run(rare_api_client.aclose())

    assert result.agent_id == agent_id

    challenge = run(kit.issue_challenge("platform"))
    signature = sign_detached(
        build_auth_challenge_payload(
            aud=challenge.aud,
            nonce=challenge.nonce,
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
        ),
        auth["session_private_key"],
    )

    with pytest.raises(Exception, match="replay"):
        run(
            kit.complete_auth(
                AuthCompleteInput(
                    nonce=challenge.nonce,
                    agent_id=agent_id,
                    session_pubkey=auth["session_pubkey"],
                    delegation_token=auth["delegation"],
                    signature_by_session=signature,
                    public_identity_attestation=auth["public_identity"],
                )
            )
        )


def test_verify_action_rejects_replay() -> None:
    kit, identity_private_key, signer_private_key = setup_kit()
    agent_id = new_agent_id()
    auth = create_auth_payload(
        kit, identity_private_key, signer_private_key, agent_id=agent_id, delegation_jti="jti-action"
    )
    login = run(
        kit.complete_auth(
            AuthCompleteInput(
                nonce=auth["challenge"].nonce,
                agent_id=agent_id,
                session_pubkey=auth["session_pubkey"],
                delegation_token=auth["delegation"],
                signature_by_session=auth["signature_by_session"],
                public_identity_attestation=auth["public_identity"],
            )
        )
    )
    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(10)
    signature = sign_detached(
        build_action_payload(
            aud="platform",
            session_token=login.session_token,
            action="post",
            action_payload={"content": "hello"},
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        ),
        auth["session_private_key"],
    )

    result = run(
        kit.verify_action(
            VerifyActionInput(
                session_token=login.session_token,
                action="post",
                action_payload={"content": "hello"},
                nonce=nonce,
                issued_at=issued_at,
                expires_at=expires_at,
                signature_by_session=signature,
            )
        )
    )
    assert result.session.agent_id == agent_id

    with pytest.raises(Exception, match="consumed"):
        run(
            kit.verify_action(
                VerifyActionInput(
                    session_token=login.session_token,
                    action="post",
                    action_payload={"content": "hello"},
                    nonce=nonce,
                    issued_at=issued_at,
                    expires_at=expires_at,
                    signature_by_session=signature,
                )
            )
        )


def test_ingest_negative_events_with_client_and_signing_helper() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"accepted": 1})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    api_client = RareApiClient(
        rare_base_url="https://rare.example",
        http_client=http_client,
    )
    kit = create_rare_platform_kit(
        RarePlatformKitConfig(
            aud="platform",
            challenge_store=InMemoryChallengeStore(),
            replay_store=InMemoryReplayStore(),
            session_store=InMemorySessionStore(),
            rare_api_client=api_client,
        )
    )
    agent_id = new_agent_id()
    event_private_key = Ed25519PrivateKey.generate()
    private_key_pem = event_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    try:
        result = run(
            kit.ingest_negative_events(
                IngestEventsInput(
                    platform_id="platform-001",
                    kid="platform-k1",
                    private_key_pem=private_key_pem,
                    jti="event-jti-1",
                    events=[
                        RarePlatformEventItem(
                            event_id="ev-1",
                            agent_id=agent_id,
                            category="spam",
                            severity=3,
                            outcome="post_removed",
                            occurred_at=1_700_000_000,
                        )
                    ],
                )
            )
        )
    finally:
        run(http_client.aclose())
        run(api_client.aclose())

    assert captured["url"] == "https://rare.example/v1/identity-library/events/ingest"
    posted = json.loads(captured["body"])
    assert "event_token" in posted
    assert result.response == {"accepted": 1}


def test_fastapi_router_exposes_auth_endpoints() -> None:
    kit, identity_private_key, signer_private_key = setup_kit()
    agent_id = new_agent_id()
    auth = create_auth_payload(
        kit, identity_private_key, signer_private_key, agent_id=agent_id, delegation_jti="jti-fastapi"
    )
    app = FastAPI()
    app.include_router(create_fastapi_rare_router(kit, prefix="/rare"))
    client = TestClient(app)

    challenge_response = client.post("/rare/auth/challenge", json={"aud": "platform"})
    assert challenge_response.status_code == 200

    response = client.post(
        "/rare/auth/complete",
        json={
            "nonce": auth["challenge"].nonce,
            "agent_id": agent_id,
            "session_pubkey": auth["session_pubkey"],
            "delegation_token": auth["delegation"],
            "signature_by_session": auth["signature_by_session"],
            "public_identity_attestation": auth["public_identity"],
        },
    )
    assert response.status_code == 200
    assert response.json()["agent_id"] == agent_id


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        del ex
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def getdel(self, key: str) -> str | None:
        value = self.kv.get(key)
        if value is not None:
            del self.kv[key]
        return value

    async def delete(self, key: str) -> int:
        return 1 if self.kv.pop(key, None) is not None else 0


def test_redis_stores_are_atomic() -> None:
    redis = FakeRedis()
    challenge_store = RedisChallengeStore(redis)
    replay_store = RedisReplayStore(redis)
    session_store = RedisSessionStore(redis)

    run(
        challenge_store.set(
            AuthChallenge(
                nonce="n1",
                aud="platform",
                issued_at=1,
                expires_at=9_999_999_999,
            )
        )
    )
    got = run(challenge_store.consume("n1"))
    assert got is not None and got.nonce == "n1"
    assert run(challenge_store.consume("n1")) is None

    assert run(replay_store.claim("k1", 9_999_999_999)) is True
    assert run(replay_store.claim("k1", 9_999_999_999)) is False

    run(
        session_store.save(
            PlatformSession(
                session_token="s1",
                agent_id="a1",
                session_pubkey="p1",
                identity_mode="public",
                raw_level="L1",
                effective_level="L1",
                display_name="neo",
                aud="platform",
                created_at=1,
                expires_at=9_999_999_999,
            )
        )
    )
    assert run(session_store.get("s1")).agent_id == "a1"
