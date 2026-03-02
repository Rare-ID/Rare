from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from rare_api.main import create_app
from rare_api.service import RareService
from rare_identity_protocol import (
    TokenValidationError,
    build_action_payload,
    build_agent_auth_payload,
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
from rare_identity_verifier import verify_delegation_token, verify_identity_attestation


@dataclass
class RegisteredAgent:
    agent_id: str
    public_attestation: str
    private_key: str | None = None
    hosted_management_token: str | None = None
    hosted_management_token_expires_at: int | None = None


@dataclass
class RegisteredPlatform:
    platform_aud: str
    platform_id: str
    key_id: str
    private_key: str


@pytest.fixture
def env() -> dict:
    admin_token = "test-admin-token"
    service = RareService(allow_local_upgrade_shortcuts=True)
    app = create_app(service, admin_token=admin_token)
    return {"service": service, "client": TestClient(app), "admin_token": admin_token}


def register_agent(client: TestClient, name: str) -> RegisteredAgent:
    response = client.post("/v1/agents/self_register", json={"name": name})
    assert response.status_code == 200
    body = response.json()
    return RegisteredAgent(
        agent_id=body["agent_id"],
        public_attestation=body["public_identity_attestation"],
        hosted_management_token=body["hosted_management_token"],
        hosted_management_token_expires_at=body["hosted_management_token_expires_at"],
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


def hosted_headers(agent: RegisteredAgent) -> dict[str, str]:
    assert agent.hosted_management_token is not None
    return {"Authorization": f"Bearer {agent.hosted_management_token}"}


def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


def self_hosted_management_headers(
    *,
    agent_id: str,
    private_key: str,
    operation: str,
    resource_id: str,
) -> dict[str, str]:
    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(10)
    payload = build_agent_auth_payload(
        agent_id=agent_id,
        operation=operation,
        resource_id=resource_id,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = sign_detached(payload, load_private_key(private_key))
    return {
        "X-Rare-Agent-Id": agent_id,
        "X-Rare-Agent-Nonce": nonce,
        "X-Rare-Agent-Issued-At": str(issued_at),
        "X-Rare-Agent-Expires-At": str(expires_at),
        "X-Rare-Agent-Signature": signature,
    }


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


def sign_hosted_platform_grant(
    client: TestClient,
    *,
    agent_id: str,
    platform_aud: str,
    hosted_management_token: str,
) -> dict:
    response = client.post(
        "/v1/signer/sign_platform_grant",
        json={"agent_id": agent_id, "platform_aud": platform_aud, "ttl_seconds": 120},
        headers={"Authorization": f"Bearer {hosted_management_token}"},
    )
    assert response.status_code == 200
    return response.json()


def sign_hosted_full_issue(
    client: TestClient,
    *,
    agent_id: str,
    platform_aud: str,
    hosted_management_token: str,
) -> dict:
    response = client.post(
        "/v1/signer/sign_full_attestation_issue",
        json={"agent_id": agent_id, "platform_aud": platform_aud, "ttl_seconds": 120},
        headers={"Authorization": f"Bearer {hosted_management_token}"},
    )
    assert response.status_code == 200
    return response.json()


def sign_hosted_upgrade_request(
    client: TestClient,
    *,
    agent_id: str,
    target_level: str,
    request_id: str,
    hosted_management_token: str,
) -> dict:
    response = client.post(
        "/v1/signer/sign_upgrade_request",
        json={
            "agent_id": agent_id,
            "target_level": target_level,
            "request_id": request_id,
            "ttl_seconds": 120,
        },
        headers={"Authorization": f"Bearer {hosted_management_token}"},
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
    assert isinstance(first_body["hosted_management_token"], str)
    assert isinstance(first_body["hosted_management_token_expires_at"], int)
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
    assert "hosted_management_token" not in body

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
        headers=hosted_headers(agent),
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
        headers=hosted_headers(agent),
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
        headers=hosted_headers(agent),
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
    admin_token = env["admin_token"]
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
        headers=admin_headers(admin_token),
    )
    assert patch.status_code == 200
    assert patch.json()["risk_score"] == 0.9


def test_public_caps_level_to_l1_but_full_keeps_l2(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "cap-agent")
    register_platform(client, service, aud="platform")

    l1_request_id = "cap-upg-l1"
    l1_signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**l1_signed, "contact_email": "owner-cap@example.com"},
    )
    assert created_l1.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified_l1 = client.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "cap-upg-l2"
    l2_signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = client.post("/v1/upgrades/requests", json=l2_signed)
    assert created_l2.status_code == 200
    upgraded = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "100", "login": "rare-agent"},
        },
        headers=hosted_headers(agent),
    )
    assert upgraded.status_code == 200
    public_token = upgraded.json()["public_identity_attestation"]
    public_verified = verify_identity_attestation(public_token, key_resolver=service.get_identity_public_key)
    assert public_verified.payload["lvl"] == "L1"

    grant_signed = sign_hosted_platform_grant(
        client,
        agent_id=agent.agent_id,
        platform_aud="platform",
        hosted_management_token=agent.hosted_management_token or "",
    )
    grant = client.post("/v1/agents/platform-grants", json=grant_signed)
    assert grant.status_code == 200

    full_signed = sign_hosted_full_issue(
        client,
        agent_id=agent.agent_id,
        platform_aud="platform",
        hosted_management_token=agent.hosted_management_token or "",
    )
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
        hosted_management_token=agent.hosted_management_token or "",
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

    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": request_id},
        headers=hosted_headers(agent),
    )
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
        hosted_management_token=agent.hosted_management_token or "",
    )
    rejected = client.post("/v1/upgrades/requests", json=signed_l2)
    assert rejected.status_code == 403

    l1_request_id = "upg-l2-prep-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "owner2@example.com"},
    )
    assert created_l1.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
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
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_x = client.post("/v1/upgrades/requests", json=signed_x)
    assert created_x.status_code == 200
    started_x = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": x_request_id, "provider": "x"},
        headers=hosted_headers(agent),
    )
    assert started_x.status_code == 200
    callback_x = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "x", "code": "x-code-1", "state": started_x.json()["state"]},
    )
    assert callback_x.status_code == 200
    assert callback_x.json()["status"] == "upgraded"
    assert callback_x.json()["level"] == "L2"
    full_x_without_platform = client.post(
        "/v1/attestations/full/issue",
        json=sign_hosted_full_issue(
            client,
            agent_id=agent.agent_id,
            platform_aud="platform",
            hosted_management_token=agent.hosted_management_token or "",
        ),
    )
    assert full_x_without_platform.status_code == 403
    assert "platform is not registered" in full_x_without_platform.json()["detail"]

    register_platform(client, service, aud="platform")
    full_x_without_grant = client.post(
        "/v1/attestations/full/issue",
        json=sign_hosted_full_issue(
            client,
            agent_id=agent.agent_id,
            platform_aud="platform",
            hosted_management_token=agent.hosted_management_token or "",
        ),
    )
    assert full_x_without_grant.status_code == 403
    assert "agent has not granted this platform" in full_x_without_grant.json()["detail"]

    grant = client.post(
        "/v1/agents/platform-grants",
        json=sign_hosted_platform_grant(
            client,
            agent_id=agent.agent_id,
            platform_aud="platform",
            hosted_management_token=agent.hosted_management_token or "",
        ),
    )
    assert grant.status_code == 200

    full_x = client.post(
        "/v1/attestations/full/issue",
        json=sign_hosted_full_issue(
            client,
            agent_id=agent.agent_id,
            platform_aud="platform",
            hosted_management_token=agent.hosted_management_token or "",
        ),
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
        hosted_management_token=agent.hosted_management_token or "",
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
        headers=hosted_headers(agent),
    )
    assert bad_complete.status_code == 400
    good_complete = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": github_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "200", "login": "rare-dev"},
        },
        headers=hosted_headers(agent),
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
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "state-owner@example.com"},
    )
    assert created_l1.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified_l1 = client.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "upg-l2-state-main"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200

    started = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": l2_request_id, "provider": "x"},
        headers=hosted_headers(agent),
    )
    assert started.status_code == 200
    state = started.json()["state"]
    state_record = env["service"].upgrade_oauth_states.get(state)
    assert state_record is not None
    state_record.expires_at = now_ts() - 31
    expired = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "x", "code": "expired-code", "state": state},
    )
    assert expired.status_code in {400, 404}
    assert expired.json()["detail"] in {"oauth state expired", "oauth state not found"}

    l2_request_id_replay = "upg-l2-state-replay"
    signed_replay = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id_replay,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_replay = client.post("/v1/upgrades/requests", json=signed_replay)
    assert created_replay.status_code == 200
    started_replay = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": l2_request_id_replay, "provider": "x"},
        headers=hosted_headers(agent),
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
    challenge_record = service.platform_register_challenges.get(challenge2["challenge_id"])
    assert challenge_record is not None
    challenge_record.expires_at = now_ts() - 31
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

    full_signed = sign_hosted_full_issue(
        client,
        agent_id=agent.agent_id,
        platform_aud="platform",
        hosted_management_token=agent.hosted_management_token or "",
    )
    no_platform = client.post("/v1/attestations/full/issue", json=full_signed)
    assert no_platform.status_code == 403

    register_platform(client, service, aud="platform")
    no_grant = client.post("/v1/attestations/full/issue", json=full_signed)
    assert no_grant.status_code == 403

    grant_signed = sign_hosted_platform_grant(
        client,
        agent_id=agent.agent_id,
        platform_aud="platform",
        hosted_management_token=agent.hosted_management_token or "",
    )
    grant_ok = client.post("/v1/agents/platform-grants", json=grant_signed)
    assert grant_ok.status_code == 200
    grant_replay = client.post("/v1/agents/platform-grants", json=grant_signed)
    assert grant_replay.status_code == 409

    full_issue_ok = client.post("/v1/attestations/full/issue", json=full_signed)
    assert full_issue_ok.status_code == 200
    full_issue_replay = client.post("/v1/attestations/full/issue", json=full_signed)
    assert full_issue_replay.status_code == 409


