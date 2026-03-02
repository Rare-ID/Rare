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
    hosted_management_token: str | None = None


@pytest.fixture
def env() -> dict:
    rare_service, platform_service, rare_app, platform_app = create_runtime(allow_local_upgrade_shortcuts=True)
    return {
        "rare_service": rare_service,
        "platform_service": platform_service,
        "rare": TestClient(rare_app),
        "platform": TestClient(platform_app),
    }


def test_runtime_defaults_local_shortcuts_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS", raising=False)
    rare_service, _, _, _ = create_runtime()
    assert rare_service.allow_local_upgrade_shortcuts is False


def test_runtime_env_can_enable_local_shortcuts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS", "1")
    rare_service, _, _, _ = create_runtime()
    assert rare_service.allow_local_upgrade_shortcuts is True


def register_agent(rare_client: TestClient, name: str) -> RegisteredAgent:
    response = rare_client.post("/v1/agents/self_register", json={"name": name})
    assert response.status_code == 200
    body = response.json()
    return RegisteredAgent(
        agent_id=body["agent_id"],
        public_attestation=body["public_identity_attestation"],
        hosted_management_token=body["hosted_management_token"],
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


def hosted_headers(agent: RegisteredAgent) -> dict[str, str]:
    assert agent.hosted_management_token is not None
    return {"Authorization": f"Bearer {agent.hosted_management_token}"}


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
        headers=hosted_headers(agent),
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
    hosted_management_token: str,
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
        headers={"Authorization": f"Bearer {hosted_management_token}"},
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
    platform_id = f"{aud}-001"
    key_id = f"{aud}-k1"
    rare_service.dns_txt_resolver = (
        lambda name: [challenge["txt_value"]] if name == challenge["txt_name"] else []
    )
    complete = rare.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "platform_id": platform_id,
            "platform_aud": aud,
            "domain": "platform.example.com",
            "keys": [{"kid": key_id, "public_key": platform_public}],
        },
    )
    assert complete.status_code == 200


