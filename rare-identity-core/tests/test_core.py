from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from rare_api.main import create_app
from rare_api.service import RareService
from rare_identity_protocol import (
    TokenValidationError,
    build_action_payload,
    build_auth_challenge_payload,
    build_platform_grant_payload,
    build_register_payload,
    build_set_name_payload,
    build_upgrade_request_payload,
    generate_ed25519_keypair,
    generate_nonce,
    issue_agent_delegation,
    load_private_key,
    load_public_key,
    now_ts,
    sign_detached,
    sign_jws,
    verify_detached,
)
from rare_identity_verifier import verify_identity_attestation


@dataclass
class RegisteredAgent:
    agent_id: str
    public_attestation: str
    private_key: str | None = None


@dataclass
class RegisteredPlatform:
    platform_aud: str
    platform_id: str
    key_id: str
    private_key: str


@pytest.fixture
def env() -> dict:
    service = RareService()
    app = create_app(service)
    return {"service": service, "client": TestClient(app)}


def register_agent(client: TestClient, name: str) -> RegisteredAgent:
    response = client.post("/v1/agents/self_register", json={"name": name})
    assert response.status_code == 200
    body = response.json()
    return RegisteredAgent(
        agent_id=body["agent_id"],
        public_attestation=body["public_identity_attestation"],
    )


def register_self_hosted_agent(client: TestClient, *, name: str) -> RegisteredAgent:
    private_key, public_key = generate_ed25519_keypair()
    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(8)
    sign_input = build_register_payload(
        agent_id=public_key,
        name=name,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = sign_detached(sign_input, load_private_key(private_key))

    response = client.post(
        "/v1/agents/self_register",
        json={
            "name": name,
            "key_mode": "self-hosted",
            "agent_public_key": public_key,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        },
    )
    assert response.status_code == 200
    body = response.json()
    return RegisteredAgent(
        agent_id=body["agent_id"],
        public_attestation=body["public_identity_attestation"],
        private_key=private_key,
    )


def register_platform(client: TestClient, service: RareService, *, aud: str = "platform") -> RegisteredPlatform:
    challenge_response = client.post(
        "/v1/platforms/register/challenge",
        json={"platform_aud": aud, "domain": "platform.example.com"},
    )
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()

    service.dns_txt_resolver = lambda name: [challenge["txt_value"]] if name == challenge["txt_name"] else []
    platform_private, platform_public = generate_ed25519_keypair()
    register_response = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": aud,
            "domain": "platform.example.com",
            "keys": [{"kid": "platform-k1", "public_key": platform_public}],
        },
    )
    assert register_response.status_code == 200
    return RegisteredPlatform(
        platform_aud=aud,
        platform_id="platform-001",
        key_id="platform-k1",
        private_key=platform_private,
    )


def sign_hosted_platform_grant(client: TestClient, *, agent_id: str, platform_aud: str) -> dict:
    response = client.post(
        "/v1/signer/sign_platform_grant",
        json={"agent_id": agent_id, "platform_aud": platform_aud, "ttl_seconds": 120},
    )
    assert response.status_code == 200
    return response.json()


def sign_hosted_full_issue(client: TestClient, *, agent_id: str, platform_aud: str) -> dict:
    response = client.post(
        "/v1/signer/sign_full_attestation_issue",
        json={"agent_id": agent_id, "platform_aud": platform_aud, "ttl_seconds": 120},
    )
    assert response.status_code == 200
    return response.json()