def test_sign_delegation_requires_bound_hosted_management_and_valid_ttl(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "sign-delegation")
    other = register_agent(client, "sign-delegation-other")
    _, session_pubkey = generate_ed25519_keypair()

    missing = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login"],
            "ttl_seconds": 300,
        },
    )
    assert missing.status_code == 401
    assert "Authorization header" in missing.json()["detail"]

    wrong = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login"],
            "ttl_seconds": 300,
        },
        headers=hosted_headers(other),
    )
    assert wrong.status_code == 403
    assert "invalid hosted management token" in wrong.json()["detail"]

    ttl_zero = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login"],
            "ttl_seconds": 0,
        },
        headers=hosted_headers(agent),
    )
    assert ttl_zero.status_code == 400
    assert "ttl_seconds must be greater than 0" in ttl_zero.json()["detail"]

    ttl_too_long = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login"],
            "ttl_seconds": 3601,
        },
        headers=hosted_headers(agent),
    )
    assert ttl_too_long.status_code == 400
    assert "ttl_seconds exceeds max 3600 seconds" in ttl_too_long.json()["detail"]

    ok = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login", "post"],
            "ttl_seconds": 300,
        },
        headers=hosted_headers(agent),
    )
    assert ok.status_code == 200
    delegation_token = ok.json()["delegation_token"]
    verified = verify_delegation_token(
        delegation_token,
        expected_aud="platform",
        required_scope="login",
        rare_signer_public_key=service.get_rare_signer_public_key(),
    )
    assert verified.payload["agent_id"] == agent.agent_id
    assert verified.payload["iss"] == "rare-signer"


