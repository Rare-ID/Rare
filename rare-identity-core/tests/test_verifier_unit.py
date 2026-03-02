from __future__ import annotations

import pytest

from rare_identity_protocol import (
    TokenValidationError,
    generate_ed25519_keypair,
    issue_agent_delegation,
    issue_rare_delegation,
    load_private_key,
    load_public_key,
    sign_jws,
)
from rare_identity_verifier import parse_rare_jwks, verify_delegation_token, verify_identity_attestation


def _identity_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "typ": "rare.identity",
        "ver": 1,
        "iss": "rare",
        "sub": "agent-1",
        "lvl": "L1",
        "claims": {"profile": {"name": "alice"}},
        "iat": 100,
        "exp": 200,
        "jti": "id-jti-1",
    }
    payload.update(overrides)
    return payload


def _sign_identity_token(
    *,
    header_typ: str = "rare.identity.public+jws",
    kid: str = "kid-1",
    payload_overrides: dict[str, object] | None = None,
) -> tuple[str, dict[str, object]]:
    private_key_b64, public_key_b64 = generate_ed25519_keypair()
    payload = _identity_payload(**(payload_overrides or {}))
    token = sign_jws(
        payload=payload,
        private_key=load_private_key(private_key_b64),
        kid=kid,
        typ=header_typ,
    )
    return token, {kid: load_public_key(public_key_b64)}


def _delegation_payload(
    *,
    issuer: str,
    agent_id: str,
    session_pubkey: str,
    aud: str = "platform",
    scope: list[str] | None = None,
    iat: int = 100,
    exp: int = 200,
    jti: str = "deleg-jti-1",
    act: str | None = None,
    ver: int = 1,
) -> dict[str, object]:
    if act is None:
        act = "delegated_by_agent" if issuer == "agent" else "delegated_by_rare"
    return {
        "typ": "rare.delegation",
        "ver": ver,
        "iss": issuer,
        "agent_id": agent_id,
        "session_pubkey": session_pubkey,
        "aud": aud,
        "scope": scope or ["login"],
        "iat": iat,
        "exp": exp,
        "act": act,
        "jti": jti,
    }


def test_parse_rare_jwks_validates_shape_and_skips_invalid_items() -> None:
    with pytest.raises(TokenValidationError, match="invalid JWKS payload"):
        parse_rare_jwks({"keys": "bad"})

    _, public_key_b64 = generate_ed25519_keypair()
    parsed = parse_rare_jwks(
        {
            "keys": [
                {"kid": "k1", "kty": "OKP", "crv": "Ed25519", "x": public_key_b64},
                {"kid": "k2", "kty": "RSA", "crv": "Ed25519", "x": public_key_b64},
                {"kid": "k3", "kty": "OKP", "crv": "P-256", "x": public_key_b64},
                {"kid": "k4", "kty": "OKP", "crv": "Ed25519"},
                "invalid",
            ]
        }
    )
    assert list(parsed.keys()) == ["k1"]


def test_verify_identity_attestation_accepts_unknown_claims_for_forward_compat() -> None:
    token, key_map = _sign_identity_token(
        payload_overrides={"claims": {"profile": {"name": "alice"}, "future_claim": {"v": 1}}}
    )

    verified = verify_identity_attestation(token, key_resolver=lambda kid: key_map.get(kid), current_ts=150)
    assert verified.payload["sub"] == "agent-1"
    assert "future_claim" in verified.payload["claims"]


def test_verify_identity_attestation_rejects_invalid_header_typ() -> None:
    token, key_map = _sign_identity_token(header_typ="rare.identity+jws")
    with pytest.raises(TokenValidationError, match="invalid identity token typ"):
        verify_identity_attestation(token, key_resolver=lambda kid: key_map.get(kid))


def test_verify_identity_attestation_rejects_missing_or_unknown_kid() -> None:
    private_key_b64, _ = generate_ed25519_keypair()
    token_missing_kid = sign_jws(
        payload=_identity_payload(),
        private_key=load_private_key(private_key_b64),
        kid=None,  # type: ignore[arg-type]
        typ="rare.identity.public+jws",
    )
    with pytest.raises(TokenValidationError, match="missing key id"):
        verify_identity_attestation(token_missing_kid, key_resolver=lambda _kid: None)

    token, _ = _sign_identity_token(kid="unknown-kid")
    with pytest.raises(TokenValidationError, match="unknown identity key id"):
        verify_identity_attestation(token, key_resolver=lambda _kid: None)