def sign_hosted_upgrade_request(
    client: TestClient,
    *,
    agent_id: str,
    target_level: str,
    request_id: str,
) -> dict:
    response = client.post(
        "/v1/signer/sign_upgrade_request",
        json={
            "agent_id": agent_id,
            "target_level": target_level,
            "request_id": request_id,
            "ttl_seconds": 120,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_self_register_supports_duplicate_display_name_and_no_private_key(env: dict) -> None:
    client = env["client"]

    first = client.post("/v1/agents/self_register", json={"name": "same"})
    second = client.post("/v1/agents/self_register", json={"name": "same"})

    assert first.status_code == 200
    assert second.status_code == 200

    first_body = first.json()
    second_body = second.json()

    assert first_body["agent_id"] != second_body["agent_id"]
    assert "agent_private_key" not in first_body
    assert first_body["key_mode"] == "hosted-signer"
    assert isinstance(first_body["public_identity_attestation"], str)


def test_self_register_self_hosted_requires_valid_proof(env: dict) -> None:
    client = env["client"]

    agent_private_key, agent_public_key = generate_ed25519_keypair()
    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(8)
    sign_input = build_register_payload(
        agent_id=agent_public_key,
        name="self-hosted",
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = sign_detached(sign_input, load_private_key(agent_private_key))

    response = client.post(
        "/v1/agents/self_register",
        json={
            "name": "self-hosted",
            "key_mode": "self-hosted",
            "agent_public_key": agent_public_key,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == agent_public_key
    assert body["key_mode"] == "self-hosted"

    forged = client.post(
        "/v1/agents/self_register",
        json={
            "name": "self-hosted-2",
            "key_mode": "self-hosted",
            "agent_public_key": agent_public_key,
            "nonce": generate_nonce(8),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        },
    )
    assert forged.status_code == 401


def test_set_name_with_hosted_signer_and_nonce_replay_rejected(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "alpha")

    signed = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": agent.agent_id, "name": "beta", "ttl_seconds": 120},
    )
    assert signed.status_code == 200
    signed_payload = signed.json()

    first = client.post("/v1/agents/set_name", json=signed_payload)
    second = client.post("/v1/agents/set_name", json=signed_payload)

    assert first.status_code == 200
    assert second.status_code == 409


def test_set_name_rejects_forged_signature(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "victim")

    attacker_priv, _ = generate_ed25519_keypair()
    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(8)

    forged_input = build_set_name_payload(
        agent_id=agent.agent_id,
        name="hacked",
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    forged_sig = sign_detached(forged_input, load_private_key(attacker_priv))

    response = client.post(
        "/v1/agents/set_name",
        json={
            "agent_id": agent.agent_id,
            "name": "hacked",
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": forged_sig,
        },
    )
    assert response.status_code == 401


def test_prepare_auth_and_sign_action_with_hosted_session_key(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "actor")

    challenge = {
        "aud": "platform",
        "nonce": generate_nonce(8),
        "issued_at": now_ts(),
        "expires_at": now_ts() + 120,
    }

    prepared = client.post(
        "/v1/signer/prepare_auth",
        json={
            "agent_id": agent.agent_id,
            "aud": challenge["aud"],
            "nonce": challenge["nonce"],
            "issued_at": challenge["issued_at"],
            "expires_at": challenge["expires_at"],
            "scope": ["login", "post"],
            "delegation_ttl_seconds": 300,
        },
    )
    assert prepared.status_code == 200
    proof = prepared.json()

    sign_action = client.post(
        "/v1/signer/sign_action",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": proof["session_pubkey"],
            "session_token": "sess-token",
            "aud": "platform",
            "action": "post",
            "action_payload": {"content": "hello"},
            "nonce": generate_nonce(8),
            "issued_at": now_ts(),
            "expires_at": now_ts() + 120,
        },
    )
    assert sign_action.status_code == 200
    action_signed = sign_action.json()

    signing_input = build_action_payload(
        aud="platform",
        session_token="sess-token",
        action="post",
        action_payload={"content": "hello"},
        nonce=action_signed["nonce"],
        issued_at=action_signed["issued_at"],
        expires_at=action_signed["expires_at"],
    )
    verify_detached(
        signing_input,
        action_signed["signature_by_session"],
        load_public_key(proof["session_pubkey"]),
    )


def test_public_attestation_refresh_and_identity_library(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "core")

    refresh = client.post("/v1/attestations/public/issue", json={"agent_id": agent.agent_id})
    assert refresh.status_code == 200

    keys = client.get("/.well-known/rare-keys.json")
    assert keys.status_code == 200
    body = keys.json()
    assert body["issuer"] == "rare"
    assert len(body["keys"]) >= 1

    attestation = refresh.json()["public_identity_attestation"]
    verified = verify_identity_attestation(attestation, key_resolver=service.get_identity_public_key)
    assert verified.payload["sub"] == agent.agent_id

    profile = client.get(f"/v1/identity-library/profiles/{agent.agent_id}")
    assert profile.status_code == 200
    assert profile.json()["agent_id"] == agent.agent_id

    patch = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"risk_score": 0.9, "labels": ["bot", "high-risk"]}},
    )
    assert patch.status_code == 200
    assert patch.json()["risk_score"] == 0.9


def test_public_caps_level_to_l1_but_full_keeps_l2(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "cap-agent")
    register_platform(client, service, aud="platform")

    bind = client.post(
        "/v1/console/bind_owner",
        json={"agent_id": agent.agent_id, "owner_id": "owner-1", "org_id": "org-1"},
    )
    assert bind.status_code == 200
    social = client.post(
        "/v1/assets/github/connect",
        json={"agent_id": agent.agent_id, "id": "100", "login": "rare-agent"},
    )
    assert social.status_code == 200
    upgraded = client.post(
        "/v1/attestations/upgrade",
        json={"agent_id": agent.agent_id, "target_level": "L2"},
    )
    assert upgraded.status_code == 200
    public_token = upgraded.json()["public_identity_attestation"]
    public_verified = verify_identity_attestation(public_token, key_resolver=service.get_identity_public_key)
    assert public_verified.payload["lvl"] == "L1"

    grant_signed = sign_hosted_platform_grant(client, agent_id=agent.agent_id, platform_aud="platform")
    grant = client.post("/v1/agents/platform-grants", json=grant_signed)
    assert grant.status_code == 200

    full_signed = sign_hosted_full_issue(client, agent_id=agent.agent_id, platform_aud="platform")
    full = client.post("/v1/attestations/full/issue", json=full_signed)
    assert full.status_code == 200
    full_token = full.json()["full_identity_attestation"]
    full_verified = verify_identity_attestation(
        full_token,
        key_resolver=service.get_identity_public_key,
        expected_aud="platform",
    )
    assert full_verified.payload["lvl"] == "L2"
    with pytest.raises(TokenValidationError):
        verify_identity_attestation(
            full_token,
            key_resolver=service.get_identity_public_key,
            expected_aud="other-platform",
        )


def test_upgrade_l1_magic_link_flow_and_nonce_replay(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "upgrade-l1")

    request_id = "upg-l1-1"
    signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=request_id,
    )
    created = client.post(
        "/v1/upgrades/requests",
        json={**signed, "contact_email": "owner@example.com"},
    )
    assert created.status_code == 200
    assert created.json()["status"] == "human_pending"
    assert created.json()["next_step"] == "verify_email"

    replay = client.post(
        "/v1/upgrades/requests",
        json={
            **signed,
            "request_id": "upg-l1-2",
            "contact_email": "owner@example.com",
        },
    )
    assert replay.status_code == 409

    sent = client.post("/v1/upgrades/l1/email/send-link", json={"upgrade_request_id": request_id})
    assert sent.status_code == 200
    token = sent.json()["token"]
    verified = client.get("/v1/upgrades/l1/email/verify", params={"token": token})
    assert verified.status_code == 200
    assert verified.json()["status"] == "upgraded"
    assert verified.json()["level"] == "L1"
    public_token = verified.json()["public_identity_attestation"]
    public_verified = verify_identity_attestation(
        public_token,
        key_resolver=service.get_identity_public_key,
    )
    assert public_verified.payload["lvl"] == "L1"

    profile = client.get(f"/v1/identity-library/profiles/{agent.agent_id}")
    assert profile.status_code == 200
    assert "owner-linked" in profile.json()["labels"]

    reused = client.get("/v1/upgrades/l1/email/verify", params={"token": token})
    assert reused.status_code == 400