def upgrade_agent_to_l1(*, rare_client: TestClient, agent: RegisteredAgent, request_id: str, email: str) -> None:
    signed = rare_client.post(
        "/v1/signer/sign_upgrade_request",
        json={"agent_id": agent.agent_id, "target_level": "L1", "request_id": request_id, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert signed.status_code == 200
    created = rare_client.post(
        "/v1/upgrades/requests",
        json={**signed.json(), "contact_email": email},
    )
    assert created.status_code == 200
    sent = rare_client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified = rare_client.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified.status_code == 200
    agent.public_attestation = verified.json()["public_identity_attestation"]


def upgrade_agent_to_l2(*, rare_client: TestClient, agent: RegisteredAgent, request_id: str) -> None:
    signed = rare_client.post(
        "/v1/signer/sign_upgrade_request",
        json={"agent_id": agent.agent_id, "target_level": "L2", "request_id": request_id, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert signed.status_code == 200
    created = rare_client.post("/v1/upgrades/requests", json=signed.json())
    assert created.status_code == 200
    upgraded = rare_client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "42", "login": "rare-agent"},
        },
        headers=hosted_headers(agent),
    )
    assert upgraded.status_code == 200
    agent.public_attestation = upgraded.json()["public_identity_attestation"]


def issue_full_attestation_for_aud(*, rare_client: TestClient, agent: RegisteredAgent, aud: str) -> str:
    grant_signed = rare_client.post(
        "/v1/signer/sign_platform_grant",
        json={"agent_id": agent.agent_id, "platform_aud": aud, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert grant_signed.status_code == 200
    grant = rare_client.post("/v1/agents/platform-grants", json=grant_signed.json())
    assert grant.status_code == 200
    full_signed = rare_client.post(
        "/v1/signer/sign_full_attestation_issue",
        json={"agent_id": agent.agent_id, "platform_aud": aud, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert full_signed.status_code == 200
    issued = rare_client.post("/v1/attestations/full/issue", json=full_signed.json())
    assert issued.status_code == 200
    return issued.json()["full_identity_attestation"]


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
        hosted_management_token=agent.hosted_management_token or "",
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
        hosted_management_token=agent.hosted_management_token or "",
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
        headers=hosted_headers(agent_a),
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
            hosted_management_token=agent.hosted_management_token or "",
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
    l1_request_id = "cap-l2-l1"
    l1_signed = rare.post(
        "/v1/signer/sign_upgrade_request",
        json={"agent_id": agent.agent_id, "target_level": "L1", "request_id": l1_request_id, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert l1_signed.status_code == 200
    created_l1 = rare.post(
        "/v1/upgrades/requests",
        json={**l1_signed.json(), "contact_email": "owner-cap@example.com"},
    )
    assert created_l1.status_code == 200
    sent = rare.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified_l1 = rare.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "cap-l2-l2"
    l2_signed = rare.post(
        "/v1/signer/sign_upgrade_request",
        json={"agent_id": agent.agent_id, "target_level": "L2", "request_id": l2_request_id, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert l2_signed.status_code == 200
    created_l2 = rare.post("/v1/upgrades/requests", json=l2_signed.json())
    assert created_l2.status_code == 200
    upgraded = rare.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "100", "login": "rare-agent"},
        },
        headers=hosted_headers(agent),
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
    l1_request_id = "full-l2-l1"
    l1_signed = rare.post(
        "/v1/signer/sign_upgrade_request",
        json={"agent_id": agent.agent_id, "target_level": "L1", "request_id": l1_request_id, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert l1_signed.status_code == 200
    created_l1 = rare.post(
        "/v1/upgrades/requests",
        json={**l1_signed.json(), "contact_email": "owner-full@example.com"},
    )
    assert created_l1.status_code == 200
    sent = rare.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified_l1 = rare.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "full-l2-l2"
    l2_signed = rare.post(
        "/v1/signer/sign_upgrade_request",
        json={"agent_id": agent.agent_id, "target_level": "L2", "request_id": l2_request_id, "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert l2_signed.status_code == 200
    created_l2 = rare.post("/v1/upgrades/requests", json=l2_signed.json())
    assert created_l2.status_code == 200
    upgraded = rare.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "x",
            "provider_user_snapshot": {"id": "200", "handle": "rare-agent"},
        },
        headers=hosted_headers(agent),
    )
    assert upgraded.status_code == 200
    agent.public_attestation = upgraded.json()["public_identity_attestation"]

    register_platform_for_full_login(env, aud="platform")
    grant_signed = rare.post(
        "/v1/signer/sign_platform_grant",
        json={"agent_id": agent.agent_id, "platform_aud": "platform", "ttl_seconds": 120},
        headers=hosted_headers(agent),
    )
    assert grant_signed.status_code == 200
    grant_ok = rare.post("/v1/agents/platform-grants", json=grant_signed.json())
    assert grant_ok.status_code == 200

    full_signed = rare.post(
        "/v1/signer/sign_full_attestation_issue",
        json={"agent_id": agent.agent_id, "platform_aud": "platform", "ttl_seconds": 120},
        headers=hosted_headers(agent),
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


def test_platform_applies_l1_comment_rate_limit(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]
    agent = register_agent(rare, "l1-comment-rate")
    upgrade_agent_to_l1(
        rare_client=rare,
        agent=agent,
        request_id="l1-comment-rate-upg",
        email="l1-comment@example.com",
    )
    login = login_platform(rare_client=rare, platform_client=platform, agent=agent)
    assert login["response"].status_code == 200
    session = login["response"].json()

    signed_post = sign_action(
        rare_client=rare,
        agent_id=agent.agent_id,
        session_pubkey=login["proof"]["session_pubkey"],
        session_token=session["session_token"],
        action="post",
        action_payload={"content": "seed-post"},
        hosted_management_token=agent.hosted_management_token or "",
    )
    post = platform.post(
        "/posts",
        json={
            "content": "seed-post",
            "nonce": signed_post["nonce"],
            "issued_at": signed_post["issued_at"],
            "expires_at": signed_post["expires_at"],
            "signature_by_session": signed_post["signature_by_session"],
        },
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert post.status_code == 200
    post_id = post.json()["id"]

    statuses = []
    for idx in range(21):
        signed_comment = sign_action(
            rare_client=rare,
            agent_id=agent.agent_id,
            session_pubkey=login["proof"]["session_pubkey"],
            session_token=session["session_token"],
            action="comment",
            action_payload={"post_id": post_id, "content": f"c-{idx}"},
            hosted_management_token=agent.hosted_management_token or "",
        )
        comment = platform.post(
            "/comments",
            json={
                "post_id": post_id,
                "content": f"c-{idx}",
                "nonce": signed_comment["nonce"],
                "issued_at": signed_comment["issued_at"],
                "expires_at": signed_comment["expires_at"],
                "signature_by_session": signed_comment["signature_by_session"],
            },
            headers={"Authorization": f"Bearer {session['session_token']}"},
        )
        statuses.append(comment.status_code)

    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_platform_applies_l1_post_rate_limit(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]
    agent = register_agent(rare, "l1-post-rate")
    upgrade_agent_to_l1(
        rare_client=rare,
        agent=agent,
        request_id="l1-post-rate-upg",
        email="l1-post@example.com",
    )
    login = login_platform(rare_client=rare, platform_client=platform, agent=agent)
    assert login["response"].status_code == 200
    session = login["response"].json()

    statuses = []
    for idx in range(11):
        signed = sign_action(
            rare_client=rare,
            agent_id=agent.agent_id,
            session_pubkey=login["proof"]["session_pubkey"],
            session_token=session["session_token"],
            action="post",
            action_payload={"content": f"l1-post-{idx}"},
            hosted_management_token=agent.hosted_management_token or "",
        )
        post = platform.post(
            "/posts",
            json={
                "content": f"l1-post-{idx}",
                "nonce": signed["nonce"],
                "issued_at": signed["issued_at"],
                "expires_at": signed["expires_at"],
                "signature_by_session": signed["signature_by_session"],
            },
            headers={"Authorization": f"Bearer {session['session_token']}"},
        )
        statuses.append(post.status_code)

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_platform_applies_l2_post_rate_limit(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]
    agent = register_agent(rare, "l2-post-rate")
    upgrade_agent_to_l1(
        rare_client=rare,
        agent=agent,
        request_id="l2-post-rate-l1",
        email="l2-post@example.com",
    )
    upgrade_agent_to_l2(rare_client=rare, agent=agent, request_id="l2-post-rate-l2")
    register_platform_for_full_login(env, aud="platform")
    full_attestation = issue_full_attestation_for_aud(rare_client=rare, agent=agent, aud="platform")
    login = login_platform(
        rare_client=rare,
        platform_client=platform,
        agent=agent,
        full_attestation=full_attestation,
    )
    assert login["response"].status_code == 200
    assert login["response"].json()["level"] == "L2"
    session = login["response"].json()

    statuses = []
    for idx in range(31):
        signed = sign_action(
            rare_client=rare,
            agent_id=agent.agent_id,
            session_pubkey=login["proof"]["session_pubkey"],
            session_token=session["session_token"],
            action="post",
            action_payload={"content": f"l2-post-{idx}"},
            hosted_management_token=agent.hosted_management_token or "",
        )
        post = platform.post(
            "/posts",
            json={
                "content": f"l2-post-{idx}",
                "nonce": signed["nonce"],
                "issued_at": signed["issued_at"],
                "expires_at": signed["expires_at"],
                "signature_by_session": signed["signature_by_session"],
            },
            headers={"Authorization": f"Bearer {session['session_token']}"},
        )
        statuses.append(post.status_code)

    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


def test_platform_applies_l2_comment_rate_limit(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]
    agent = register_agent(rare, "l2-comment-rate")
    upgrade_agent_to_l1(
        rare_client=rare,
        agent=agent,
        request_id="l2-comment-rate-l1",
        email="l2-comment@example.com",
    )
    upgrade_agent_to_l2(rare_client=rare, agent=agent, request_id="l2-comment-rate-l2")
    register_platform_for_full_login(env, aud="platform")
    full_attestation = issue_full_attestation_for_aud(rare_client=rare, agent=agent, aud="platform")
    login = login_platform(
        rare_client=rare,
        platform_client=platform,
        agent=agent,
        full_attestation=full_attestation,
    )
    assert login["response"].status_code == 200
    assert login["response"].json()["level"] == "L2"
    session = login["response"].json()

    signed_post = sign_action(
        rare_client=rare,
        agent_id=agent.agent_id,
        session_pubkey=login["proof"]["session_pubkey"],
        session_token=session["session_token"],
        action="post",
        action_payload={"content": "seed-l2-comment-post"},
        hosted_management_token=agent.hosted_management_token or "",
    )
    post = platform.post(
        "/posts",
        json={
            "content": "seed-l2-comment-post",
            "nonce": signed_post["nonce"],
            "issued_at": signed_post["issued_at"],
            "expires_at": signed_post["expires_at"],
            "signature_by_session": signed_post["signature_by_session"],
        },
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert post.status_code == 200
    post_id = post.json()["id"]

    statuses = []
    for idx in range(61):
        signed_comment = sign_action(
            rare_client=rare,
            agent_id=agent.agent_id,
            session_pubkey=login["proof"]["session_pubkey"],
            session_token=session["session_token"],
            action="comment",
            action_payload={"post_id": post_id, "content": f"l2-c-{idx}"},
            hosted_management_token=agent.hosted_management_token or "",
        )
        comment = platform.post(
            "/comments",
            json={
                "post_id": post_id,
                "content": f"l2-c-{idx}",
                "nonce": signed_comment["nonce"],
                "issued_at": signed_comment["issued_at"],
                "expires_at": signed_comment["expires_at"],
                "signature_by_session": signed_comment["signature_by_session"],
            },
            headers={"Authorization": f"Bearer {session['session_token']}"},
        )
        statuses.append(comment.status_code)

    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429


def test_platform_rejects_invalid_action_windows_and_unknown_session(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]
    agent = register_self_hosted_agent(rare, "window-self")
    assert agent.agent_private_key is not None

    challenge = platform.post("/auth/challenge", json={"aud": "platform"}).json()
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

    def signed_post_payload(*, issued_at: int, expires_at: int, nonce: str) -> dict:
        sign_input = build_action_payload(
            aud="platform",
            session_token=session["session_token"],
            action="post",
            action_payload={"content": "window"},
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return {
            "content": "window",
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_session": sign_detached(sign_input, load_private_key(session_private_key)),
        }

    now = now_ts()
    future = platform.post(
        "/posts",
        json=signed_post_payload(
            issued_at=now + 31,
            expires_at=now + 91,
            nonce=generate_nonce(8),
        ),
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert future.status_code == 400
    assert "issued_at too far in future" in future.json()["detail"]

    expired = platform.post(
        "/posts",
        json=signed_post_payload(
            issued_at=now - 120,
            expires_at=now - 80,
            nonce=generate_nonce(8),
        ),
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert expired.status_code == 400
    assert "action expired" in expired.json()["detail"]

    too_long = platform.post(
        "/posts",
        json=signed_post_payload(
            issued_at=now,
            expires_at=now + 301,
            nonce=generate_nonce(8),
        ),
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert too_long.status_code == 400
    assert "action ttl exceeds max 300 seconds" in too_long.json()["detail"]

    unknown_session = platform.post(
        "/posts",
        json=signed_post_payload(
            issued_at=now,
            expires_at=now + 60,
            nonce=generate_nonce(8),
        ),
        headers={"Authorization": "Bearer unknown-session"},
    )
    assert unknown_session.status_code == 403
    assert "invalid session token" in unknown_session.json()["detail"]


def test_platform_comment_rejects_unknown_post_id(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]
    agent = register_agent(rare, "comment-404")
    login = login_platform(rare_client=rare, platform_client=platform, agent=agent)
    assert login["response"].status_code == 200
    session = login["response"].json()

    signed = sign_action(
        rare_client=rare,
        agent_id=agent.agent_id,
        session_pubkey=login["proof"]["session_pubkey"],
        session_token=session["session_token"],
        action="comment",
        action_payload={"post_id": "post-404", "content": "missing"},
        hosted_management_token=agent.hosted_management_token or "",
    )
    response = platform.post(
        "/comments",
        json={
            "post_id": "post-404",
            "content": "missing",
            "nonce": signed["nonce"],
            "issued_at": signed["issued_at"],
            "expires_at": signed["expires_at"],
            "signature_by_session": signed["signature_by_session"],
        },
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    assert response.status_code == 404
    assert "post not found" in response.json()["detail"]


def test_platform_rejects_full_attestation_aud_mismatch(env: dict) -> None:
    rare = env["rare"]
    platform = env["platform"]
    agent = register_agent(rare, "full-aud-mismatch")
    upgrade_agent_to_l1(
        rare_client=rare,
        agent=agent,
        request_id="full-aud-l1",
        email="full-aud@example.com",
    )
    upgrade_agent_to_l2(rare_client=rare, agent=agent, request_id="full-aud-l2")

    register_platform_for_full_login(env, aud="platform-2")
    wrong_full_attestation = issue_full_attestation_for_aud(
        rare_client=rare,
        agent=agent,
        aud="platform-2",
    )
    login = login_platform(
        rare_client=rare,
        platform_client=platform,
        agent=agent,
        full_attestation=wrong_full_attestation,
    )
    assert login["response"].status_code == 400
    assert "identity full token aud mismatch" in login["response"].json()["detail"]


def test_platform_rejects_expired_challenge() -> None:
    _, platform_service, rare_app, platform_app = create_runtime(
        challenge_ttl_seconds=1,
        allow_local_upgrade_shortcuts=True,
    )
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
        headers=hosted_headers(agent),
    ).json()

    challenge_record = platform_service.challenges.get(challenge["nonce"])
    assert challenge_record is not None
    challenge_record.expires_at = now_ts() - 31
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
