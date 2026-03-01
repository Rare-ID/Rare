from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from apps.runtime import create_runtime
from rare_identity_protocol import (
    build_action_payload,
    build_auth_challenge_payload,
    build_register_payload,
    generate_ed25519_keypair,
    generate_nonce,
    issue_agent_delegation,
    load_private_key,
    now_ts,
    sign_detached,
)


@dataclass
class RegisteredAgent:
    agent_id: str
    public_attestation: str
    agent_private_key: str | None = None


@pytest.fixture
def env() -> dict:
    rare_service, platform_service, rare_app, platform_app = create_runtime()
    return {
        "rare_service": rare_service,
        "platform_service": platform_service,
        "rare": TestClient(rare_app),
        "platform": TestClient(platform_app),
    }


def register_agent(rare_client: TestClient, name: str) -> RegisteredAgent:
    response = rare_client.post("/v1/agents/self_register", json={"name": name})
    assert response.status_code == 200
    body = response.json()
    return RegisteredAgent(
        agent_id=body["agent_id"],
        public_attestation=body["public_identity_attestation"],
    )


def register_self_hosted_agent(rare_client: TestClient, name: str) -> RegisteredAgent:
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

    response = rare_client.post(
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
        agent_private_key=private_key,
    )


def login_platform(
    *,
    rare_client: TestClient,
    platform_client: TestClient,
    agent: RegisteredAgent,
    aud: str = "platform",
    full_attestation: str | None = None,
) -> dict:
    challenge_response = platform_client.post("/auth/challenge", json={"aud": aud})
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()

    proof = rare_client.post(
        "/v1/signer/prepare_auth",
        json={
            "agent_id": agent.agent_id,
            "aud": aud,
            "nonce": challenge["nonce"],
            "issued_at": challenge["issued_at"],
            "expires_at": challenge["expires_at"],
            "scope": ["login", "post", "comment"],
            "delegation_ttl_seconds": 3600,
        },
    )
    assert proof.status_code == 200
    signed = proof.json()

    response = platform_client.post(
        "/auth/complete",
        json={
            "nonce": challenge["nonce"],
            "agent_id": agent.agent_id,
            "session_pubkey": signed["session_pubkey"],
            "delegation_token": signed["delegation_token"],
            "signature_by_session": signed["signature_by_session"],
            "public_identity_attestation": agent.public_attestation,
            "full_identity_attestation": full_attestation,
        },
    )
    return {
        "response": response,
        "challenge": challenge,
        "proof": signed,
    }


def sign_action(
    *,
    rare_client: TestClient,
    agent_id: str,
    session_pubkey: str,
    session_token: str,
    action: str,
    action_payload: dict,
    aud: str = "platform",
) -> dict:
    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(8)

    response = rare_client.post(
        "/v1/signer/sign_action",
        json={
            "agent_id": agent_id,
            "session_pubkey": session_pubkey,
            "session_token": session_token,
            "aud": aud,
            "action": action,
            "action_payload": action_payload,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
        },
    )
    assert response.status_code == 200
    return response.json()


def register_platform_for_full_login(env: dict, *, aud: str = "platform") -> None:
    rare = env["rare"]
    rare_service = env["rare_service"]
    challenge_resp = rare.post(
        "/v1/platforms/register/challenge",
        json={"platform_aud": aud, "domain": "platform.example.com"},
    )
    assert challenge_resp.status_code == 200
    challenge = challenge_resp.json()

    platform_private, platform_public = generate_ed25519_keypair()
    del platform_private
    rare_service.dns_txt_resolver = (
        lambda name: [challenge["txt_value"]] if name == challenge["txt_name"] else []
    )
    complete = rare.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "platform_id": "platform-001",
            "platform_aud": aud,
            "domain": "platform.example.com",
            "keys": [{"kid": "platform-k1", "public_key": platform_public}],
        },
    )
    assert complete.status_code == 200