def test_upgrade_request_rejects_invalid_signature(env: dict) -> None:
    client = env["client"]
    agent = register_self_hosted_agent(client, name="upgrade-self")
    assert agent.private_key is not None

    issued_at = now_ts()
    expires_at = issued_at + 120
    request_id = "upg-bad-signature"
    nonce = generate_nonce(8)
    sign_input = build_upgrade_request_payload(
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=request_id,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = sign_detached(sign_input, load_private_key(agent.private_key))

    forged = client.post(
        "/v1/upgrades/requests",
        json={
            "agent_id": agent.agent_id,
            "target_level": "L1",
            "request_id": request_id,
            "nonce": generate_nonce(8),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
            "contact_email": "owner@example.com",
        },
    )
    assert forged.status_code == 401


def test_upgrade_l2_requires_l1_and_supports_x_or_github(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "upgrade-l2")

    l2_request_id = "upg-l2-reject"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
    )
    rejected = client.post("/v1/upgrades/requests", json=signed_l2)
    assert rejected.status_code == 403

    l1_request_id = "upg-l2-prep-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "owner2@example.com"},
    )
    assert created_l1.status_code == 200
    sent = client.post("/v1/upgrades/l1/email/send-link", json={"upgrade_request_id": l1_request_id})
    assert sent.status_code == 200
    verified_l1 = client.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200
    assert verified_l1.json()["level"] == "L1"

    x_request_id = "upg-l2-x"
    signed_x = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=x_request_id,
    )
    created_x = client.post("/v1/upgrades/requests", json=signed_x)
    assert created_x.status_code == 200
    started_x = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": x_request_id, "provider": "x"},
    )
    assert started_x.status_code == 200
    callback_x = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "x", "code": "x-code-1", "state": started_x.json()["state"]},
    )
    assert callback_x.status_code == 200
    assert callback_x.json()["status"] == "upgraded"
    assert callback_x.json()["level"] == "L2"
    full_x = client.post(
        "/v1/attestations/full/issue",
        json=sign_hosted_full_issue(client, agent_id=agent.agent_id, platform_aud="platform"),
    )
    if full_x.status_code == 403:
        register_platform(client, service, aud="platform")
        grant = client.post(
            "/v1/agents/platform-grants",
            json=sign_hosted_platform_grant(client, agent_id=agent.agent_id, platform_aud="platform"),
        )
        assert grant.status_code == 200
        full_x = client.post(
            "/v1/attestations/full/issue",
            json=sign_hosted_full_issue(client, agent_id=agent.agent_id, platform_aud="platform"),
        )
    assert full_x.status_code == 200
    full_verified = verify_identity_attestation(
        full_x.json()["full_identity_attestation"],
        key_resolver=service.get_identity_public_key,
        expected_aud="platform",
    )
    assert full_verified.payload["lvl"] == "L2"

    github_request_id = "upg-l2-github"
    signed_github = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=github_request_id,
    )
    created_gh = client.post("/v1/upgrades/requests", json=signed_github)
    assert created_gh.status_code == 200
    bad_complete = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": github_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "200"},
        },
    )
    assert bad_complete.status_code == 400
    good_complete = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": github_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "200", "login": "rare-dev"},
        },
    )
    assert good_complete.status_code == 200
    assert good_complete.json()["status"] == "upgraded"
    assert good_complete.json()["level"] == "L2"