def test_refresh_attestation_endpoint_and_error_mapping(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "refresh")

    refreshed = client.post("/v1/attestations/refresh", json={"agent_id": agent.agent_id})
    assert refreshed.status_code == 200
    verified = verify_identity_attestation(
        refreshed.json()["public_identity_attestation"],
        key_resolver=service.get_identity_public_key,
    )
    assert verified.payload["sub"] == agent.agent_id

    unknown = client.post("/v1/attestations/refresh", json={"agent_id": "missing-agent"})
    assert unknown.status_code == 404
    assert "agent not found" in unknown.json()["detail"]


def test_identity_library_patch_and_subscription_validation(env: dict) -> None:
    client = env["client"]
    admin_token = env["admin_token"]
    agent = register_agent(client, "identity-validators")

    bad_risk = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"risk_score": 1.1}},
        headers=admin_headers(admin_token),
    )
    assert bad_risk.status_code == 400
    assert "risk_score must be between 0.0 and 1.0" in bad_risk.json()["detail"]

    bad_labels = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"labels": "not-a-list"}},
        headers=admin_headers(admin_token),
    )
    assert bad_labels.status_code == 400
    assert "labels must be string list" in bad_labels.json()["detail"]

    bad_summary = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"summary": {"bad": "type"}}},
        headers=admin_headers(admin_token),
    )
    assert bad_summary.status_code == 400
    assert "summary must be string" in bad_summary.json()["detail"]

    bad_metadata = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"metadata": "not-object"}},
        headers=admin_headers(admin_token),
    )
    assert bad_metadata.status_code == 400
    assert "metadata must be object" in bad_metadata.json()["detail"]

    bad_webhook = client.post(
        "/v1/identity-library/subscriptions",
        json={
            "name": "risk-feed",
            "webhook_url": "ftp://example.com/hook",
            "fields": ["risk_score"],
            "event_types": ["risk_update"],
        },
        headers=admin_headers(admin_token),
    )
    assert bad_webhook.status_code == 400
    assert "webhook_url must be http/https" in bad_webhook.json()["detail"]

    bad_name = client.post(
        "/v1/identity-library/subscriptions",
        json={
            "name": "   ",
            "webhook_url": "https://example.com/hook",
            "fields": ["risk_score"],
            "event_types": ["risk_update"],
        },
        headers=admin_headers(admin_token),
    )
    assert bad_name.status_code == 400
    assert "subscription name cannot be empty" in bad_name.json()["detail"]