def test_verify_identity_attestation_rejects_public_token_with_aud() -> None:
    token, key_map = _sign_identity_token(payload_overrides={"aud": "platform"})
    with pytest.raises(TokenValidationError, match="must not contain aud"):
        verify_identity_attestation(token, key_resolver=lambda kid: key_map.get(kid))


def test_verify_identity_attestation_rejects_full_token_without_expected_aud() -> None:
    token, key_map = _sign_identity_token(
        header_typ="rare.identity.full+jws",
        payload_overrides={"aud": "platform"},
    )
    with pytest.raises(TokenValidationError, match="expected_aud required"):
        verify_identity_attestation(token, key_resolver=lambda kid: key_map.get(kid))


def test_verify_identity_attestation_rejects_full_token_aud_mismatch() -> None:
    token, key_map = _sign_identity_token(
        header_typ="rare.identity.full+jws",
        payload_overrides={"aud": "platform-a"},
    )
    with pytest.raises(TokenValidationError, match="aud mismatch"):
        verify_identity_attestation(
            token,
            key_resolver=lambda kid: key_map.get(kid),
            expected_aud="platform-b",
        )


@pytest.mark.parametrize(
    ("payload_overrides", "error_match"),
    [
        ({"typ": "wrong"}, "invalid identity payload typ"),
        ({"ver": 2}, "unsupported identity payload version"),
        ({"iss": "other"}, "invalid identity issuer"),
        ({"lvl": "L9"}, "invalid identity level"),
        ({"iat": "100"}, "timestamps must be integers"),
        ({"exp": "200"}, "timestamps must be integers"),
    ],
)
def test_verify_identity_attestation_rejects_invalid_payload_fields(
    payload_overrides: dict[str, object],
    error_match: str,
) -> None:
    token, key_map = _sign_identity_token(payload_overrides=payload_overrides)
    with pytest.raises(TokenValidationError, match=error_match):
        verify_identity_attestation(token, key_resolver=lambda kid: key_map.get(kid), current_ts=150)


def test_verify_identity_attestation_rejects_not_yet_valid_and_expired() -> None:
    future_token, future_key_map = _sign_identity_token(payload_overrides={"iat": 500, "exp": 560})
    with pytest.raises(TokenValidationError, match="not yet valid"):
        verify_identity_attestation(
            future_token,
            key_resolver=lambda kid: future_key_map.get(kid),
            current_ts=100,
            clock_skew_seconds=30,
        )

    expired_token, expired_key_map = _sign_identity_token(payload_overrides={"iat": 10, "exp": 50})
    with pytest.raises(TokenValidationError, match="expired"):
        verify_identity_attestation(
            expired_token,
            key_resolver=lambda kid: expired_key_map.get(kid),
            current_ts=100,
            clock_skew_seconds=30,
        )


def test_verify_delegation_token_accepts_agent_and_rare_signer_issuers() -> None:
    agent_private_b64, agent_public_b64 = generate_ed25519_keypair()
    _, session_public_b64 = generate_ed25519_keypair()
    rare_private_b64, rare_public_b64 = generate_ed25519_keypair()

    agent_token = issue_agent_delegation(
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
        aud="platform",
        scope=["login", "post"],
        signer_private_key=load_private_key(agent_private_b64),
        kid=f"agent-{agent_public_b64[:8]}",
        ttl_seconds=120,
        jti="agent-jti-1",
    )
    agent_verified = verify_delegation_token(
        agent_token,
        expected_aud="platform",
        required_scope="login",
        rare_signer_public_key=load_public_key(rare_public_b64),
    )
    assert agent_verified.payload["iss"] == "agent"

    rare_token = issue_rare_delegation(
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
        aud="platform",
        scope=["login", "post"],
        signer_private_key=load_private_key(rare_private_b64),
        kid="rare-signer-k1",
        ttl_seconds=120,
        jti="rare-jti-1",
    )
    rare_verified = verify_delegation_token(
        rare_token,
        expected_aud="platform",
        required_scope="post",
        rare_signer_public_key=load_public_key(rare_public_b64),
    )
    assert rare_verified.payload["iss"] == "rare-signer"


def test_verify_delegation_token_rejects_invalid_header_typ() -> None:
    agent_private_b64, agent_public_b64 = generate_ed25519_keypair()
    payload = _delegation_payload(issuer="agent", agent_id=agent_public_b64, session_pubkey=agent_public_b64)
    token = sign_jws(
        payload=payload,
        private_key=load_private_key(agent_private_b64),
        kid="agent-k1",
        typ="rare.delegation",
    )
    with pytest.raises(TokenValidationError, match="invalid delegation token typ"):
        verify_delegation_token(
            token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=None,
            current_ts=120,
        )


