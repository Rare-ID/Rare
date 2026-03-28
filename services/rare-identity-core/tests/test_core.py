from __future__ import annotations

import base64
import builtins
import pickle
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from rare_api.integrations import (
    GcpKmsEd25519JwsSigner,
    GcpKmsHostedKeyCipher,
    GitHubOAuthAdapter,
    LinkedInOAuthAdapter,
    LocalAesGcmHostedKeyCipher,
    LocalEd25519JwsSigner,
    NoopEmailProvider,
    PlaintextHostedKeyCipher,
    resolve_public_dns_txt,
    SendGridEmailProvider,
    StubSocialProviderAdapter,
    XOAuthAdapter,
    default_social_provider_adapters,
)
from rare_api.key_provider import EphemeralKeyProvider, FileKeyProvider, GcpSecretManagerKeyProvider
from rare_api.main import create_app
from rare_api.service import RareService
from rare_api.state_store import (
    PostgresRedisStateStore,
    SqliteStateStore,
    _RedisBackedExpiringMap,
    _RedisBackedExpiringSet,
)
from rare_identity_protocol import (
    TokenValidationError,
    build_action_payload,
    build_agent_auth_payload,
    build_auth_challenge_payload,
    build_register_payload,
    build_set_name_payload,
    build_upgrade_request_payload,
    generate_ed25519_keypair,
    generate_nonce,
    issue_agent_delegation,
    load_private_key,
    load_public_key,
    now_ts,
    public_key_to_b64,
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


class FakeHttpResponse:
    def __init__(self, *, status_code: int = 200, json_body: dict | None = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._json_body = json_body or {}
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict:
        return self._json_body


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def post(self, url: str, **kwargs: dict) -> FakeHttpResponse:
        self.calls.append(("POST", url, kwargs))
        if url.endswith("/access_token"):
            return FakeHttpResponse(json_body={"access_token": "gh-token"})
        return FakeHttpResponse(status_code=202, headers={"x-message-id": "sg-message-1"})

    def get(self, url: str, **kwargs: dict) -> FakeHttpResponse:
        self.calls.append(("GET", url, kwargs))
        return FakeHttpResponse(
            json_body={
                "id": 123,
                "login": "rare-agent",
                "name": "Rare Agent",
                "html_url": "https://github.com/rare-agent",
            }
        )


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[bytes, bytes] = {}
        self.ttls: dict[bytes, int] = {}

    def scan_iter(self, *, match: str) -> list[bytes]:
        prefix = match.removesuffix("*").encode("utf-8")
        return [key for key in self.values if key.startswith(prefix)]

    def get(self, key: bytes) -> bytes | None:
        return self.values.get(key)

    def ttl(self, key: bytes) -> int | None:
        return self.ttls.get(key)


class FakeSecretPayload:
    def __init__(self, data: bytes) -> None:
        self.data = data


class FakeSecretVersionResponse:
    def __init__(self, data: bytes) -> None:
        self.payload = FakeSecretPayload(data)


class FakeSecretManagerClient:
    class NotFound(Exception):
        pass

    def __init__(self) -> None:
        self.secrets: dict[str, list[bytes]] = {}

    @staticmethod
    def secret_path(project_id: str, secret_id: str) -> str:
        return f"projects/{project_id}/secrets/{secret_id}"

    def get_secret(self, request: dict) -> dict:
        name = request["name"]
        if name not in self.secrets:
            raise self.NotFound(name)
        return {"name": name}

    def create_secret(self, request: dict) -> dict:
        parent = request["parent"]
        secret_id = request["secret_id"]
        secret_path = f"{parent}/secrets/{secret_id}"
        self.secrets.setdefault(secret_path, [])
        return {"name": secret_path}

    def add_secret_version(self, request: dict) -> dict:
        parent = request["parent"]
        data = bytes(request["payload"]["data"])
        self.secrets.setdefault(parent, []).append(data)
        return {"name": f"{parent}/versions/{len(self.secrets[parent])}"}

    def access_secret_version(self, request: dict) -> FakeSecretVersionResponse:
        name = request["name"]
        parent = name.removesuffix("/versions/latest")
        versions = self.secrets.get(parent)
        if not versions:
            raise self.NotFound(name)
        return FakeSecretVersionResponse(versions[-1])


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
    platform_suffix = aud.replace("_", "-").replace(":", "-")
    platform_id = f"platform-{platform_suffix}"
    key_id = f"{platform_id}-k1"
    register_response = client.post(
        "/v1/platforms/register/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "platform_id": platform_id,
            "platform_aud": aud,
            "domain": "platform.example.com",
            "keys": [{"kid": key_id, "public_key": platform_public}],
        },
    )
    assert register_response.status_code == 200
    return RegisteredPlatform(
        platform_aud=aud,
        platform_id=platform_id,
        key_id=key_id,
        private_key=platform_private,
    )


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
    service = env["service"]
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
    session = service.hosted_session_keys.get(proof["session_pubkey"])
    assert session is not None
    pickle.dumps(session, protocol=pickle.HIGHEST_PROTOCOL)

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
    assert {item["rare_role"] for item in body["keys"]} >= {"identity", "delegation"}

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
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": sent.json()["token"]})
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
    created_body = created.json()
    assert created_body["status"] == "human_pending"
    assert created_body["next_step"] == "verify_email"
    assert created_body["email_delivery"]["state"] == "queued"
    assert created_body["email_delivery"]["attempt_count"] == 1

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
    sent_body = sent.json()
    assert "?" not in sent_body["magic_link"]
    assert sent_body["email_delivery"]["attempt_count"] == 2
    token = sent_body["token"]
    verified = client.post("/v1/upgrades/l1/email/verify", json={"token": token})
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

    reused = client.post("/v1/upgrades/l1/email/verify", json={"token": token})
    assert reused.status_code == 400


def test_upgrade_l1_rejects_email_already_linked_to_another_agent(env: dict) -> None:
    client = env["client"]
    first_agent = register_agent(client, "upgrade-l1-owner-a")
    second_agent = register_agent(client, "upgrade-l1-owner-b")

    first_request_id = "upg-l1-owner-a"
    signed_first = sign_hosted_upgrade_request(
        client,
        agent_id=first_agent.agent_id,
        target_level="L1",
        request_id=first_request_id,
        hosted_management_token=first_agent.hosted_management_token or "",
    )
    created_first = client.post(
        "/v1/upgrades/requests",
        json={**signed_first, "contact_email": "unique-owner@example.com"},
    )
    assert created_first.status_code == 200
    verified_first = client.post("/v1/upgrades/l1/email/verify", json={"token": created_first.json()["token"]})
    assert verified_first.status_code == 200

    second_request_id = "upg-l1-owner-b"
    signed_second = sign_hosted_upgrade_request(
        client,
        agent_id=second_agent.agent_id,
        target_level="L1",
        request_id=second_request_id,
        hosted_management_token=second_agent.hosted_management_token or "",
    )
    created_second = client.post(
        "/v1/upgrades/requests",
        json={**signed_second, "contact_email": "unique-owner@example.com"},
    )
    assert created_second.status_code == 409
    assert "already linked to another agent" in created_second.json()["detail"]


def test_upgrade_l1_request_can_skip_auto_send_and_reports_delivery_failure() -> None:
    class FailingEmailProvider:
        def send_upgrade_link(
            self,
            *,
            recipient_hint: str,
            upgrade_request_id: str,
            verify_url: str,
            expires_at: int,
        ) -> dict:
            raise RuntimeError("email backend unavailable")

        def readiness(self) -> dict[str, str]:
            return {"status": "error", "backend": "failing-email"}

    service = RareService(allow_local_upgrade_shortcuts=True, email_provider=FailingEmailProvider())
    client = TestClient(create_app(service))
    agent = register_agent(client, "upgrade-l1-failing")

    failed_request = "upg-l1-failed-delivery"
    failed_signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=failed_request,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_failed = client.post(
        "/v1/upgrades/requests",
        json={**failed_signed, "contact_email": "owner-fail@example.com"},
    )
    assert created_failed.status_code == 200
    failed_body = created_failed.json()
    assert failed_body["email_delivery"]["state"] == "failed"
    assert failed_body["email_delivery"]["attempt_count"] == 1
    assert failed_body["email_delivery"]["last_error_code"] == "email_delivery_runtimeerror"

    status_failed = client.get(
        f"/v1/upgrades/requests/{failed_request}",
        headers=hosted_headers(agent),
    )
    assert status_failed.status_code == 200
    assert status_failed.json()["email_delivery"]["state"] == "failed"

    skipped_request = "upg-l1-manual-send"
    skipped_signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=skipped_request,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_skipped = client.post(
        "/v1/upgrades/requests",
        json={**skipped_signed, "contact_email": "owner-skip@example.com", "send_email": False},
    )
    assert created_skipped.status_code == 200
    skipped_body = created_skipped.json()
    assert skipped_body["email_delivery"]["state"] == "not_requested"
    assert skipped_body["email_delivery"]["attempt_count"] == 0


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


def test_hosted_management_token_can_be_recovered_via_email_factor(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "recover-email-agent")

    request_id = "recover-email-upgrade"
    signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    upgraded = client.post("/v1/upgrades/requests", json={**signed, "contact_email": "recover@example.com"})
    assert upgraded.status_code == 200
    verified = client.post("/v1/upgrades/l1/email/verify", json={"token": upgraded.json()["token"]})
    assert verified.status_code == 200

    factors = client.get(f"/v1/signer/recovery/factors/{agent.agent_id}")
    assert factors.status_code == 200
    factor_body = factors.json()
    assert factor_body["available_factors"][0]["type"] == "email"
    assert factor_body["available_factors"][0]["contact"] == "r*****r@example.com"

    expired = service.hosted_management_tokens[agent.agent_id]
    expired.expires_at = now_ts() - 1

    status_with_old_token = client.get(
        f"/v1/upgrades/requests/{request_id}",
        headers=hosted_headers(agent),
    )
    assert status_with_old_token.status_code == 403

    sent = client.post("/v1/signer/recovery/email/send-link", json={"agent_id": agent.agent_id})
    assert sent.status_code == 200
    recovered = client.post("/v1/signer/recovery/email/verify", json={"token": sent.json()["token"]})
    assert recovered.status_code == 200
    recovered_body = recovered.json()
    assert recovered_body["recovered"] is True
    assert recovered_body["recovery_factor"] == "email"

    recovered_status = client.get(
        f"/v1/upgrades/requests/{request_id}",
        headers={"Authorization": f"Bearer {recovered_body['hosted_management_token']}"},
    )
    assert recovered_status.status_code == 200

    sent_browser = client.post("/v1/signer/recovery/email/send-link", json={"agent_id": agent.agent_id})
    assert sent_browser.status_code == 200
    recovered_page = client.get("/v1/signer/recovery/email/verify", params={"token": sent_browser.json()["token"]})
    assert recovered_page.status_code == 200
    assert "text/html" in recovered_page.headers["content-type"]
    assert "Hosted access recovered" in recovered_page.text
    assert "Store it now before closing this page" in recovered_page.text


def test_hosted_management_token_social_recovery_requires_linked_account(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "recover-social-agent")

    l1_request_id = "recover-social-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post("/v1/upgrades/requests", json={**signed_l1, "contact_email": "recover-social@example.com"})
    assert created_l1.status_code == 200
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": created_l1.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "recover-social-l2"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200
    completed_l2 = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "42", "login": "rare-dev"},
        },
        headers=hosted_headers(agent),
    )
    assert completed_l2.status_code == 200

    factors = client.get(f"/v1/signer/recovery/factors/{agent.agent_id}")
    assert factors.status_code == 200
    factor_types = {(item["type"], item.get("provider")) for item in factors.json()["available_factors"]}
    assert ("email", None) in factor_types
    assert ("social", "github") in factor_types

    started = client.post(
        "/v1/signer/recovery/social/start",
        json={"agent_id": agent.agent_id, "provider": "github"},
    )
    assert started.status_code == 200

    wrong = client.post(
        "/v1/signer/recovery/social/complete",
        json={
            "agent_id": agent.agent_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "777", "login": "intruder"},
        },
    )
    assert wrong.status_code == 403

    recovered = client.post(
        "/v1/signer/recovery/social/complete",
        json={
            "agent_id": agent.agent_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "42", "login": "rare-dev"},
        },
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovery_factor"] == "social:github"