def test_breaking_rejects_legacy_identity_typ(env: dict) -> None:
    service = env["service"]
    _, pub = generate_ed25519_keypair()
    key = service.identity_keys[service.active_identity_kid]
    token = sign_jws(
        payload={
            "typ": "rare.identity",
            "ver": 1,
            "iss": "rare",
            "sub": pub,
            "lvl": "L1",
            "claims": {"profile": {"name": "legacy"}},
            "iat": now_ts(),
            "exp": now_ts() + 300,
            "jti": "legacy-token",
        },
        private_key=key.private_key,
        kid=key.kid,
        typ="rare.identity+jws",
    )
    with pytest.raises(TokenValidationError):
        verify_identity_attestation(token, key_resolver=service.get_identity_public_key)


def test_upgrade_l2_oauth_state_expired_and_replay(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "upgrade-l2-state")

    l1_request_id = "upg-l2-state-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "state-owner@example.com"},
    )
    assert created_l1.status_code == 200
    sent = client.post("/v1/upgrades/l1/email/send-link", json={"upgrade_request_id": l1_request_id})
    assert sent.status_code == 200
    verified_l1 = client.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "upg-l2-state-main"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
    )
    created_l2 = client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200

    started = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": l2_request_id, "provider": "x"},
    )
    assert started.status_code == 200
    state = started.json()["state"]
    env["service"].upgrade_oauth_states[state].expires_at = now_ts() - 31
    expired = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "x", "code": "expired-code", "state": state},
    )
    assert expired.status_code in {400, 404}

    l2_request_id_replay = "upg-l2-state-replay"
    signed_replay = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id_replay,
    )
    created_replay = client.post("/v1/upgrades/requests", json=signed_replay)
    assert created_replay.status_code == 200
    started_replay = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": l2_request_id_replay, "provider": "x"},
    )
    assert started_replay.status_code == 200
    state_replay = started_replay.json()["state"]
    first = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "x", "code": "good-code", "state": state_replay},
    )
    assert first.status_code == 200
    second = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "x", "code": "good-code-2", "state": state_replay},
    )
    assert second.status_code == 400