def test_platform_register_key_validation_and_conflicts(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    challenge_values: dict[str, str] = {}

    def remember_challenge(payload: dict) -> None:
        challenge_values[payload["txt_name"]] = payload["txt_value"]

    service.dns_txt_resolver = (
        lambda name: [challenge_values[name]] if name in challenge_values else []
    )

    first_challenge = client.post(
        "/v1/platforms/register/challenge",
        json={"platform_aud": "platform", "domain": "platform.example.com"},
    )
    assert first_challenge.status_code == 200
    first_payload = first_challenge.json()
    remember_challenge(first_payload)

    _, pub1 = generate_ed25519_keypair()
    empty_keys = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": first_payload["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform",
            "domain": "platform.example.com",
            "keys": [],
        },
    )
    assert empty_keys.status_code == 400
    assert "at least one platform key required" in empty_keys.json()["detail"]

    duplicate_kid = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": first_payload["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform",
            "domain": "platform.example.com",
            "keys": [
                {"kid": "shared-kid", "public_key": pub1},
                {"kid": "shared-kid", "public_key": pub1},
            ],
        },
    )
    assert duplicate_kid.status_code == 400
    assert "duplicate platform key kid" in duplicate_kid.json()["detail"]

    first_ok = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": first_payload["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform",
            "domain": "platform.example.com",
            "keys": [{"kid": "shared-kid", "public_key": pub1}],
        },
    )
    assert first_ok.status_code == 200

    second_challenge = client.post(
        "/v1/platforms/register/challenge",
        json={"platform_aud": "platform-2", "domain": "platform2.example.com"},
    )
    assert second_challenge.status_code == 200
    second_payload = second_challenge.json()
    remember_challenge(second_payload)

    _, pub2 = generate_ed25519_keypair()
    conflict_kid = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": second_payload["challenge_id"],
            "platform_id": "platform-002",
            "platform_aud": "platform-2",
            "domain": "platform2.example.com",
            "keys": [{"kid": "shared-kid", "public_key": pub2}],
        },
    )
    assert conflict_kid.status_code == 400
    assert "platform key kid already used by another platform" in conflict_kid.json()["detail"]

    third_challenge = client.post(
        "/v1/platforms/register/challenge",
        json={"platform_aud": "platform", "domain": "platform.example.com"},
    )
    assert third_challenge.status_code == 200
    third_payload = third_challenge.json()
    remember_challenge(third_payload)

    aud_conflict = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": third_payload["challenge_id"],
            "platform_id": "platform-override",
            "platform_aud": "platform",
            "domain": "platform.example.com",
            "keys": [{"kid": "new-kid", "public_key": pub2}],
        },
    )
    assert aud_conflict.status_code == 400
    assert "platform_aud already registered by another platform_id" in aud_conflict.json()["detail"]


def test_self_hosted_grant_revoke_and_list(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    admin_token = env["admin_token"]
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

    listing = client.get(
        f"/v1/agents/platform-grants/{agent.agent_id}",
        headers=admin_headers(admin_token),
    )
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

    with pytest.raises(TokenValidationError, match="unknown identity key id"):
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


def test_signer_requires_bound_hosted_management_token(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "hosted-auth")
    other = register_agent(client, "hosted-auth-other")

    missing = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": agent.agent_id, "name": "next", "ttl_seconds": 120},
    )
    assert missing.status_code == 401

    wrong = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": agent.agent_id, "name": "next", "ttl_seconds": 120},
        headers=hosted_headers(other),
    )
    assert wrong.status_code == 403

    ok = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": agent.agent_id, "name": "next", "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert ok.status_code == 200


def test_hosted_management_token_rotate_revoke_and_expiry(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "hosted-rotate")
    assert isinstance(agent.hosted_management_token_expires_at, int)
    assert agent.hosted_management_token_expires_at > now_ts()

    rotated = client.post(
        "/v1/signer/rotate_management_token",
        json={"agent_id": agent.agent_id},
        headers=hosted_headers(agent),
    )
    assert rotated.status_code == 200
    rotated_body = rotated.json()
    assert isinstance(rotated_body["hosted_management_token"], str)
    assert rotated_body["hosted_management_token"] != agent.hosted_management_token
    assert isinstance(rotated_body["hosted_management_token_expires_at"], int)

    old_sign = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": agent.agent_id, "name": "next-old", "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert old_sign.status_code == 403

    new_headers = {"Authorization": f"Bearer {rotated_body['hosted_management_token']}"}
    new_sign = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": agent.agent_id, "name": "next-new", "ttl_seconds": 120},
        headers=new_headers,
    )
    assert new_sign.status_code == 200

    service.hosted_management_tokens[agent.agent_id].expires_at = now_ts() - 1
    expired = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": agent.agent_id, "name": "expired", "ttl_seconds": 120},
        headers=new_headers,
    )
    assert expired.status_code == 403

    revoke_agent = register_agent(client, "hosted-revoke")
    revoked = client.post(
        "/v1/signer/revoke_management_token",
        json={"agent_id": revoke_agent.agent_id},
        headers=hosted_headers(revoke_agent),
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True
    after_revoke = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": revoke_agent.agent_id, "name": "blocked", "ttl_seconds": 120},
        headers=hosted_headers(revoke_agent),
    )
    assert after_revoke.status_code == 403