def test_hosted_management_token_social_recovery_supports_linkedin_without_handle(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "recover-linkedin-agent")

    l1_request_id = "recover-linkedin-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "recover-linkedin@example.com"},
    )
    assert created_l1.status_code == 200
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": created_l1.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "recover-linkedin-l2"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200
    completed_l2 = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "linkedin",
            "provider_user_snapshot": {"id": "linkedin-user-42", "display_name": "Rare LinkedIn"},
        },
        headers=hosted_headers(agent),
    )
    assert completed_l2.status_code == 200

    factors = client.get(f"/v1/signer/recovery/factors/{agent.agent_id}")
    assert factors.status_code == 200
    assert ("social", "linkedin") in {
        (item["type"], item.get("provider")) for item in factors.json()["available_factors"]
    }

    recovered = client.post(
        "/v1/signer/recovery/social/complete",
        json={
            "agent_id": agent.agent_id,
            "provider": "linkedin",
            "provider_user_snapshot": {"id": "linkedin-user-42"},
        },
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovery_factor"] == "social:linkedin"


def test_upgrade_l2_requires_l1_and_supports_x_github_and_linkedin(env: dict) -> None:
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
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": sent.json()["token"]})
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
    assert full_verified.payload["claims"]["twitter"]["handle"].startswith("x_")

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
    status_after_bad_complete = client.get(
        f"/v1/upgrades/requests/{github_request_id}",
        headers=hosted_headers(agent),
    )
    assert status_after_bad_complete.status_code == 200
    assert status_after_bad_complete.json()["status"] == "human_pending"
    assert status_after_bad_complete.json()["next_step"] == "connect_social"
    assert status_after_bad_complete.json()["social_provider"] is None
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

    linkedin_request_id = "upg-l2-linkedin-complete"
    signed_linkedin = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=linkedin_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_linkedin = client.post("/v1/upgrades/requests", json=signed_linkedin)
    assert created_linkedin.status_code == 200
    linkedin_complete = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": linkedin_request_id,
            "provider": "linkedin",
            "provider_user_snapshot": {"id": "linkedin-200", "display_name": "Rare LinkedIn"},
        },
        headers=hosted_headers(agent),
    )
    assert linkedin_complete.status_code == 200
    register_platform(client, service, aud="platform-linkedin-complete")
    full_linkedin = client.post(
        "/v1/attestations/full/issue",
        json=sign_hosted_full_issue(
            client,
            agent_id=agent.agent_id,
            platform_aud="platform-linkedin-complete",
            hosted_management_token=agent.hosted_management_token or "",
        ),
    )
    assert full_linkedin.status_code == 200
    linkedin_verified = verify_identity_attestation(
        full_linkedin.json()["full_identity_attestation"],
        key_resolver=service.get_identity_public_key,
        expected_aud="platform-linkedin-complete",
    )
    assert linkedin_verified.payload["claims"]["linkedin"]["id"] == "linkedin-200"