def test_cross_repo_e2e_register_in_core_then_login_post_comment(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]

    agent = register_agent(rare, "neo")
    login = login_platform(rare_client=rare, platform_client=platform, agent=agent)
    assert login["response"].status_code == 200

    session = login["response"].json()
    signed_post = sign_action(
        rare_client=rare,
        agent_id=agent.agent_id,
        session_pubkey=login["proof"]["session_pubkey"],
        session_token=session["session_token"],
        action="post",
        action_payload={"content": "hello world"},
    )

    post = platform.post(
        "/posts",
        json={
            "content": "hello world",
            "nonce": signed_post["nonce"],
            "issued_at": signed_post["issued_at"],
            "expires_at": signed_post["expires_at"],
            "signature_by_session": signed_post["signature_by_session"],
        },
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert post.status_code == 200

    signed_comment = sign_action(
        rare_client=rare,
        agent_id=agent.agent_id,
        session_pubkey=login["proof"]["session_pubkey"],
        session_token=session["session_token"],
        action="comment",
        action_payload={"post_id": post.json()["id"], "content": "first"},
    )

    comment = platform.post(
        "/comments",
        json={
            "post_id": post.json()["id"],
            "content": "first",
            "nonce": signed_comment["nonce"],
            "issued_at": signed_comment["issued_at"],
            "expires_at": signed_comment["expires_at"],
            "signature_by_session": signed_comment["signature_by_session"],
        },
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert comment.status_code == 200


def test_cross_repo_e2e_self_hosted_login_and_post(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]

    agent = register_self_hosted_agent(rare, "neo-self")
    assert agent.agent_private_key is not None

    challenge_response = platform.post("/auth/challenge", json={"aud": "platform"})
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()

    session_private_key, session_pubkey = generate_ed25519_keypair()
    auth_sign_input = build_auth_challenge_payload(
        aud="platform",
        nonce=challenge["nonce"],
        issued_at=challenge["issued_at"],
        expires_at=challenge["expires_at"],
    )
    signature_by_session = sign_detached(auth_sign_input, load_private_key(session_private_key))
    delegation = issue_agent_delegation(
        agent_id=agent.agent_id,
        session_pubkey=session_pubkey,
        aud="platform",
        scope=["login", "post"],
        signer_private_key=load_private_key(agent.agent_private_key),
        kid=f"agent-{agent.agent_id[:8]}",
        ttl_seconds=3600,
        jti=generate_nonce(12),
    )

    login_response = platform.post(
        "/auth/complete",
        json={
            "nonce": challenge["nonce"],
            "agent_id": agent.agent_id,
            "session_pubkey": session_pubkey,
            "delegation_token": delegation,
            "signature_by_session": signature_by_session,
            "public_identity_attestation": agent.public_attestation,
        },
    )
    assert login_response.status_code == 200
    session = login_response.json()

    issued_at = now_ts()
    expires_at = issued_at + 120
    nonce = generate_nonce(8)
    action_sign_input = build_action_payload(
        aud="platform",
        session_token=session["session_token"],
        action="post",
        action_payload={"content": "hello-self"},
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    action_signature = sign_detached(action_sign_input, load_private_key(session_private_key))

    post = platform.post(
        "/posts",
        json={
            "content": "hello-self",
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_session": action_signature,
        },
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert post.status_code == 200


def test_platform_rejects_identity_triad_mismatch(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]

    agent_a = register_agent(rare, "A")
    agent_b = register_agent(rare, "B")

    challenge = platform.post("/auth/challenge", json={"aud": "platform"}).json()
    proof = rare.post(
        "/v1/signer/prepare_auth",
        json={
            "agent_id": agent_a.agent_id,
            "aud": "platform",
            "nonce": challenge["nonce"],
            "issued_at": challenge["issued_at"],
            "expires_at": challenge["expires_at"],
            "scope": ["login"],
            "delegation_ttl_seconds": 300,
        },
    ).json()

    response = platform.post(
        "/auth/complete",
        json={
            "nonce": challenge["nonce"],
            "agent_id": agent_b.agent_id,
            "session_pubkey": proof["session_pubkey"],
            "delegation_token": proof["delegation_token"],
            "signature_by_session": proof["signature_by_session"],
            "public_identity_attestation": agent_a.public_attestation,
        },
    )

    assert response.status_code == 400


def test_platform_rejects_nonce_replay_and_aud_mismatch(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]

    agent = register_agent(rare, "Replay")

    ok = login_platform(rare_client=rare, platform_client=platform, agent=agent)
    assert ok["response"].status_code == 200

    replay = platform.post(
        "/auth/complete",
        json={
            "nonce": ok["challenge"]["nonce"],
            "agent_id": agent.agent_id,
            "session_pubkey": ok["proof"]["session_pubkey"],
            "delegation_token": ok["proof"]["delegation_token"],
            "signature_by_session": ok["proof"]["signature_by_session"],
            "public_identity_attestation": agent.public_attestation,
        },
    )
    assert replay.status_code == 409

    wrong_aud = platform.post("/auth/challenge", json={"aud": "other-platform"})
    assert wrong_aud.status_code == 400


def test_platform_applies_l0_rate_limit(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]

    agent = register_agent(rare, "rate")
    login = login_platform(rare_client=rare, platform_client=platform, agent=agent)
    assert login["response"].status_code == 200
    session = login["response"].json()

    def create_post(content: str) -> TestClient:
        signed = sign_action(
            rare_client=rare,
            agent_id=agent.agent_id,
            session_pubkey=login["proof"]["session_pubkey"],
            session_token=session["session_token"],
            action="post",
            action_payload={"content": content},
        )
        return platform.post(
            "/posts",
            json={
                "content": content,
                "nonce": signed["nonce"],
                "issued_at": signed["issued_at"],
                "expires_at": signed["expires_at"],
                "signature_by_session": signed["signature_by_session"],
            },
            headers={"Authorization": f"Bearer {session['session_token']}"},
        )

    first = create_post("1")
    second = create_post("2")
    third = create_post("3")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_unregistered_platform_login_caps_l2_agent_to_l1(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]

    agent = register_agent(rare, "cap-l2")
    bind = rare.post(
        "/v1/console/bind_owner",
        json={"agent_id": agent.agent_id, "owner_id": "owner-1", "org_id": "org-1"},
    )
    assert bind.status_code == 200
    social = rare.post(
        "/v1/assets/github/connect",
        json={"agent_id": agent.agent_id, "id": "100", "login": "rare-agent"},
    )
    assert social.status_code == 200
    upgraded = rare.post(
        "/v1/attestations/upgrade",
        json={"agent_id": agent.agent_id, "target_level": "L2"},
    )
    assert upgraded.status_code == 200
    agent.public_attestation = upgraded.json()["public_identity_attestation"]

    login = login_platform(rare_client=rare, platform_client=platform, agent=agent)
    assert login["response"].status_code == 200
    assert login["response"].json()["level"] == "L1"


def test_registered_platform_can_login_with_full_attestation_l2(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]

    agent = register_agent(rare, "full-l2")
    bind = rare.post(
        "/v1/console/bind_owner",
        json={"agent_id": agent.agent_id, "owner_id": "owner-2", "org_id": "org-2"},
    )
    assert bind.status_code == 200
    social = rare.post(
        "/v1/assets/twitter/connect",
        json={"agent_id": agent.agent_id, "user_id": "200", "handle": "rare-agent"},
    )
    assert social.status_code == 200
    upgraded = rare.post(
        "/v1/attestations/upgrade",
        json={"agent_id": agent.agent_id, "target_level": "L2"},
    )
    assert upgraded.status_code == 200
    agent.public_attestation = upgraded.json()["public_identity_attestation"]

    register_platform_for_full_login(env, aud="platform")
    grant_signed = rare.post(
        "/v1/signer/sign_platform_grant",
        json={"agent_id": agent.agent_id, "platform_aud": "platform", "ttl_seconds": 120},
    )
    assert grant_signed.status_code == 200
    grant_ok = rare.post("/v1/agents/platform-grants", json=grant_signed.json())
    assert grant_ok.status_code == 200

    full_signed = rare.post(
        "/v1/signer/sign_full_attestation_issue",
        json={"agent_id": agent.agent_id, "platform_aud": "platform", "ttl_seconds": 120},
    )
    assert full_signed.status_code == 200
    full_issue = rare.post("/v1/attestations/full/issue", json=full_signed.json())
    assert full_issue.status_code == 200
    full_attestation = full_issue.json()["full_identity_attestation"]

    login = login_platform(
        rare_client=rare,
        platform_client=platform,
        agent=agent,
        full_attestation=full_attestation,
    )
    assert login["response"].status_code == 200
    assert login["response"].json()["level"] == "L2"


def test_platform_rejects_expired_challenge() -> None:
    _, platform_service, rare_app, platform_app = create_runtime(challenge_ttl_seconds=1)
    rare = TestClient(rare_app)
    platform = TestClient(platform_app)

    agent = register_agent(rare, "expired")
    challenge = platform.post("/auth/challenge", json={"aud": "platform"}).json()

    proof = rare.post(
        "/v1/signer/prepare_auth",
        json={
            "agent_id": agent.agent_id,
            "aud": "platform",
            "nonce": challenge["nonce"],
            "issued_at": challenge["issued_at"],
            "expires_at": challenge["expires_at"],
            "scope": ["login"],
            "delegation_ttl_seconds": 300,
        },
    ).json()

    platform_service.challenges[challenge["nonce"]].expires_at = now_ts() - 31
    response = platform.post(
        "/auth/complete",
        json={
            "nonce": challenge["nonce"],
            "agent_id": agent.agent_id,
            "session_pubkey": proof["session_pubkey"],
            "delegation_token": proof["delegation_token"],
            "signature_by_session": proof["signature_by_session"],
            "public_identity_attestation": agent.public_attestation,
        },
    )
    assert response.status_code == 400