def test_upgrade_state_transitions_require_bound_management_auth(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "upgrade-auth-owner")
    other = register_agent(client, "upgrade-auth-other")

    l1_request_id = "upgrade-auth-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "owner-auth@example.com"},
    )
    assert created_l1.status_code == 200

    send_missing = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
    )
    assert send_missing.status_code == 401
    send_wrong = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(other),
    )
    assert send_wrong.status_code == 403
    send_ok = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert send_ok.status_code == 200
    verified_l1 = client.get("/v1/upgrades/l1/email/verify", params={"token": send_ok.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "upgrade-auth-l2"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200

    start_missing = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": l2_request_id, "provider": "github"},
    )
    assert start_missing.status_code == 401
    start_ok = client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": l2_request_id, "provider": "github"},
        headers=hosted_headers(agent),
    )
    assert start_ok.status_code == 200

    complete_missing = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "1", "login": "owner"},
        },
    )
    assert complete_missing.status_code == 401
    complete_ok = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "1", "login": "owner"},
        },
        headers=hosted_headers(agent),
    )
    assert complete_ok.status_code == 200


def test_read_endpoints_require_admin_or_bound_hosted_token(env: dict) -> None:
    client = env["client"]
    admin_token = env["admin_token"]
    agent = register_agent(client, "read-auth-agent")
    other = register_agent(client, "read-auth-other")

    list_missing = client.get(f"/v1/agents/platform-grants/{agent.agent_id}")
    assert list_missing.status_code == 401
    list_wrong = client.get(
        f"/v1/agents/platform-grants/{agent.agent_id}",
        headers=hosted_headers(other),
    )
    assert list_wrong.status_code == 403
    list_ok = client.get(
        f"/v1/agents/platform-grants/{agent.agent_id}",
        headers=hosted_headers(agent),
    )
    assert list_ok.status_code == 200
    list_admin = client.get(
        f"/v1/agents/platform-grants/{agent.agent_id}",
        headers=admin_headers(admin_token),
    )
    assert list_admin.status_code == 200

    request_id = "read-auth-upgrade"
    signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created = client.post("/v1/upgrades/requests", json={**signed, "contact_email": "read-auth@example.com"})
    assert created.status_code == 200

    get_missing = client.get(f"/v1/upgrades/requests/{request_id}")
    assert get_missing.status_code == 401
    get_wrong = client.get(
        f"/v1/upgrades/requests/{request_id}",
        headers=hosted_headers(other),
    )
    assert get_wrong.status_code == 403
    get_ok = client.get(
        f"/v1/upgrades/requests/{request_id}",
        headers=hosted_headers(agent),
    )
    assert get_ok.status_code == 200
    assert get_ok.json()["upgrade_request_id"] == request_id
    get_admin = client.get(
        f"/v1/upgrades/requests/{request_id}",
        headers=admin_headers(admin_token),
    )
    assert get_admin.status_code == 200

    self_hosted = register_self_hosted_agent(client, name="read-auth-self")
    assert self_hosted.private_key is not None

    self_list = client.get(
        f"/v1/agents/platform-grants/{self_hosted.agent_id}",
        headers=self_hosted_management_headers(
            agent_id=self_hosted.agent_id,
            private_key=self_hosted.private_key,
            operation="list_platform_grants",
            resource_id=self_hosted.agent_id,
        ),
    )
    assert self_list.status_code == 200

    self_request_id = "read-auth-self-upgrade"
    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(10)
    signed_payload = build_upgrade_request_payload(
        agent_id=self_hosted.agent_id,
        target_level="L1",
        request_id=self_request_id,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    self_signature = sign_detached(signed_payload, load_private_key(self_hosted.private_key))
    self_created = client.post(
        "/v1/upgrades/requests",
        json={
            "agent_id": self_hosted.agent_id,
            "target_level": "L1",
            "request_id": self_request_id,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": self_signature,
            "contact_email": "self-read@example.com",
        },
    )
    assert self_created.status_code == 200

    self_status = client.get(
        f"/v1/upgrades/requests/{self_request_id}",
        headers=self_hosted_management_headers(
            agent_id=self_hosted.agent_id,
            private_key=self_hosted.private_key,
            operation="upgrade_status",
            resource_id=self_request_id,
        ),
    )
    assert self_status.status_code == 200


def test_identity_library_write_requires_admin_bearer(env: dict) -> None:
    client = env["client"]
    admin_token = env["admin_token"]
    agent = register_agent(client, "admin-check")

    missing = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"risk_score": 0.2}},
    )
    assert missing.status_code == 401

    wrong = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"risk_score": 0.2}},
        headers={"Authorization": "Bearer wrong"},
    )
    assert wrong.status_code == 403

    ok = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"risk_score": 0.2}},
        headers=admin_headers(admin_token),
    )
    assert ok.status_code == 200

    sub_missing = client.post(
        "/v1/identity-library/subscriptions",
        json={
            "name": "risk-feed",
            "webhook_url": "https://example.com/hook",
            "fields": ["risk_score"],
            "event_types": ["risk_update"],
        },
    )
    assert sub_missing.status_code == 401

    sub_ok = client.post(
        "/v1/identity-library/subscriptions",
        json={
            "name": "risk-feed",
            "webhook_url": "https://example.com/hook",
            "fields": ["risk_score"],
            "event_types": ["risk_update"],
        },
        headers=admin_headers(admin_token),
    )
    assert sub_ok.status_code == 200

    list_missing = client.get("/v1/identity-library/subscriptions")
    assert list_missing.status_code == 401

    listed = client.get("/v1/identity-library/subscriptions", headers=admin_headers(admin_token))
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