def test_upgrade_l2_rejects_social_account_already_linked_to_another_agent(env: dict) -> None:
    client = env["client"]
    first_agent = register_agent(client, "upgrade-l2-social-a")
    second_agent = register_agent(client, "upgrade-l2-social-b")

    def upgrade_l1(agent: RegisteredAgent, request_id: str, email: str) -> None:
        signed = sign_hosted_upgrade_request(
            client,
            agent_id=agent.agent_id,
            target_level="L1",
            request_id=request_id,
            hosted_management_token=agent.hosted_management_token or "",
        )
        created = client.post("/v1/upgrades/requests", json={**signed, "contact_email": email})
        assert created.status_code == 200
        verified = client.post("/v1/upgrades/l1/email/verify", json={"token": created.json()["token"]})
        assert verified.status_code == 200

    upgrade_l1(first_agent, "upg-l2-social-a-l1", "social-owner-a@example.com")
    upgrade_l1(second_agent, "upg-l2-social-b-l1", "social-owner-b@example.com")

    first_l2_request_id = "upg-l2-social-a"
    signed_first_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=first_agent.agent_id,
        target_level="L2",
        request_id=first_l2_request_id,
        hosted_management_token=first_agent.hosted_management_token or "",
    )
    created_first_l2 = client.post("/v1/upgrades/requests", json=signed_first_l2)
    assert created_first_l2.status_code == 200
    completed_first_l2 = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": first_l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "shared-github-1", "login": "shared-owner"},
        },
        headers=hosted_headers(first_agent),
    )
    assert completed_first_l2.status_code == 200

    second_l2_request_id = "upg-l2-social-b"
    signed_second_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=second_agent.agent_id,
        target_level="L2",
        request_id=second_l2_request_id,
        hosted_management_token=second_agent.hosted_management_token or "",
    )
    created_second_l2 = client.post("/v1/upgrades/requests", json=signed_second_l2)
    assert created_second_l2.status_code == 200
    completed_second_l2 = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": second_l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "shared-github-1", "login": "shared-owner"},
        },
        headers=hosted_headers(second_agent),
    )
    assert completed_second_l2.status_code == 409
    assert "already linked to another agent" in completed_second_l2.json()["detail"]


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
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": sent.json()["token"]})
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


def test_upgrade_l2_linkedin_callback_updates_attestation_claims(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "linkedin-agent")

    l1_request_id = "upg-linkedin-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "linkedin-owner@example.com"},
    )
    assert created_l1.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "upg-linkedin-l2"
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
        json={"upgrade_request_id": l2_request_id, "provider": "linkedin"},
        headers=hosted_headers(agent),
    )
    assert started.status_code == 200
    callback = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "linkedin", "code": "linkedin-code", "state": started.json()["state"]},
    )
    assert callback.status_code == 200
    assert callback.json()["level"] == "L2"

    register_platform(client, service, aud="platform-linkedin")
    full_issue = client.post(
        "/v1/attestations/full/issue",
        json=sign_hosted_full_issue(
            client,
            agent_id=agent.agent_id,
            platform_aud="platform-linkedin",
            hosted_management_token=agent.hosted_management_token or "",
        ),
    )
    assert full_issue.status_code == 200
    verified = verify_identity_attestation(
        full_issue.json()["full_identity_attestation"],
        key_resolver=service.get_identity_public_key,
        expected_aud="platform-linkedin",
    )
    assert verified.payload["claims"]["linkedin"]["vanity_name"].startswith("li_")


def test_upgrade_l2_social_callback_returns_html_for_browser_accept(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "browser-social-agent")

    l1_request_id = "browser-social-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "browser-social@example.com"},
    )
    assert created_l1.status_code == 200
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": created_l1.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "browser-social-l2"
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
        json={"upgrade_request_id": l2_request_id, "provider": "github"},
        headers=hosted_headers(agent),
    )
    assert started.status_code == 200

    callback = client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "github", "code": "browser-code", "state": started.json()["state"]},
        headers={"Accept": "text/html"},
    )
    assert callback.status_code == 200
    assert "text/html" in callback.headers["content-type"]
    assert "Social verification complete" in callback.text
    assert "github" in callback.text


def test_hosted_management_social_recovery_callback_returns_html_for_browser_accept(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "browser-recovery-agent")

    class FixedGitHubAdapter:
        def start_authorization(self, *, state: str) -> dict[str, str | dict[str, str]]:
            return {"authorize_url": f"https://oauth.github.local/authorize?state={state}", "provider_context": {}}

        def exchange_code(
            self,
            *,
            code: str,
            state: str,
            provider_context: dict[str, str] | None = None,
        ) -> dict[str, str | dict[str, str]]:
            return {
                "provider": "github",
                "provider_user_id": "42",
                "username_or_handle": "rare-dev",
                "display_name": "Rare Dev",
                "profile_url": "https://github.com/rare-dev",
                "raw_snapshot": {"id": "42", "login": "rare-dev"},
            }

        def readiness(self) -> dict[str, str]:
            return {"status": "ok", "backend": "stub", "provider": "github"}

    service.social_provider_adapters["github"] = FixedGitHubAdapter()

    l1_request_id = "browser-recovery-l1"
    signed_l1 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "browser-recovery@example.com"},
    )
    assert created_l1.status_code == 200
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": created_l1.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "browser-recovery-l2"
    signed_l2 = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200
    completed_l2 = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": l2_request_id,
            "provider": "github",
            "provider_user_snapshot": {"id": "42", "login": "rare-dev"},
        },
        headers=hosted_headers(agent),
    )
    assert completed_l2.status_code == 200

    started = client.post(
        "/v1/signer/recovery/social/start",
        json={"agent_id": agent.agent_id, "provider": "github"},
    )
    assert started.status_code == 200
    callback = client.get(
        "/v1/signer/recovery/social/callback",
        params={"provider": "github", "code": "browser-recovery-code", "state": started.json()["state"]},
        headers={"Accept": "text/html"},
    )
    assert callback.status_code == 200
    assert "text/html" in callback.headers["content-type"]
    assert "Social recovery complete" in callback.text
    assert "github" in callback.text


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


def test_full_issue_requires_registration_and_rejects_replay(env: dict) -> None:
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
    verified_l1 = client.post("/v1/upgrades/l1/email/verify", json={"token": send_ok.json()["token"]})
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


def test_create_app_disables_docs_and_openapi_by_default() -> None:
    client = TestClient(create_app(RareService()))
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_create_app_can_enable_docs_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RARE_ENABLE_OPENAPI_DOCS", "1")
    client = TestClient(create_app(RareService()))
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_file_key_provider_keeps_keys_stable_across_service_restarts(tmp_path: Path) -> None:
    keyring_file = tmp_path / "rare-keyring.json"
    provider = FileKeyProvider(path=keyring_file)
    first = RareService(key_provider=provider)
    second = RareService(key_provider=provider)

    assert first.active_identity_kid == second.active_identity_kid
    first_identity_pub = public_key_to_b64(first.identity_keys[first.active_identity_kid].private_key.public_key())
    second_identity_pub = public_key_to_b64(second.identity_keys[second.active_identity_kid].private_key.public_key())
    assert first_identity_pub == second_identity_pub
    assert public_key_to_b64(first.get_rare_signer_public_key()) == public_key_to_b64(second.get_rare_signer_public_key())

    identity_key = first.identity_keys[first.active_identity_kid]
    _, agent_public_b64 = generate_ed25519_keypair()
    token = sign_jws(
        payload={
            "typ": "rare.identity",
            "ver": 1,
            "iss": "rare",
            "sub": agent_public_b64,
            "lvl": "L1",
            "claims": {"profile": {"name": "stable"}},
            "iat": 0,
            "exp": 120,
            "jti": "stable-jti",
        },
        private_key=identity_key.private_key,
        kid=identity_key.kid,
        typ="rare.identity.public+jws",
    )
    verified = verify_identity_attestation(token, key_resolver=second.get_identity_public_key, current_ts=0)
    assert verified.payload["sub"] == agent_public_b64