def test_platform_registration_dns_mismatch_expired_and_reuse(env: dict) -> None:
    client = env["client"]
    service = env["service"]

    challenge_resp = client.post(
        "/v1/platforms/register/challenge",
        json={"platform_aud": "platform", "domain": "platform.example.com"},
    )
    assert challenge_resp.status_code == 200
    challenge = challenge_resp.json()

    platform_priv, platform_pub = generate_ed25519_keypair()
    service.dns_txt_resolver = lambda _name: []
    mismatch = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform",
            "domain": "platform.example.com",
            "keys": [{"kid": "platform-k1", "public_key": platform_pub}],
        },
    )
    assert mismatch.status_code == 400
    del platform_priv

    service.dns_txt_resolver = lambda name: [challenge["txt_value"]] if name == challenge["txt_name"] else []
    success = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform",
            "domain": "platform.example.com",
            "keys": [{"kid": "platform-k1", "public_key": platform_pub}],
        },
    )
    assert success.status_code == 200

    reused = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform",
            "domain": "platform.example.com",
            "keys": [{"kid": "platform-k1", "public_key": platform_pub}],
        },
    )
    assert reused.status_code == 400

    challenge2 = client.post(
        "/v1/platforms/register/challenge",
        json={"platform_aud": "platform-2", "domain": "platform2.example.com"},
    ).json()
    service.platform_register_challenges[challenge2["challenge_id"]].expires_at = now_ts() - 31
    expired = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge2["challenge_id"],
            "platform_id": "platform-002",
            "platform_aud": "platform-2",
            "domain": "platform2.example.com",
            "keys": [{"kid": "platform-k2", "public_key": platform_pub}],
        },
    )
    assert expired.status_code == 400


def test_full_issue_requires_registration_grant_and_rejects_replay(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "need-grant")

    full_signed = sign_hosted_full_issue(client, agent_id=agent.agent_id, platform_aud="platform")
    no_platform = client.post("/v1/attestations/full/issue", json=full_signed)
    assert no_platform.status_code == 403

    register_platform(client, service, aud="platform")
    no_grant = client.post("/v1/attestations/full/issue", json=full_signed)
    assert no_grant.status_code == 403

    grant_signed = sign_hosted_platform_grant(client, agent_id=agent.agent_id, platform_aud="platform")
    grant_ok = client.post("/v1/agents/platform-grants", json=grant_signed)
    assert grant_ok.status_code == 200
    grant_replay = client.post("/v1/agents/platform-grants", json=grant_signed)
    assert grant_replay.status_code == 409

    full_issue_ok = client.post("/v1/attestations/full/issue", json=full_signed)
    assert full_issue_ok.status_code == 200
    full_issue_replay = client.post("/v1/attestations/full/issue", json=full_signed)
    assert full_issue_replay.status_code == 409