def test_create_app_keeps_existing_admin_token_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RARE_ADMIN_TOKEN", raising=False)
    service = RareService(admin_token="preset-admin")
    client = TestClient(create_app(service))

    response = client.get(
        "/v1/identity-library/subscriptions",
        headers={"Authorization": "Bearer preset-admin"},
    )
    assert response.status_code == 200


def test_create_app_with_service_does_not_override_admin_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RARE_ADMIN_TOKEN", "env-admin")
    service = RareService(admin_token="preset-admin")
    client = TestClient(create_app(service))

    preset = client.get(
        "/v1/identity-library/subscriptions",
        headers={"Authorization": "Bearer preset-admin"},
    )
    assert preset.status_code == 200

    env = client.get(
        "/v1/identity-library/subscriptions",
        headers={"Authorization": "Bearer env-admin"},
    )
    assert env.status_code == 403


def test_upgrade_local_shortcuts_disabled_by_default() -> None:
    service = RareService(allow_local_upgrade_shortcuts=False)
    client = TestClient(create_app(service))
    agent = register_agent(client, "no-shortcuts")

    l1_request_id = "no-shortcuts-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "owner-no-shortcuts@example.com"},
    )
    assert created_l1.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    sent_body = sent.json()
    assert "token" not in sent_body
    assert "magic_link" not in sent_body

    service.agents[agent.agent_id].level = "L1"
    l2_request_id = "no-shortcuts-l2"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200
    direct_complete = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "42", "login": "shortcut"},
        },
        headers=hosted_headers(agent),
    )
    assert direct_complete.status_code == 403


def test_removed_deprecated_endpoints_return_404(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "removed-endpoint")

    removed_paths = [
        ("/v1/console/bind_owner", {"agent_id": agent.agent_id, "owner_id": "o-1"}),
        ("/v1/assets/twitter/connect", {"agent_id": agent.agent_id, "user_id": "1", "handle": "x"}),
        ("/v1/assets/github/connect", {"agent_id": agent.agent_id, "id": "1", "login": "x"}),
        ("/v1/attestations/upgrade", {"agent_id": agent.agent_id, "target_level": "L2"}),
        ("/v1/agents/hosted_sign_delegation", {"agent_id": agent.agent_id, "aud": "platform", "session_pubkey": agent.agent_id}),
    ]
    for path, payload in removed_paths:
        response = client.post(path, json=payload)
        assert response.status_code == 404