def test_postgres_redis_store_shares_replay_state_between_instances() -> None:
    namespace = f"shared-{generate_nonce(6)}"
    PostgresRedisStateStore.clear_namespace(namespace)
    store = PostgresRedisStateStore(namespace=namespace)
    try:
        service_one = RareService(state_store=store, key_provider=EphemeralKeyProvider())
        service_two = RareService(state_store=store, key_provider=EphemeralKeyProvider())
        client_one = TestClient(create_app(service_one))
        client_two = TestClient(create_app(service_two))

        agent = register_self_hosted_agent(client_one, name="shared-replay")
        assert agent.private_key is not None
        issued_at = now_ts()
        expires_at = issued_at + 120
        nonce = "shared-nonce-1"
        payload = build_set_name_payload(
            agent_id=agent.agent_id,
            name="shared-replay-v2",
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        signature = sign_detached(payload, load_private_key(agent.private_key))
        request_payload = {
            "agent_id": agent.agent_id,
            "name": "shared-replay-v2",
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": signature,
        }

        first = client_one.post("/v1/agents/set_name", json=request_payload)
        assert first.status_code == 200
        replay = client_two.post("/v1/agents/set_name", json=request_payload)
        assert replay.status_code == 409
        assert "nonce already used" in replay.json()["detail"]
    finally:
        PostgresRedisStateStore.clear_namespace(namespace)


def test_create_app_forbids_memory_backend_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RARE_ENV", "prod")
    monkeypatch.setenv("RARE_PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("RARE_STORAGE_BACKEND", "memory")
    with pytest.raises(RuntimeError, match="forbidden"):
        create_app()


def test_create_app_allows_postgres_redis_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = f"app-ns-{generate_nonce(6)}"
    PostgresRedisStateStore.clear_namespace(namespace)
    monkeypatch.setenv("RARE_ENV", "staging")
    monkeypatch.setenv("RARE_PUBLIC_BASE_URL", "https://api.staging.example.com")
    monkeypatch.setenv("RARE_STORAGE_BACKEND", "postgres_redis")
    monkeypatch.setenv("RARE_STATE_NAMESPACE", namespace)
    monkeypatch.setenv("RARE_KEY_PROVIDER", "ephemeral")
    monkeypatch.setenv("RARE_SOCIAL_PROVIDER_ALLOWLIST", "github")
    monkeypatch.setenv("RARE_GITHUB_CLIENT_ID", "gh-client")
    monkeypatch.setenv("RARE_GITHUB_CLIENT_SECRET", "gh-secret")
    try:
        client = TestClient(create_app())
        response = client.post("/v1/agents/self_register", json={"name": "store-enabled"})
        assert response.status_code == 200
    finally:
        PostgresRedisStateStore.clear_namespace(namespace)


def test_create_app_supports_all_social_providers_in_prod(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RARE_ENV", "prod")
    monkeypatch.setenv("RARE_PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("RARE_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("RARE_SQLITE_STATE_FILE", str(tmp_path / "prod-state.sqlite3"))
    monkeypatch.setenv("RARE_KEY_PROVIDER", "ephemeral")
    monkeypatch.setenv("RARE_SOCIAL_PROVIDER_ALLOWLIST", "github,x,linkedin")
    monkeypatch.setenv("RARE_GITHUB_CLIENT_ID", "gh-client")
    monkeypatch.setenv("RARE_GITHUB_CLIENT_SECRET", "gh-secret")
    monkeypatch.setenv("RARE_LINKEDIN_CLIENT_ID", "li-client")
    monkeypatch.setenv("RARE_LINKEDIN_CLIENT_SECRET", "li-secret")
    monkeypatch.setenv("RARE_X_CLIENT_ID", "x-client")
    monkeypatch.setenv("RARE_X_CLIENT_SECRET", "x-secret")

    client = TestClient(create_app())
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["enabled_social_providers"] == ["github", "linkedin", "x"]


def test_create_app_rejects_missing_secret_for_enabled_social_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RARE_ENV", "prod")
    monkeypatch.setenv("RARE_PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("RARE_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("RARE_SQLITE_STATE_FILE", str(tmp_path / "missing-secret.sqlite3"))
    monkeypatch.setenv("RARE_KEY_PROVIDER", "ephemeral")
    monkeypatch.setenv("RARE_SOCIAL_PROVIDER_ALLOWLIST", "github,linkedin")
    monkeypatch.setenv("RARE_GITHUB_CLIENT_ID", "gh-client")
    monkeypatch.setenv("RARE_GITHUB_CLIENT_SECRET", "gh-secret")
    monkeypatch.delenv("RARE_LINKEDIN_CLIENT_ID", raising=False)
    monkeypatch.delenv("RARE_LINKEDIN_CLIENT_SECRET", raising=False)

    with pytest.raises(ValueError, match="LinkedIn OAuth requires"):
        create_app()


def test_healthz_and_readyz_report_runtime_status(env: dict) -> None:
    client = env["client"]
    health = client.get("/healthz")
    ready = client.get("/readyz")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["status"] == "ok"
    assert ready_body["checks"]["state_store"]["status"] == "ok"


def test_sqlite_state_store_persists_agents_and_audit(tmp_path: Path) -> None:
    keyring_file = tmp_path / "rare-keyring.json"
    sqlite_file = tmp_path / "rare-state.sqlite3"
    provider = FileKeyProvider(path=keyring_file)
    cipher_key = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
    cipher = LocalAesGcmHostedKeyCipher(key_b64=cipher_key)
    admin_token = "sqlite-admin"

    first = RareService(
        allow_local_upgrade_shortcuts=True,
        admin_token=admin_token,
        key_provider=provider,
        state_store=SqliteStateStore(path=sqlite_file),
        hosted_key_cipher=cipher,
    )
    first_client = TestClient(create_app(first))
    registered = first_client.post("/v1/agents/self_register", json={"name": "sqlite-agent"})
    assert registered.status_code == 200
    agent_id = registered.json()["agent_id"]
    private_key_b64 = first._private_key_to_b64(first.hosted_agent_private_keys[agent_id])

    second = RareService(
        allow_local_upgrade_shortcuts=True,
        admin_token=admin_token,
        key_provider=provider,
        state_store=SqliteStateStore(path=sqlite_file),
        hosted_key_cipher=cipher,
    )
    second_client = TestClient(create_app(second))
    details = second_client.get(
        f"/v1/admin/agents/{agent_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert details.status_code == 200
    assert details.json()["agent_id"] == agent_id
    audit = second_client.get(
        f"/v1/admin/agents/{agent_id}/audit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert audit.status_code == 200
    assert any(item["event_type"] == "self_register" for item in audit.json())

    raw_db = sqlite_file.read_bytes()
    assert private_key_b64.encode("utf-8") not in raw_db

    with sqlite3.connect(sqlite_file) as connection:
        agent_row = connection.execute(
            "SELECT agent_id, key_mode, name, status FROM rare_agents WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        assert agent_row == (agent_id, "hosted-signer", "sqlite-agent", "active")
        hosted_key_row = connection.execute(
            "SELECT agent_id, public_key_b64, private_key_ciphertext FROM rare_hosted_agent_keys WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        assert hosted_key_row is not None
        assert hosted_key_row[0] == agent_id
        assert hosted_key_row[1] == agent_id
        assert private_key_b64 not in hosted_key_row[2]
        audit_count = connection.execute("SELECT COUNT(*) FROM rare_audit_events").fetchone()
        assert audit_count == (1,)


def test_sqlite_state_store_syncs_between_instances(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "shared-state.sqlite3"
    keyring_file = tmp_path / "shared-keyring.json"
    provider = FileKeyProvider(path=keyring_file)

    first = RareService(
        key_provider=provider,
        state_store=SqliteStateStore(path=sqlite_file),
    )
    second = RareService(
        key_provider=provider,
        state_store=SqliteStateStore(path=sqlite_file),
    )
    first_client = TestClient(create_app(first))
    second_client = TestClient(create_app(second))

    registered = first_client.post("/v1/agents/self_register", json={"name": "shared-sqlite-agent"})
    assert registered.status_code == 200
    agent_id = registered.json()["agent_id"]

    refreshed = second_client.post("/v1/attestations/refresh", json={"agent_id": agent_id})
    assert refreshed.status_code == 200
    assert refreshed.json()["agent_id"] == agent_id


def test_sqlite_state_store_persists_x_oauth_provider_context_across_restart(tmp_path: Path) -> None:
    @dataclass
    class PersistedXAdapter:
        provider: str = "x"

        def start_authorization(self, *, state: str) -> dict[str, object]:
            return {
                "authorize_url": f"https://x.example/authorize?state={state}",
                "provider_context": {"code_verifier": "persisted-verifier"},
            }

        def exchange_code(
            self,
            *,
            code: str,
            state: str,
            provider_context: dict[str, object] | None = None,
        ) -> dict[str, object]:
            assert code == "oauth-code"
            assert state
            assert provider_context == {"code_verifier": "persisted-verifier"}
            return {
                "provider": "x",
                "provider_user_id": "x-user-1",
                "username_or_handle": "rarex",
                "display_name": "Rare X",
                "profile_url": "https://x.com/rarex",
                "raw_snapshot": {"id": "x-user-1", "username": "rarex"},
            }

        def readiness(self) -> dict[str, object]:
            return {"status": "ok", "backend": "test", "provider": "x"}

    sqlite_file = tmp_path / "oauth-state.sqlite3"
    keyring_file = tmp_path / "oauth-keyring.json"
    provider = FileKeyProvider(path=keyring_file)

    first = RareService(
        allow_local_upgrade_shortcuts=True,
        key_provider=provider,
        state_store=SqliteStateStore(path=sqlite_file),
        social_provider_adapters={"x": PersistedXAdapter()},
    )
    first_client = TestClient(create_app(first))
    agent = register_agent(first_client, "persisted-x-agent")

    l1_request_id = "persisted-x-l1"
    signed_l1 = sign_hosted_upgrade_request(
        first_client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id=l1_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l1 = first_client.post(
        "/v1/upgrades/requests",
        json={**signed_l1, "contact_email": "persisted-x@example.com"},
    )
    assert created_l1.status_code == 200
    sent = first_client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": l1_request_id},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified_l1 = first_client.post("/v1/upgrades/l1/email/verify", json={"token": sent.json()["token"]})
    assert verified_l1.status_code == 200

    l2_request_id = "persisted-x-l2"
    signed_l2 = sign_hosted_upgrade_request(
        first_client,
        agent_id=agent.agent_id,
        target_level="L2",
        request_id=l2_request_id,
        hosted_management_token=agent.hosted_management_token or "",
    )
    created_l2 = first_client.post("/v1/upgrades/requests", json=signed_l2)
    assert created_l2.status_code == 200
    started = first_client.post(
        "/v1/upgrades/l2/social/start",
        json={"upgrade_request_id": l2_request_id, "provider": "x"},
        headers=hosted_headers(agent),
    )
    assert started.status_code == 200

    second = RareService(
        allow_local_upgrade_shortcuts=True,
        key_provider=provider,
        state_store=SqliteStateStore(path=sqlite_file),
        social_provider_adapters={"x": PersistedXAdapter()},
    )
    second_client = TestClient(create_app(second))
    callback = second_client.get(
        "/v1/upgrades/l2/social/callback",
        params={"provider": "x", "code": "oauth-code", "state": started.json()["state"]},
    )
    assert callback.status_code == 200
    assert callback.json()["status"] == "upgraded"
    assert callback.json()["level"] == "L2"


def test_self_register_persists_snapshot_with_redis_backed_replay_handles(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "redis-backed-state.sqlite3"
    service = RareService(state_store=SqliteStateStore(path=sqlite_file))
    service.public_write_counters = _RedisBackedExpiringMap(  # type: ignore[assignment]
        redis_url=None,
        prefix="test:public-write",
        capacity=64,
    )
    service.used_name_nonces = _RedisBackedExpiringSet(  # type: ignore[assignment]
        redis_url=None,
        prefix="test:used-name",
        capacity=64,
    )
    client = TestClient(create_app(service))

    response = client.post("/v1/agents/self_register", json={"name": "redis-backed-register"})

    assert response.status_code == 200
    snapshot = service._serialize_snapshot()
    assert snapshot["public_write_counters"]


def test_redis_backed_expiring_map_snapshot_entries_decode_colon_prefix_keys() -> None:
    store = _RedisBackedExpiringMap(redis_url=None, prefix="rare:ratelimit:public_write:prod:default", capacity=8)
    fake_redis = FakeRedisClient()
    redis_key = b'rare:ratelimit:public_write:prod:default:["client",1]'
    fake_redis.values[redis_key] = store._encode_value({"count": 2})
    fake_redis.ttls[redis_key] = 30
    store._redis = fake_redis

    entries = store.snapshot_entries()

    assert len(entries) == 1
    assert entries[0][0] == ["client", 1]
    assert entries[0][1] == {"count": 2}


def test_admin_agent_endpoints_require_admin_token(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "admin-endpoint-check")

    missing = client.get(f"/v1/admin/agents/{agent.agent_id}")
    assert missing.status_code == 401

    forbidden = client.get(
        f"/v1/admin/agents/{agent.agent_id}",
        headers=hosted_headers(agent),
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        f"/v1/admin/agents/{agent.agent_id}",
        headers=admin_headers(env["admin_token"]),
    )
    assert allowed.status_code == 200
    assert allowed.json()["agent_id"] == agent.agent_id


def test_self_register_public_write_rate_limit_enforced() -> None:
    service = RareService(public_write_rate_limit_per_minute=2)
    client = TestClient(create_app(service))
    assert client.post("/v1/agents/self_register", json={"name": "ratelimit-1"}).status_code == 200
    assert client.post("/v1/agents/self_register", json={"name": "ratelimit-2"}).status_code == 200
    blocked = client.post("/v1/agents/self_register", json={"name": "ratelimit-3"})
    assert blocked.status_code == 429
    assert "rate limit exceeded" in blocked.json()["detail"]


def test_self_register_agent_capacity_enforced() -> None:
    service = RareService(max_agent_records=1, max_identity_profiles=1)
    client = TestClient(create_app(service))
    assert client.post("/v1/agents/self_register", json={"name": "cap-1"}).status_code == 200
    blocked = client.post("/v1/agents/self_register", json={"name": "cap-2"})
    assert blocked.status_code == 429
    assert "capacity exceeded" in blocked.json()["detail"]


def test_magic_link_verify_query_disabled_by_default(env: dict) -> None:
    client = env["client"]
    agent = register_agent(client, "legacy-query-off")
    signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id="legacy-query-off-req",
        hosted_management_token=agent.hosted_management_token or "",
    )
    created = client.post(
        "/v1/upgrades/requests",
        json={**signed, "contact_email": "legacy-off@example.com"},
    )
    assert created.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": "legacy-query-off-req"},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    legacy = client.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert legacy.status_code == 405


def test_magic_link_verify_query_can_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RARE_ENABLE_LEGACY_MAGIC_LINK_QUERY_VERIFY", "1")
    service = RareService(allow_local_upgrade_shortcuts=True)
    client = TestClient(create_app(service))
    agent = register_agent(client, "legacy-query-on")
    signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id="legacy-query-on-req",
        hosted_management_token=agent.hosted_management_token or "",
    )
    created = client.post(
        "/v1/upgrades/requests",
        json={**signed, "contact_email": "legacy-on@example.com"},
    )
    assert created.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": "legacy-query-on-req"},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    verified = client.get("/v1/upgrades/l1/email/verify", params={"token": sent.json()["token"]})
    assert verified.status_code == 200
    assert "text/html" in verified.headers["content-type"]
    assert "Email verified" in verified.text


def test_magic_link_verify_query_renders_html_error_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RARE_ENABLE_LEGACY_MAGIC_LINK_QUERY_VERIFY", "1")
    service = RareService(allow_local_upgrade_shortcuts=True)
    client = TestClient(create_app(service))

    failed = client.get("/v1/upgrades/l1/email/verify", params={"token": "missing-token"})

    assert failed.status_code == 404
    assert "text/html" in failed.headers["content-type"]
    assert "Verification link failed" in failed.text
    assert "/static/favicon.svg" in failed.text


def test_static_favicon_is_served(env: dict) -> None:
    response = env["client"].get("/static/favicon.svg")

    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]
    assert "<svg" in response.text


def test_public_base_url_emits_clickable_magic_link_and_enables_query_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RARE_ENABLE_LEGACY_MAGIC_LINK_QUERY_VERIFY", raising=False)
    service = RareService(allow_local_upgrade_shortcuts=True, public_base_url="https://api.example.com")
    client = TestClient(create_app(service))
    agent = register_agent(client, "public-base-url")
    signed = sign_hosted_upgrade_request(
        client,
        agent_id=agent.agent_id,
        target_level="L1",
        request_id="public-base-url-req",
        hosted_management_token=agent.hosted_management_token or "",
    )
    created = client.post(
        "/v1/upgrades/requests",
        json={**signed, "contact_email": "public-base@example.com"},
    )
    assert created.status_code == 200
    sent = client.post(
        "/v1/upgrades/l1/email/send-link",
        json={"upgrade_request_id": "public-base-url-req"},
        headers=hosted_headers(agent),
    )
    assert sent.status_code == 200
    magic_link = sent.json()["magic_link"]
    parsed = urlparse(magic_link)
    assert parsed.scheme == "https"
    assert parsed.netloc == "api.example.com"
    token = parse_qs(parsed.query)["token"][0]
    verified = client.get(parsed.path, params={"token": token})
    assert verified.status_code == 200
    assert "Email verified" in verified.text


def test_request_body_size_limit_enforced(env: dict) -> None:
    client = env["client"]
    huge_name = "x" * (300 * 1024)
    rejected = client.post("/v1/agents/self_register", json={"name": huge_name})
    assert rejected.status_code == 413


def test_dynamic_object_limits_enforced(env: dict) -> None:
    client = env["client"]
    admin_token = env["admin_token"]
    agent = register_agent(client, "dynamic-limit")

    oversize_patch = {
        "metadata": {f"k{i}": "v" for i in range(80)},
    }
    patch_rejected = client.patch(
        f"/v1/identity-library/profiles/{agent.agent_id}",
        json={"patch": oversize_patch},
        headers=admin_headers(admin_token),
    )
    assert patch_rejected.status_code == 422

    now = now_ts()
    prepared = client.post(
        "/v1/signer/prepare_auth",
        json={
            "agent_id": agent.agent_id,
            "aud": "platform",
            "nonce": generate_nonce(8),
            "issued_at": now,
            "expires_at": now + 120,
            "scope": ["login"],
        },
        headers=hosted_headers(agent),
    )
    assert prepared.status_code == 200
    prepared_body = prepared.json()
    action_rejected = client.post(
        "/v1/signer/sign_action",
        json={
            "agent_id": agent.agent_id,
            "session_pubkey": prepared_body["session_pubkey"],
            "session_token": "sess-token",
            "aud": "platform",
            "action": "post",
            "action_payload": {f"k{i}": "v" for i in range(80)},
            "nonce": generate_nonce(8),
            "issued_at": now,
            "expires_at": now + 120,
        },
        headers=hosted_headers(agent),
    )
    assert action_rejected.status_code == 422

    oversized_snapshot = client.post(
        "/v1/upgrades/l2/social/complete",
        json={
            "upgrade_request_id": "does-not-matter",
            "provider": "github",
            "provider_user_snapshot": {f"k{i}": "v" for i in range(80)},
        },
    )
    assert oversized_snapshot.status_code == 422


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
        ("/v1/signer/sign_platform_grant", {"agent_id": agent.agent_id, "platform_aud": "platform", "ttl_seconds": 120}),
        ("/v1/agents/platform-grants", {"agent_id": agent.agent_id, "platform_aud": "platform"}),
    ]
    for path, payload in removed_paths:
        response = client.post(path, json=payload)
        assert response.status_code == 404

    removed_get = client.get(f"/v1/agents/platform-grants/{agent.agent_id}")
    assert removed_get.status_code == 404

    removed_delete = client.request(
        "DELETE",
        "/v1/agents/platform-grants/platform",
        json={"agent_id": agent.agent_id},
    )
    assert removed_delete.status_code == 404


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
    _, agent_public_b64 = generate_ed25519_keypair()
    token = sign_jws(
        payload={
            "typ": "rare.identity",
            "ver": 1,
            "iss": "rare",
            "sub": agent_public_b64,
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


def test_sendgrid_provider_sends_real_http_request_shape() -> None:
    fake_http = FakeHttpClient()
    provider = SendGridEmailProvider(
        api_key="sg-key",
        from_email="noreply@example.com",
        http_client=fake_http,
    )

    result = provider.send_upgrade_link(
        recipient_hint="owner@example.com",
        upgrade_request_id="upg-1",
        verify_url="https://api.example.com/v1/upgrades/l1/email/verify?token=abc",
        expires_at=123456,
    )

    assert result["provider"] == "sendgrid"
    assert result["provider_request_id"] == "sg-message-1"
    method, url, kwargs = fake_http.calls[0]
    assert method == "POST"
    assert url == "https://api.sendgrid.com/v3/mail/send"
    assert kwargs["json"]["personalizations"][0]["to"][0]["email"] == "owner@example.com"
    assert kwargs["json"]["reply_to"]["email"] == "contact@example.com"
    content_types = [item["type"] for item in kwargs["json"]["content"]]
    assert content_types == ["text/plain", "text/html"]
    assert "Verify email" in kwargs["json"]["content"][1]["value"]
    assert 'content="light only"' in kwargs["json"]["content"][1]["value"]

    recovery = provider.send_management_recovery_link(
        recipient_hint="owner@example.com",
        agent_id="agent-1",
        verify_url="https://api.example.com/v1/signer/recovery/email/verify?token=abc",
        expires_at=123457,
    )
    assert recovery["provider"] == "sendgrid"
    assert recovery["agent_id"] == "agent-1"
    _, _, recovery_kwargs = fake_http.calls[1]
    assert "Recover token" in recovery_kwargs["json"]["content"][1]["value"]


def test_github_oauth_adapter_builds_and_exchanges_with_real_endpoints() -> None:
    fake_http = FakeHttpClient()
    adapter = GitHubOAuthAdapter(
        client_id="gh-client",
        client_secret="gh-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=github",
        http_client=fake_http,
    )

    auth_start = adapter.start_authorization(state="state-123")
    authorize_url = auth_start["authorize_url"]
    parsed = urlparse(authorize_url)
    assert parsed.netloc == "github.com"
    assert parse_qs(parsed.query)["state"] == ["state-123"]
    assert auth_start["provider_context"] == {}

    snapshot = adapter.exchange_code(code="oauth-code", state="state-123")
    assert snapshot["provider"] == "github"
    assert snapshot["provider_user_id"] == "123"
    assert snapshot["username_or_handle"] == "rare-agent"


def test_gcp_secret_manager_key_provider_persists_keyring_versions() -> None:
    fake_client = FakeSecretManagerClient()
    provider = GcpSecretManagerKeyProvider(
        secret_name="rare-keyring-test",
        project_id="rare-project",
        client=fake_client,
    )

    first = provider.load_or_create()
    second = provider.load_or_create()

    assert first.active_identity_kid == second.active_identity_kid
    assert len(fake_client.secrets["projects/rare-project/secrets/rare-keyring-test"]) == 1
    readiness = provider.readiness()
    assert readiness["status"] == "ok"


def test_plaintext_cipher_and_noop_email_provider_report_ready() -> None:
    cipher = PlaintextHostedKeyCipher()
    assert cipher.encrypt_text("rare") == "rare"
    assert cipher.decrypt_text("rare") == "rare"
    assert cipher.readiness() == {"status": "ok", "backend": "plaintext"}

    provider = NoopEmailProvider()
    upgrade = provider.send_upgrade_link(
        recipient_hint="owner@example.com",
        upgrade_request_id="upg-1",
        verify_url="https://example.com/upgrade",
        expires_at=123,
    )
    recovery = provider.send_management_recovery_link(
        recipient_hint="owner@example.com",
        agent_id="agent-1",
        verify_url="https://example.com/recovery",
        expires_at=456,
    )
    assert upgrade["provider"] == "noop"
    assert upgrade["upgrade_request_id"] == "upg-1"
    assert recovery["agent_id"] == "agent-1"
    assert provider.readiness() == {"status": "ok", "backend": "noop"}


def test_local_aes_cipher_readiness_and_invalid_key() -> None:
    with pytest.raises(ValueError, match="AES-GCM key must decode"):
        LocalAesGcmHostedKeyCipher(key_b64=base64.urlsafe_b64encode(b"short").decode("ascii"))

    cipher = LocalAesGcmHostedKeyCipher(key_b64=base64.urlsafe_b64encode(b"1" * 32).decode("ascii"))
    encrypted = cipher.encrypt_text("rare-secret")
    assert cipher.decrypt_text(encrypted) == "rare-secret"
    assert cipher.readiness() == {"status": "ok", "backend": "aesgcm"}


def test_sendgrid_provider_readiness_and_local_signer_roundtrip() -> None:
    provider = SendGridEmailProvider(api_key="sg-key", from_email="noreply@example.com")
    assert provider.readiness() == {
        "status": "ok",
        "backend": "sendgrid",
        "from_email": "noreply@example.com",
    }

    private_key_b64, public_key_b64 = generate_ed25519_keypair()
    signer = LocalEd25519JwsSigner(kid="kid-local", private_key=load_private_key(private_key_b64))
    signing_input = b"header.payload"
    signature = signer.sign_bytes(signing_input)
    signer.public_key().verify(signature, signing_input)
    assert public_key_to_b64(signer.public_key()) == public_key_b64
    assert signer.readiness() == {"status": "ok", "backend": "local", "kid": "kid-local"}


def test_stub_social_provider_variants_and_registry() -> None:
    registry = default_social_provider_adapters()
    assert set(registry) == {"github", "linkedin", "x"}
    assert registry["github"].readiness()["backend"] == "stub"

    stub_start = StubSocialProviderAdapter(provider="x").start_authorization(state="state")
    assert stub_start["provider_context"] == {}
    github_snapshot = StubSocialProviderAdapter(provider="github").exchange_code(code="code", state="state")
    x_snapshot = StubSocialProviderAdapter(provider="x").exchange_code(code="code", state="state")
    linkedin_snapshot = StubSocialProviderAdapter(provider="linkedin").exchange_code(code="code", state="state")
    assert github_snapshot["profile_url"].startswith("https://github.com/")
    assert x_snapshot["profile_url"].startswith("https://x.com/")
    assert linkedin_snapshot["profile_url"].startswith("https://www.linkedin.com/in/")

    with pytest.raises(TokenValidationError, match="unsupported social provider"):
        StubSocialProviderAdapter(provider="mastodon").exchange_code(code="code", state="state")


def test_github_oauth_adapter_readiness_and_error_paths() -> None:
    class MissingTokenHttpClient(FakeHttpClient):
        def post(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            self.calls.append(("POST", url, kwargs))
            return FakeHttpResponse(json_body={})

    class MissingProfileHttpClient(FakeHttpClient):
        def get(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            self.calls.append(("GET", url, kwargs))
            return FakeHttpResponse(json_body={"id": "", "login": ""})

    adapter = GitHubOAuthAdapter(
        client_id="gh-client",
        client_secret="gh-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=github",
        http_client=MissingTokenHttpClient(),
    )
    assert adapter.readiness()["provider"] == "github"
    with pytest.raises(TokenValidationError, match="github access token missing"):
        adapter.exchange_code(code="oauth-code", state="state-123")

    bad_profile_adapter = GitHubOAuthAdapter(
        client_id="gh-client",
        client_secret="gh-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=github",
        http_client=MissingProfileHttpClient(),
    )
    with pytest.raises(TokenValidationError, match="github user profile missing id/login"):
        bad_profile_adapter.exchange_code(code="oauth-code", state="state-123")


def test_linkedin_oauth_adapter_builds_and_exchanges_with_real_endpoints() -> None:
    class LinkedInHttpClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict]] = []

        def post(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            self.calls.append(("POST", url, kwargs))
            return FakeHttpResponse(json_body={"access_token": "li-token"})

        def get(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            self.calls.append(("GET", url, kwargs))
            return FakeHttpResponse(
                json_body={
                    "sub": "linkedin-user-1",
                    "name": "Rare LinkedIn",
                    "email": "owner@example.com",
                    "email_verified": True,
                }
            )

    fake_http = LinkedInHttpClient()
    adapter = LinkedInOAuthAdapter(
        client_id="li-client",
        client_secret="li-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=linkedin",
        api_version="202501",
        http_client=fake_http,
    )

    auth_start = adapter.start_authorization(state="state-456")
    parsed = urlparse(auth_start["authorize_url"])
    assert parsed.netloc == "www.linkedin.com"
    assert parse_qs(parsed.query)["scope"] == ["openid profile email"]
    assert auth_start["provider_context"] == {}

    snapshot = adapter.exchange_code(code="linkedin-code", state="state-456")
    assert snapshot["provider"] == "linkedin"
    assert snapshot["provider_user_id"] == "linkedin-user-1"
    assert "username_or_handle" not in snapshot
    assert snapshot["display_name"] == "Rare LinkedIn"
    assert snapshot["raw_snapshot"]["email_verified"] is True
    _, _, userinfo_kwargs = fake_http.calls[1]
    assert userinfo_kwargs["headers"]["LinkedIn-Version"] == "202501"


def test_linkedin_oauth_adapter_rejects_missing_subject() -> None:
    class MissingSubjectLinkedInHttpClient:
        def post(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            return FakeHttpResponse(json_body={"access_token": "li-token"})

        def get(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            return FakeHttpResponse(json_body={"name": "Rare LinkedIn"})

    adapter = LinkedInOAuthAdapter(
        client_id="li-client",
        client_secret="li-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=linkedin",
        http_client=MissingSubjectLinkedInHttpClient(),
    )
    with pytest.raises(TokenValidationError, match="linkedin user profile missing sub"):
        adapter.exchange_code(code="linkedin-code", state="state-456")


def test_x_oauth_adapter_uses_pkce_and_exchanges_profile() -> None:
    class XHttpClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict]] = []

        def post(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            self.calls.append(("POST", url, kwargs))
            return FakeHttpResponse(json_body={"access_token": "x-token"})

        def get(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            self.calls.append(("GET", url, kwargs))
            return FakeHttpResponse(json_body={"data": {"id": "x-user-1", "username": "rarex", "name": "Rare X"}})

    fake_http = XHttpClient()
    adapter = XOAuthAdapter(
        client_id="x-client",
        client_secret="x-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=x",
        http_client=fake_http,
    )

    auth_start = adapter.start_authorization(state="state-x")
    parsed = urlparse(auth_start["authorize_url"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "twitter.com"
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["users.read"]
    provider_context = auth_start["provider_context"]
    assert provider_context["code_verifier"]

    snapshot = adapter.exchange_code(code="x-code", state="state-x", provider_context=provider_context)
    assert snapshot["provider"] == "x"
    assert snapshot["provider_user_id"] == "x-user-1"
    assert snapshot["username_or_handle"] == "rarex"
    _, _, token_kwargs = fake_http.calls[0]
    assert token_kwargs["data"]["code_verifier"] == provider_context["code_verifier"]
    assert token_kwargs["auth"] == ("x-client", "x-secret")


def test_x_oauth_adapter_requires_pkce_context_and_profile_fields() -> None:
    class MissingFieldsXHttpClient:
        def post(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            return FakeHttpResponse(json_body={"access_token": "x-token"})

        def get(self, url: str, **kwargs: dict) -> FakeHttpResponse:
            return FakeHttpResponse(json_body={"data": {"id": "", "username": ""}})

    adapter = XOAuthAdapter(
        client_id="x-client",
        client_secret="x-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=x",
        http_client=MissingFieldsXHttpClient(),
    )
    with pytest.raises(TokenValidationError, match="x oauth state missing code_verifier"):
        adapter.exchange_code(code="x-code", state="state-x")
    with pytest.raises(TokenValidationError, match="x user profile missing id/username"):
        adapter.exchange_code(
            code="x-code",
            state="state-x",
            provider_context={"code_verifier": "verifier"},
        )


def test_kms_backends_raise_clear_error_without_google_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "google.cloud":
            raise ImportError("blocked for test")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="google-cloud-kms is required for GcpKmsHostedKeyCipher"):
        GcpKmsHostedKeyCipher(key_name="projects/x/locations/y/keyRings/z/cryptoKeys/a")

    with pytest.raises(RuntimeError, match="google-cloud-kms is required for GcpKmsEd25519JwsSigner"):
        GcpKmsEd25519JwsSigner(kid="kid-1", key_version_name="projects/x/locations/y/keyRings/z/cryptoKeys/a/cryptoKeyVersions/1")

    with pytest.raises(RuntimeError, match="google-cloud-secret-manager is required for GcpSecretManagerKeyProvider"):
        GcpSecretManagerKeyProvider(secret_name="rare-keyring", project_id="rare-project").load_or_create()


def test_gcp_secret_manager_key_provider_resolves_full_name_env_and_blank_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="secret_name is required"):
        GcpSecretManagerKeyProvider(secret_name="   ")

    full_name_client = FakeSecretManagerClient()
    full_name_provider = GcpSecretManagerKeyProvider(
        secret_name="projects/full-project/secrets/rare-keyring",
        client=full_name_client,
    )
    full_name_provider.load_or_create()
    assert "projects/full-project/secrets/rare-keyring" in full_name_client.secrets

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    env_client = FakeSecretManagerClient()
    env_provider = GcpSecretManagerKeyProvider(secret_name="rare-keyring-env", client=env_client)
    env_provider.load_or_create()
    assert "projects/env-project/secrets/rare-keyring-env" in env_client.secrets


def test_file_key_provider_ignores_chmod_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "rare-keyring.json"
    provider = FileKeyProvider(path=path)

    def raise_os_error(self, mode: int) -> None:
        raise OSError("chmod blocked")

    monkeypatch.setattr(Path, "chmod", raise_os_error)
    keyring = provider.load_or_create()

    assert keyring.active_identity_kid
    assert path.exists()


def test_ephemeral_key_provider_reports_ready() -> None:
    provider = EphemeralKeyProvider()
    assert provider.load_or_create().active_identity_kid
    assert provider.readiness() == {"status": "ok", "backend": "ephemeral"}


def test_httpx_context_manager_branches_for_sendgrid_and_github(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeContextHttpClient(FakeHttpClient):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    context_client = FakeContextHttpClient()
    monkeypatch.setattr("rare_api.integrations.httpx.Client", lambda timeout=10.0: context_client)

    sendgrid_provider = SendGridEmailProvider(api_key="sg-key", from_email="noreply@example.com")
    queued = sendgrid_provider.send_upgrade_link(
        recipient_hint="owner@example.com",
        upgrade_request_id="upg-ctx",
        verify_url="https://example.com/upgrade",
        expires_at=123,
    )
    assert queued["provider"] == "sendgrid"

    github_adapter = GitHubOAuthAdapter(
        client_id="gh-client",
        client_secret="gh-secret",
        redirect_uri="https://api.example.com/v1/upgrades/l2/social/callback?provider=github",
    )
    snapshot = github_adapter.exchange_code(code="oauth-code", state="state-123")
    assert snapshot["provider_user_id"] == "123"


def test_kms_integrations_support_success_paths_with_fake_google_client(monkeypatch: pytest.MonkeyPatch) -> None:
    signing_private_key_b64, signing_public_key_b64 = generate_ed25519_keypair()
    signing_private_key = load_private_key(signing_private_key_b64)
    public_key_pem = (
        load_public_key(signing_public_key_b64)
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    class FakeKmsClient:
        def encrypt(self, request: dict):
            return type("Resp", (), {"ciphertext": bytes(request["plaintext"])[::-1]})()

        def decrypt(self, request: dict):
            return type("Resp", (), {"plaintext": bytes(request["ciphertext"])[::-1]})()

        def asymmetric_sign(self, request: dict):
            return type("Resp", (), {"signature": signing_private_key.sign(bytes(request["data"]))})()

        def get_public_key(self, request: dict):
            return type("Resp", (), {"pem": public_key_pem})()

    fake_kms_client = FakeKmsClient()
    fake_kms_module = type(
        "FakeKmsModule",
        (),
        {"KeyManagementServiceClient": staticmethod(lambda: fake_kms_client)},
    )()
    fake_cloud_module = type("FakeCloudModule", (), {"kms": fake_kms_module})()
    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "google.cloud":
            return fake_cloud_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    cipher = GcpKmsHostedKeyCipher(key_name="projects/p/locations/l/keyRings/r/cryptoKeys/k")
    encrypted = cipher.encrypt_text("rare-secret")
    assert cipher.decrypt_text(encrypted) == "rare-secret"
    assert cipher.readiness() == {
        "status": "ok",
        "backend": "gcp_kms",
        "key_name": "projects/p/locations/l/keyRings/r/cryptoKeys/k",
    }

    signer = GcpKmsEd25519JwsSigner(
        kid="kms-kid",
        key_version_name="projects/p/locations/l/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    )
    signature = signer.sign_bytes(b"header.payload")
    signer.public_key().verify(signature, b"header.payload")
    assert public_key_to_b64(signer.public_key()) == signing_public_key_b64
    assert signer.readiness() == {
        "status": "ok",
        "backend": "gcp_kms",
        "kid": "kms-kid",
        "key_version_name": "projects/p/locations/l/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    }


def test_resolve_public_dns_txt_handles_success_empty_and_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTxtAnswer:
        def __init__(self, strings=None, rendered: str | None = None) -> None:
            self.strings = strings
            self._rendered = rendered

        def __str__(self) -> str:
            return self._rendered or ""

    class FakeResolverModule:
        @staticmethod
        def resolve(name: str, record_type: str):
            assert record_type == "TXT"
            if name == "missing.example.com":
                raise type("NXDOMAIN", (Exception,), {})()
            return [
                FakeTxtAnswer(strings=[b"rare=", b"ok"]),
                FakeTxtAnswer(strings=None, rendered='"fallback-value"'),
            ]

    fake_dns_module = type("FakeDnsModule", (), {"resolver": FakeResolverModule})()
    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name in {"dns", "dns.resolver"}:
            return fake_dns_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert resolve_public_dns_txt("rare.example.com") == ["rare=ok", "fallback-value"]
    assert resolve_public_dns_txt("missing.example.com") == []

    def failing_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "dns.resolver":
            raise ImportError("blocked for test")
        if name == "dns":
            raise ImportError("blocked for test")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    with pytest.raises(RuntimeError, match="dnspython is required"):
        resolve_public_dns_txt("rare.example.com")


def test_sign_delegation_endpoint_rejects_invalid_session_key_and_accepts_valid_one(env: dict) -> None:
    client = env["client"]
    service = env["service"]
    agent = register_agent(client, "deleg-sign-valid")
    _, session_pubkey = generate_ed25519_keypair()

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