def test_self_hosted_grant_revoke_and_list(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    register_platform(client, service, aud="platform")
    agent = register_self_hosted_agent(client, name="self-agent")
    assert agent.private_key is not None

    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(8)
    sign_input = build_platform_grant_payload(
        agent_id=agent.agent_id,
        platform_aud="platform",
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = sign_detached(sign_input, load_private_key(agent.private_key))
    granted = client.post(
        "/v1/agents/platform-grants",
        json={
            "agent_id": agent.agent_id,
            "platform_aud": "platform",
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        },
    )
    assert granted.status_code == 200

    listing = client.get(f"/v1/agents/platform-grants/{agent.agent_id}")
    assert listing.status_code == 200
    assert listing.json()["grants"][0]["status"] == "active"

    revoke_nonce = generate_nonce(8)
    revoke_input = build_platform_grant_payload(
        agent_id=agent.agent_id,
        platform_aud="platform",
        nonce=revoke_nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    revoke_sig = sign_detached(revoke_input, load_private_key(agent.private_key))
    revoked = client.request(
        "DELETE",
        "/v1/agents/platform-grants/platform",
        json={
            "agent_id": agent.agent_id,
            "nonce": revoke_nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": revoke_sig,
        },
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"


def test_platform_event_ingest_updates_profile_and_blocks_replays(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "risk-agent")
    platform = register_platform(client, service, aud="platform")

    now = now_ts()
    token = sign_jws(
        payload={
            "typ": "rare.platform-event",
            "ver": 1,
            "iss": platform.platform_id,
            "aud": "rare.identity-library",
            "iat": now,
            "exp": now + 300,
            "jti": "evt-jti-1",
            "events": [
                {
                    "event_id": "e-1",
                    "agent_id": agent.agent_id,
                    "category": "fraud",
                    "severity": 4,
                    "outcome": "blocked",
                    "occurred_at": now,
                    "evidence_hash": "sha256:abc",
                }
            ],
        },
        private_key=load_private_key(platform.private_key),
        kid=platform.key_id,
        typ="rare.platform-event+jws",
    )
    ingested = client.post("/v1/identity-library/events/ingest", json={"event_token": token})
    assert ingested.status_code == 200
    assert ingested.json()["accepted_count"] == 1

    profile = client.get(f"/v1/identity-library/profiles/{agent.agent_id}")
    assert profile.status_code == 200
    body = profile.json()
    assert body["risk_score"] > 0
    assert "abuse-reported" in body["labels"]
    assert "fraud-risk" in body["labels"]
    assert body["metadata"]["platform_event_counts"]["fraud"] == 1

    deduped_token = sign_jws(
        payload={
            "typ": "rare.platform-event",
            "ver": 1,
            "iss": platform.platform_id,
            "aud": "rare.identity-library",
            "iat": now,
            "exp": now + 300,
            "jti": "evt-jti-1b",
            "events": [
                {
                    "event_id": "e-1",
                    "agent_id": agent.agent_id,
                    "category": "fraud",
                    "severity": 4,
                    "outcome": "blocked",
                    "occurred_at": now,
                    "evidence_hash": "sha256:abc",
                }
            ],
        },
        private_key=load_private_key(platform.private_key),
        kid=platform.key_id,
        typ="rare.platform-event+jws",
    )
    deduped = client.post("/v1/identity-library/events/ingest", json={"event_token": deduped_token})
    assert deduped.status_code == 200
    assert deduped.json()["accepted_count"] == 0
    assert deduped.json()["deduped_count"] == 1

    replay = client.post("/v1/identity-library/events/ingest", json={"event_token": token})
    assert replay.status_code == 409

    bad_category = sign_jws(
        payload={
            "typ": "rare.platform-event",
            "ver": 1,
            "iss": platform.platform_id,
            "aud": "rare.identity-library",
            "iat": now,
            "exp": now + 300,
            "jti": "evt-jti-2",
            "events": [
                {
                    "event_id": "e-2",
                    "agent_id": agent.agent_id,
                    "category": "other",
                    "severity": 1,
                    "outcome": "note",
                    "occurred_at": now,
                }
            ],
        },
        private_key=load_private_key(platform.private_key),
        kid=platform.key_id,
        typ="rare.platform-event+jws",
    )
    rejected = client.post("/v1/identity-library/events/ingest", json={"event_token": bad_category})
    assert rejected.status_code == 400


def test_verifier_rejects_unknown_kid(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "kid")

    with pytest.raises(Exception):
        verify_identity_attestation(
            agent.public_attestation,
            key_resolver=lambda _kid: None,
        )


def test_self_hosted_login_payload_can_be_built_for_platform(env: dict) -> None:
    del env
    private_key, public_key = generate_ed25519_keypair()
    issued_at = now_ts()
    expires_at = issued_at + 120
    challenge_payload = build_auth_challenge_payload(
        aud="platform",
        nonce=generate_nonce(8),
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = sign_detached(challenge_payload, load_private_key(private_key))
    assert isinstance(signature, str)

    delegation = issue_agent_delegation(
        agent_id=public_key,
        session_pubkey=public_key,
        aud="platform",
        scope=["login"],
        signer_private_key=load_private_key(private_key),
        kid=f"agent-{public_key[:8]}",
        ttl_seconds=300,
        jti=generate_nonce(8),
    )
    assert isinstance(delegation, str)