def test_signed_window_limit_enforced_for_signer_and_requests(env: dict) -> None:
    client = env["client"]
    hosted = register_agent(client, "ttl-hosted")
    ttl_too_long = client.post(
        "/v1/signer/sign_set_name",
        json={"agent_id": hosted.agent_id, "name": "next", "ttl_seconds": 301},
        headers=hosted_headers(hosted),
    )
    assert ttl_too_long.status_code == 400
    for path, payload in [
        ("/v1/signer/sign_platform_grant", {"agent_id": hosted.agent_id, "platform_aud": "platform", "ttl_seconds": 301}),
        (
            "/v1/signer/sign_full_attestation_issue",
            {"agent_id": hosted.agent_id, "platform_aud": "platform", "ttl_seconds": 301},
        ),
        (
            "/v1/signer/sign_upgrade_request",
            {"agent_id": hosted.agent_id, "target_level": "L1", "request_id": "ttl-upg", "ttl_seconds": 301},
        ),
    ]:
        rejected = client.post(path, json=payload, headers=hosted_headers(hosted))
        assert rejected.status_code == 400

    self_hosted = register_self_hosted_agent(client, name="ttl-self")
    assert self_hosted.private_key is not None
    issued_at = now_ts()
    expires_at = issued_at + 301
    nonce = generate_nonce(10)
    sign_input = build_set_name_payload(
        agent_id=self_hosted.agent_id,
        name="next",
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = sign_detached(sign_input, load_private_key(self_hosted.private_key))
    rejected = client.post(
        "/v1/agents/set_name",
        json={
            "agent_id": self_hosted.agent_id,
            "name": "next",
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        },
    )
    assert rejected.status_code == 400

    challenge = {
        "aud": "platform",
        "nonce": generate_nonce(8),
        "issued_at": now_ts(),
        "expires_at": now_ts() + 120,
    }
    prepared = client.post(
        "/v1/signer/prepare_auth",
        json={
            "agent_id": hosted.agent_id,
            "aud": challenge["aud"],
            "nonce": challenge["nonce"],
            "issued_at": challenge["issued_at"],
            "expires_at": challenge["expires_at"],
            "scope": ["post"],
            "delegation_ttl_seconds": 300,
        },
        headers=hosted_headers(hosted),
    )
    assert prepared.status_code == 200
    proof = prepared.json()
    issued_at_action = now_ts()
    action_rejected = client.post(
        "/v1/signer/sign_action",
        json={
            "agent_id": hosted.agent_id,
            "session_pubkey": proof["session_pubkey"],
            "session_token": "sess",
            "aud": "platform",
            "action": "post",
            "action_payload": {"content": "x"},
            "nonce": generate_nonce(8),
            "issued_at": issued_at_action,
            "expires_at": issued_at_action + 301,
        },
        headers=hosted_headers(hosted),
    )
    assert action_rejected.status_code == 400


def test_delegation_verifier_requires_jti(env: dict) -> None:
    del env
    private_key, public_key = generate_ed25519_keypair()
    token = sign_jws(
        payload={
            "typ": "rare.delegation",
            "ver": 1,
            "iss": "agent",
            "agent_id": public_key,
            "session_pubkey": public_key,
            "aud": "platform",
            "scope": ["login"],
            "iat": 0,
            "exp": 60,
            "act": "delegated_by_agent",
        },
        private_key=load_private_key(private_key),
        kid=f"agent-{public_key[:8]}",
        typ="rare.delegation+jws",
    )
    with pytest.raises(TokenValidationError):
        verify_delegation_token(
            token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=None,
            current_ts=0,
        )


def test_verifier_accepts_current_ts_zero_when_token_is_valid(env: dict) -> None:
    service = env["service"]
    signing_key = service.identity_keys[service.active_identity_kid]
    token = sign_jws(
        payload={
            "typ": "rare.identity",
            "ver": 1,
            "iss": "rare",
            "sub": "agent-ts0",
            "lvl": "L0",
            "claims": {"profile": {"name": "ts0"}},
            "iat": 0,
            "exp": 60,
            "jti": "ts0-token",
        },
        private_key=signing_key.private_key,
        kid=signing_key.kid,
        typ="rare.identity.public+jws",
    )
    verified = verify_identity_attestation(
        token,
        key_resolver=service.get_identity_public_key,
        current_ts=0,
    )
    assert verified.payload["iat"] == 0


def test_sign_delegation_endpoint_requires_bound_hosted_token_and_valid_ttl(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "deleg-sign")
    other = register_agent(client, "deleg-sign-other")
    _, session_pubkey = generate_ed25519_keypair()

    missing = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login", "post"],
            "ttl_seconds": 300,
        },
    )
    assert missing.status_code == 401
    assert "missing Authorization header" in missing.json()["detail"]

    wrong = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login", "post"],
            "ttl_seconds": 300,
        },
        headers=hosted_headers(other),
    )
    assert wrong.status_code == 403
    assert "invalid hosted management token" in wrong.json()["detail"]

    ttl_too_long = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login", "post"],
            "ttl_seconds": 3601,
        },
        headers=hosted_headers(agent),
    )
    assert ttl_too_long.status_code == 400
    assert "ttl_seconds exceeds max" in ttl_too_long.json()["detail"]

    bad_session = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": "bad-session-key",
            "aud": "platform",
            "scope": ["login", "post"],
            "ttl_seconds": 300,
        },
        headers=hosted_headers(agent),
    )
    assert bad_session.status_code == 400
    assert "invalid Ed25519 public key length" in bad_session.json()["detail"]

    ok = client.post(
        "/v1/signer/sign_delegation",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "aud": "platform",
            "scope": ["login", "post"],
            "ttl_seconds": 300,
        },
        headers=hosted_headers(agent),
    )
    assert ok.status_code == 200
    delegation = ok.json()["delegation_token"]
    verified = verify_delegation_token(
        delegation,
        expected_aud="platform",
        required_scope="post",
        rare_signer_public_key=service.get_rare_signer_public_key(),
    )
    assert verified.payload["agent_id"] == agent.agent_id
    assert verified.payload["iss"] == "rare-signer"


