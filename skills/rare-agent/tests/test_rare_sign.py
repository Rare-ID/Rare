from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "python" / "rare-identity-protocol-python" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "python" / "rare-identity-verifier-python" / "src"))

from rare_identity_protocol import (  # noqa: E402
    build_action_payload,
    build_auth_challenge_payload,
    build_full_attestation_issue_payload,
    build_register_payload,
    build_set_name_payload,
    build_upgrade_request_payload,
    load_public_key,
    verify_detached,
)
from rare_identity_verifier import verify_delegation_token  # noqa: E402


SCRIPT = ROOT / "skills" / "rare-agent" / "scripts" / "rare_sign.py"


def run_helper(*args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_gen_keypair_and_register_and_set_name(tmp_path: Path) -> None:
    private_key_file = tmp_path / "agent.key"
    generated = run_helper("gen-keypair", "--private-key-file", str(private_key_file))
    assert generated["private_key_file"] == str(private_key_file)
    assert "private_key" not in generated

    register = run_helper(
        "register",
        "--private-key-file",
        str(private_key_file),
        "--name",
        "alice",
        "--nonce",
        "r1",
        "--issued-at",
        "1700000000",
        "--expires-at",
        "1700000120",
    )
    register_payload = build_register_payload(
        agent_id=register["agent_id"],
        name=register["name"],
        nonce=register["nonce"],
        issued_at=register["issued_at"],
        expires_at=register["expires_at"],
    )
    verify_detached(
        register_payload,
        register["signature_by_agent"],
        load_public_key(register["agent_id"]),
    )

    set_name = run_helper(
        "set-name",
        "--private-key-file",
        str(private_key_file),
        "--agent-id",
        register["agent_id"],
        "--name",
        "alice-v2",
        "--nonce",
        "n1",
        "--issued-at",
        "1700001000",
        "--expires-at",
        "1700001120",
    )
    set_name_payload = build_set_name_payload(
        agent_id=set_name["agent_id"],
        name=set_name["name"],
        nonce=set_name["nonce"],
        issued_at=set_name["issued_at"],
        expires_at=set_name["expires_at"],
    )
    verify_detached(
        set_name_payload,
        set_name["signature_by_agent"],
        load_public_key(set_name["agent_id"]),
    )


def test_full_attestation_and_upgrade_signatures(tmp_path: Path) -> None:
    private_key_file = tmp_path / "agent.key"
    register = run_helper("gen-keypair", "--private-key-file", str(private_key_file), "--show-private-key")
    agent_private_key = register["private_key"]
    register_payload = run_helper(
        "register",
        "--private-key",
        agent_private_key,
        "--name",
        "builder",
    )
    agent_id = register_payload["agent_id"]

    full_issue = run_helper(
        "issue-full-attestation",
        "--private-key-file",
        str(private_key_file),
        "--agent-id",
        agent_id,
        "--platform-aud",
        "platform",
        "--nonce",
        "f1",
        "--issued-at",
        "1700002000",
        "--expires-at",
        "1700002120",
    )
    full_issue_payload = build_full_attestation_issue_payload(
        agent_id=agent_id,
        platform_aud="platform",
        nonce=full_issue["nonce"],
        issued_at=full_issue["issued_at"],
        expires_at=full_issue["expires_at"],
    )
    verify_detached(
        full_issue_payload,
        full_issue["signature_by_agent"],
        load_public_key(agent_id),
    )

    upgrade = run_helper(
        "upgrade-request",
        "--private-key-file",
        str(private_key_file),
        "--agent-id",
        agent_id,
        "--target-level",
        "L1",
        "--request-id",
        "req-1",
        "--contact-email",
        "owner@example.com",
        "--nonce",
        "u1",
        "--issued-at",
        "1700003000",
        "--expires-at",
        "1700003120",
    )
    upgrade_payload = build_upgrade_request_payload(
        agent_id=agent_id,
        target_level="L1",
        request_id="req-1",
        nonce=upgrade["nonce"],
        issued_at=upgrade["issued_at"],
        expires_at=upgrade["expires_at"],
    )
    verify_detached(
        upgrade_payload,
        upgrade["signature_by_agent"],
        load_public_key(agent_id),
    )
    assert upgrade["contact_email"] == "owner@example.com"
    assert upgrade["send_email"] is True


def test_prepare_auth_and_sign_action(tmp_path: Path) -> None:
    private_key_file = tmp_path / "agent.key"
    run_helper("gen-keypair", "--private-key-file", str(private_key_file))
    register = run_helper(
        "register",
        "--private-key-file",
        str(private_key_file),
        "--name",
        "actor",
    )
    agent_id = register["agent_id"]
    session_key_file = tmp_path / "session.key"

    prepared = run_helper(
        "prepare-auth",
        "--private-key-file",
        str(private_key_file),
        "--agent-id",
        agent_id,
        "--aud",
        "platform",
        "--nonce",
        "auth-1",
        "--issued-at",
        "1700004000",
        "--expires-at",
        "1700004060",
        "--session-private-key-file",
        str(session_key_file),
    )
    verified = verify_delegation_token(
        prepared["delegation_token"],
        expected_aud="platform",
        required_scope="login",
        rare_signer_public_key=None,
    )
    assert verified.payload["agent_id"] == agent_id
    assert verified.payload["session_pubkey"] == prepared["session_pubkey"]

    challenge_payload = build_auth_challenge_payload(
        aud="platform",
        nonce="auth-1",
        issued_at=1700004000,
        expires_at=1700004060,
    )
    verify_detached(
        challenge_payload,
        prepared["signature_by_session"],
        load_public_key(prepared["session_pubkey"]),
    )

    signed_action = run_helper(
        "sign-action",
        "--session-private-key-file",
        str(session_key_file),
        "--aud",
        "platform",
        "--session-token",
        "sess-1",
        "--action",
        "post",
        "--action-payload",
        '{"content":"hello"}',
        "--nonce",
        "a1",
        "--issued-at",
        "1700005000",
        "--expires-at",
        "1700005060",
    )
    action_payload = build_action_payload(
        aud="platform",
        session_token="sess-1",
        action="post",
        action_payload={"content": "hello"},
        nonce=signed_action["nonce"],
        issued_at=signed_action["issued_at"],
        expires_at=signed_action["expires_at"],
    )
    verify_detached(
        action_payload,
        signed_action["signature_by_session"],
        load_public_key(prepared["session_pubkey"]),
    )