@pytest.mark.parametrize(
    ("payload_overrides", "error_match"),
    [
        ({"typ": "bad"}, "invalid delegation payload typ"),
        ({"ver": 2}, "unsupported delegation payload version"),
        ({"agent_id": 1}, "delegation agent_id missing"),
        ({"iss": "service"}, "unsupported delegation issuer"),
        ({"aud": "other"}, "delegation aud mismatch"),
        ({"scope": ["post"]}, "scope missing required action"),
        ({"session_pubkey": 1}, "missing session_pubkey"),
        ({"iat": "100"}, "timestamps must be integers"),
        ({"exp": "200"}, "timestamps must be integers"),
        ({"jti": ""}, "delegation jti missing"),
    ],
)
def test_verify_delegation_token_rejects_invalid_payload_fields(
    payload_overrides: dict[str, object],
    error_match: str,
) -> None:
    agent_private_b64, agent_public_b64 = generate_ed25519_keypair()
    session_private_b64, session_public_b64 = generate_ed25519_keypair()
    del session_private_b64
    payload = _delegation_payload(
        issuer="agent",
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
    )
    payload.update(payload_overrides)
    token = sign_jws(
        payload=payload,
        private_key=load_private_key(agent_private_b64),
        kid="agent-k1",
        typ="rare.delegation+jws",
    )
    with pytest.raises(TokenValidationError, match=error_match):
        verify_delegation_token(
            token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=None,
            current_ts=120,
        )


def test_verify_delegation_token_rejects_act_mismatch_and_missing_rare_key() -> None:
    agent_private_b64, agent_public_b64 = generate_ed25519_keypair()
    _, session_public_b64 = generate_ed25519_keypair()
    rare_private_b64, rare_public_b64 = generate_ed25519_keypair()

    bad_agent_act_payload = _delegation_payload(
        issuer="agent",
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
        act="delegated_by_rare",
    )
    bad_agent_act_token = sign_jws(
        payload=bad_agent_act_payload,
        private_key=load_private_key(agent_private_b64),
        kid="agent-k1",
        typ="rare.delegation+jws",
    )
    with pytest.raises(TokenValidationError, match="agent delegation missing act"):
        verify_delegation_token(
            bad_agent_act_token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=None,
            current_ts=120,
        )

    rare_token = issue_rare_delegation(
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
        aud="platform",
        scope=["login"],
        signer_private_key=load_private_key(rare_private_b64),
        kid="rare-k1",
        ttl_seconds=120,
        jti="rare-jti-2",
    )
    with pytest.raises(TokenValidationError, match="rare signer key unavailable"):
        verify_delegation_token(
            rare_token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=None,
            current_ts=120,
        )

    bad_rare_act_payload = _delegation_payload(
        issuer="rare-signer",
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
        act="delegated_by_agent",
    )
    bad_rare_act_token = sign_jws(
        payload=bad_rare_act_payload,
        private_key=load_private_key(rare_private_b64),
        kid="rare-k2",
        typ="rare.delegation+jws",
    )
    with pytest.raises(TokenValidationError, match="rare signer delegation missing act"):
        verify_delegation_token(
            bad_rare_act_token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=load_public_key(rare_public_b64),
            current_ts=120,
        )


def test_verify_delegation_token_rejects_not_yet_valid_and_expired() -> None:
    agent_private_b64, agent_public_b64 = generate_ed25519_keypair()
    _, session_public_b64 = generate_ed25519_keypair()

    future_payload = _delegation_payload(
        issuer="agent",
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
        iat=500,
        exp=560,
    )
    future_token = sign_jws(
        payload=future_payload,
        private_key=load_private_key(agent_private_b64),
        kid="agent-k1",
        typ="rare.delegation+jws",
    )
    with pytest.raises(TokenValidationError, match="not yet valid"):
        verify_delegation_token(
            future_token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=None,
            current_ts=100,
            clock_skew_seconds=30,
        )

    expired_payload = _delegation_payload(
        issuer="agent",
        agent_id=agent_public_b64,
        session_pubkey=session_public_b64,
        iat=10,
        exp=50,
    )
    expired_token = sign_jws(
        payload=expired_payload,
        private_key=load_private_key(agent_private_b64),
        kid="agent-k2",
        typ="rare.delegation+jws",
    )
    with pytest.raises(TokenValidationError, match="expired"):
        verify_delegation_token(
            expired_token,
            expected_aud="platform",
            required_scope="login",
            rare_signer_public_key=None,
            current_ts=100,
            clock_skew_seconds=30,
        )