def test_refresh_attestation_endpoint_and_error_mapping(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "refresh")

    refreshed = client.post("/v1/attestations/refresh", json={"agent_id": agent.agent_id})
    assert refreshed.status_code == 200
    assert isinstance(refreshed.json()["public_identity_attestation"], str)

    missing = client.post("/v1/attestations/refresh", json={"agent_id": "agent-404"})
    assert missing.status_code == 404
    assert "agent not found" in missing.json()["detail"]


def test_identity_library_validates_profile_patch_and_subscription_fields(env: dict) -> None:
    client = env["client"]
    admin_token = env["admin_token"]
    agent = register_agent(client, "profile-validate")
    headers = admin_headers(admin_token)

    risk_score_too_high = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"risk_score": 1.2}},
        headers=headers,
    )
    assert risk_score_too_high.status_code == 400
    assert "risk_score must be between 0.0 and 1.0" in risk_score_too_high.json()["detail"]

    invalid_labels = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"labels": ["ok", 1]}},
        headers=headers,
    )
    assert invalid_labels.status_code == 400
    assert "labels must be string list" in invalid_labels.json()["detail"]

    invalid_summary = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"summary": 123}},
        headers=headers,
    )
    assert invalid_summary.status_code == 400
    assert "summary must be string" in invalid_summary.json()["detail"]

    invalid_metadata = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": {"metadata": []}},
        headers=headers,
    )
    assert invalid_metadata.status_code == 400
    assert "metadata must be object" in invalid_metadata.json()["detail"]

    empty_name = client.post(
        "/v1/identity-library/subscriptions",
        json={
            "name": "   ",
            "webhook_url": "https://example.com/hook",
            "fields": ["risk_score"],
            "event_types": ["risk_update"],
        },
        headers=headers,
    )
    assert empty_name.status_code == 400
    assert "subscription name cannot be empty" in empty_name.json()["detail"]

    invalid_webhook = client.post(
        "/v1/identity-library/subscriptions",
        json={
            "name": "risk-feed",
            "webhook_url": "ftp://example.com/hook",
            "fields": ["risk_score"],
            "event_types": ["risk_update"],
        },
        headers=headers,
    )
    assert invalid_webhook.status_code == 400
    assert "webhook_url must be http/https" in invalid_webhook.json()["detail"]


def test_platform_registration_validates_empty_duplicate_and_conflicting_keys(env: dict) -> None:
    client = env["client"]
    service = env["service"]

    def issue_challenge(platform_aud: str, domain: str) -> dict:
        response = client.post(
            "/v1/platforms/register/challenge",
            json={"platform_aud": platform_aud, "domain": domain},
        )
        assert response.status_code == 200
        challenge = response.json()
        service.dns_txt_resolver = (
            lambda name: [challenge["txt_value"]] if name == challenge["txt_name"] else []
        )
        return challenge

    challenge_empty = issue_challenge("platform-aud", "platform.example.com")
    empty_keys = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge_empty["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform-aud",
            "domain": "platform.example.com",
            "keys": [],
        },
    )
    assert empty_keys.status_code == 400
    assert "at least one platform key required" in empty_keys.json()["detail"]

    _, duplicate_key_pub = generate_ed25519_keypair()
    challenge_dup = issue_challenge("platform-aud", "platform.example.com")
    duplicate_kid = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge_dup["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform-aud",
            "domain": "platform.example.com",
            "keys": [
                {"kid": "dup-kid", "public_key": duplicate_key_pub},
                {"kid": "dup-kid", "public_key": duplicate_key_pub},
            ],
        },
    )
    assert duplicate_kid.status_code == 400
    assert "duplicate platform key kid" in duplicate_kid.json()["detail"]

    _, shared_key_pub = generate_ed25519_keypair()
    challenge_ok = issue_challenge("platform-aud", "platform.example.com")
    registered = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge_ok["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": "platform-aud",
            "domain": "platform.example.com",
            "keys": [{"kid": "shared-kid", "public_key": shared_key_pub}],
        },
    )
    assert registered.status_code == 200

    challenge_conflict_kid = issue_challenge("platform-aud-2", "platform2.example.com")
    conflict_kid = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge_conflict_kid["challenge_id"],
            "platform_id": "platform-002",
            "platform_aud": "platform-aud-2",
            "domain": "platform2.example.com",
            "keys": [{"kid": "shared-kid", "public_key": shared_key_pub}],
        },
    )
    assert conflict_kid.status_code == 400
    assert "platform key kid already used by another platform" in conflict_kid.json()["detail"]

    _, other_key_pub = generate_ed25519_keypair()
    challenge_conflict_aud = issue_challenge("platform-aud", "platform.example.com")
    conflict_aud = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge_conflict_aud["challenge_id"],
            "platform_id": "platform-999",
            "platform_aud": "platform-aud",
            "domain": "platform.example.com",
            "keys": [{"kid": "other-kid", "public_key": other_key_pub}],
        },
    )
    assert conflict_aud.status_code == 400
    assert "platform_aud already registered by another platform_id" in conflict_aud.json()["detail"]
