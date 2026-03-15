from __future__ import annotations

import pytest

from rare_identity_protocol import (
    ExpiringMap,
    ExpiringSet,
    ResourceLimitError,
    SignatureError,
    TokenValidationError,
    b64url_decode,
    b64url_encode,
    decode_jws,
    generate_ed25519_keypair,
    generate_nonce,
    load_private_key,
    load_public_key,
    now_ts,
    public_key_to_b64,
    build_agent_auth_payload,
    issue_agent_delegation,
    issue_full_identity_attestation,
    issue_public_identity_attestation,
    issue_rare_delegation,
    sign_detached,
    sign_jws,
    validate_name,
    verify_detached,
    verify_jws,
)
from rare_identity_protocol.tokens import build_identity_payload


def test_load_key_rejects_invalid_length() -> None:
    invalid_b64 = b64url_encode(b"short")
    with pytest.raises(TokenValidationError, match="private key length"):
        load_private_key(invalid_b64)
    with pytest.raises(TokenValidationError, match="public key length"):
        load_public_key(invalid_b64)


def test_decode_jws_rejects_invalid_compact_format() -> None:
    with pytest.raises(TokenValidationError, match="invalid compact JWS format"):
        decode_jws("only-two.parts")


def test_decode_jws_rejects_invalid_encoding_and_non_object_json() -> None:
    with pytest.raises(TokenValidationError, match="invalid JWS encoding"):
        decode_jws("a.b.c")

    header = b64url_encode(b'["not-object"]')
    payload = b64url_encode(b'{"ok":1}')
    signature = b64url_encode(b"x" * 64)
    token = f"{header}.{payload}.{signature}"
    with pytest.raises(TokenValidationError, match="must be JSON objects"):
        decode_jws(token)


def test_verify_jws_rejects_unsupported_alg() -> None:
    private_b64, public_b64 = generate_ed25519_keypair()
    private_key = load_private_key(private_b64)
    public_key = load_public_key(public_b64)

    header = b64url_encode(b'{"alg":"HS256","kid":"k1","typ":"rare.identity.public+jws"}')
    payload = b64url_encode(b'{"typ":"rare.identity","ver":1}')
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = b64url_encode(private_key.sign(signing_input))
    token = f"{header}.{payload}.{signature}"
    with pytest.raises(TokenValidationError, match="unsupported JWS alg"):
        verify_jws(token, public_key)


def test_verify_jws_rejects_invalid_signature() -> None:
    private_b64, public_b64 = generate_ed25519_keypair()
    token = sign_jws(
        payload={"typ": "rare.identity", "ver": 1, "iss": "rare"},
        private_key=load_private_key(private_b64),
        kid="k1",
        typ="rare.identity.public+jws",
    )
    encoded_header, encoded_payload, encoded_signature = token.split(".")
    signature_bytes = bytearray(b64url_decode(encoded_signature))
    signature_bytes[0] ^= 0x01
    tampered = f"{encoded_header}.{encoded_payload}.{b64url_encode(bytes(signature_bytes))}"
    with pytest.raises(SignatureError, match="invalid JWS signature"):
        verify_jws(tampered, load_public_key(public_b64))


def test_verify_jws_returns_decoded_payload() -> None:
    private_b64, public_b64 = generate_ed25519_keypair()
    payload = {"typ": "rare.identity", "ver": 1, "iss": "rare", "sub": "agent-1"}
    token = sign_jws(
        payload=payload,
        private_key=load_private_key(private_b64),
        kid="k1",
        typ="rare.identity.public+jws",
    )
    decoded = verify_jws(token, load_public_key(public_b64))
    assert decoded.payload == payload
    assert decoded.header["kid"] == "k1"


def test_verify_detached_rejects_invalid_signature() -> None:
    private_a_b64, public_a_b64 = generate_ed25519_keypair()
    private_b_b64, _ = generate_ed25519_keypair()
    message = "rare-auth-v1:platform:nonce:1:2"
    wrong_sig = sign_detached(message, load_private_key(private_b_b64))
    with pytest.raises(SignatureError, match="invalid detached signature"):
        verify_detached(message, wrong_sig, load_public_key(public_a_b64))


def test_validate_name_normalizes_and_checks_boundaries() -> None:
    assert validate_name("  Ａｌｉｃｅ　") == "Alice"
    assert validate_name("a") == "a"
    assert validate_name("x" * 48) == "x" * 48

    with pytest.raises(TokenValidationError, match="between 1 and 48"):
        validate_name("")
    with pytest.raises(TokenValidationError, match="between 1 and 48"):
        validate_name("x" * 49)


def test_validate_name_rejects_control_and_reserved_words() -> None:
    with pytest.raises(TokenValidationError, match="control characters"):
        validate_name("hello\nworld")
    with pytest.raises(TokenValidationError, match="control characters"):
        validate_name("hello\u200Eworld")
    with pytest.raises(TokenValidationError, match="reserved"):
        validate_name("AdMiN")


def test_expiring_map_rejects_invalid_capacity_and_overflow() -> None:
    with pytest.raises(ValueError, match="capacity must be greater than 0"):
        ExpiringMap[int, int](capacity=0)

    store = ExpiringMap[str, int](capacity=1)
    store.set(key="k1", value=1, expires_at=100, now=0)
    with pytest.raises(ResourceLimitError, match="capacity exceeded"):
        store.set(key="k2", value=2, expires_at=100, now=0)


def test_expiring_map_cleanup_handles_stale_revisions() -> None:
    store = ExpiringMap[str, str](capacity=4)
    store.set(key="k", value="old", expires_at=10, now=0)
    store.set(key="k", value="new", expires_at=200, now=0)
    store.cleanup(now=50)
    assert store.get("k") == "new"
    store.cleanup(now=300)
    assert store.get("k") is None


def test_expiring_map_helpers_pop_discard_keys_values_items() -> None:
    store = ExpiringMap[str, int](capacity=4)
    store.set(key="a", value=1, expires_at=100, now=0)
    store.set(key="b", value=2, expires_at=100, now=0)

    assert "a" in store
    assert len(store) == 2
    assert set(store.keys()) == {"a", "b"}
    assert set(store.values()) == {1, 2}
    assert set(store.items()) == {("a", 1), ("b", 2)}
    assert store.pop("a") == 1
    assert store.pop("missing") is None
    store.discard("b")
    store.discard("missing")
    assert len(store) == 0


def test_expiring_set_helpers_cover_add_contains_discard_and_len() -> None:
    seen = ExpiringSet[str](capacity=4)
    seen.add(key="nonce-1", expires_at=100, now=0)
    assert seen.contains("nonce-1")
    assert len(seen) == 1
    seen.discard("nonce-1")
    seen.discard("nonce-404")
    assert not seen.contains("nonce-1")
    assert len(seen) == 0


def test_expiring_store_cleanup_handles_missing_and_expiry_mismatch() -> None:
    store = ExpiringMap[str, int](capacity=4)
    store.set(key="gone", value=1, expires_at=10, now=0)
    store.discard("gone")
    store.cleanup(now=50)

    store.set(key="mismatch", value=2, expires_at=10, now=0)
    store._entries["mismatch"].expires_at = 999
    store.cleanup(now=50)
    assert store.get("mismatch") == 2

    seen = ExpiringSet[str](capacity=2)
    seen.add(key="nonce-1", expires_at=10, now=0)
    seen.cleanup(now=100)
    assert not seen.contains("nonce-1")


def test_crypto_helpers_cover_nonce_timestamp_and_public_key_roundtrip() -> None:
    private_b64, public_b64 = generate_ed25519_keypair()
    assert public_key_to_b64(load_public_key(public_b64)) == public_b64
    assert isinstance(now_ts(), int)
    assert generate_nonce(8) != generate_nonce(8)
    signature = sign_detached("msg", load_private_key(private_b64))
    verify_detached("msg", signature, load_public_key(public_b64))


def test_build_agent_auth_payload_uses_fixed_format() -> None:
    assert (
        build_agent_auth_payload(
            agent_id="agent-1",
            operation="login",
            resource_id="platform",
            nonce="nonce-1",
            issued_at=100,
            expires_at=160,
        )
        == "rare-agent-auth-v1:agent-1:login:platform:nonce-1:100:160"
    )


def test_build_identity_payload_can_include_or_omit_extended_claims() -> None:
    public_payload = build_identity_payload(
        agent_id="agent-1",
        level="L1",
        name="Alice",
        iat=100,
        exp=160,
        jti="jti-public",
        include_extended_claims=False,
    )
    assert public_payload["claims"] == {"profile": {"name": "Alice", "name_updated_at": 100}}
    assert "aud" not in public_payload

    full_payload = build_identity_payload(
        agent_id="agent-1",
        level="L2",
        name="Alice",
        aud="platform",
        iat=100,
        exp=160,
        jti="jti-full",
        include_extended_claims=True,
        name_updated_at=120,
        owner_id="owner-1",
        org_id="org-1",
        twitter={"handle": "rare"},
        github={"login": "rare"},
        linkedin={"handle": "rare-li"},
    )
    assert full_payload["aud"] == "platform"
    assert full_payload["claims"]["owner_id"] == "owner-1"
    assert full_payload["claims"]["org_id"] == "org-1"
    assert full_payload["claims"]["twitter"] == {"handle": "rare"}
    assert full_payload["claims"]["github"] == {"login": "rare"}
    assert full_payload["claims"]["linkedin"] == {"handle": "rare-li"}
    assert full_payload["claims"]["profile"]["name_updated_at"] == 120


def test_issue_identity_attestations_and_delegations(monkeypatch: pytest.MonkeyPatch) -> None:
    private_b64, public_b64 = generate_ed25519_keypair()
    signer_private_key = load_private_key(private_b64)
    monkeypatch.setattr("rare_identity_protocol.tokens.now_ts", lambda: 100)

    public_token = issue_public_identity_attestation(
        agent_id=public_b64,
        level="L2",
        name="Alice",
        kid="kid-public",
        signer_private_key=signer_private_key,
        ttl_seconds=60,
        jti="public-jti",
        name_updated_at=90,
    )
    decoded_public = verify_jws(public_token, load_public_key(public_b64))
    assert decoded_public.header["typ"] == "rare.identity.public+jws"
    assert decoded_public.payload["lvl"] == "L1"
    assert decoded_public.payload["claims"] == {"profile": {"name": "Alice", "name_updated_at": 90}}

    full_token = issue_full_identity_attestation(
        agent_id=public_b64,
        level="L2",
        name="Alice",
        aud="platform",
        kid="kid-full",
        signer_private_key=signer_private_key,
        ttl_seconds=60,
        jti="full-jti",
        owner_id="owner-1",
        org_id="org-1",
        github={"login": "rare"},
    )
    decoded_full = verify_jws(full_token, load_public_key(public_b64))
    assert decoded_full.header["typ"] == "rare.identity.full+jws"
    assert decoded_full.payload["aud"] == "platform"
    assert decoded_full.payload["claims"]["github"] == {"login": "rare"}

    agent_delegation = issue_agent_delegation(
        agent_id=public_b64,
        session_pubkey="session-key",
        aud="platform",
        scope=("login", "post"),
        signer_private_key=signer_private_key,
        kid="kid-delegation",
        ttl_seconds=60,
        jti="agent-jti",
    )
    decoded_agent_delegation = verify_jws(agent_delegation, load_public_key(public_b64))
    assert decoded_agent_delegation.payload["iss"] == "agent"
    assert decoded_agent_delegation.payload["act"] == "delegated_by_agent"

    rare_delegation = issue_rare_delegation(
        agent_id=public_b64,
        session_pubkey="session-key",
        aud="platform",
        scope=("login",),
        signer_private_key=signer_private_key,
        kid="kid-rare",
        ttl_seconds=60,
        jti="rare-jti",
    )
    decoded_rare_delegation = verify_jws(rare_delegation, load_public_key(public_b64))
    assert decoded_rare_delegation.payload["iss"] == "rare-signer"
    assert decoded_rare_delegation.payload["act"] == "delegated_by_rare"


@pytest.mark.parametrize(
    "issuer",
    [
        issue_agent_delegation,
        issue_rare_delegation,
    ],
)
def test_delegation_issue_requires_non_empty_jti(issuer) -> None:
    private_b64, public_b64 = generate_ed25519_keypair()
    with pytest.raises(TokenValidationError, match="delegation jti is required"):
        issuer(
            agent_id=public_b64,
            session_pubkey="session-key",
            aud="platform",
            scope=("login",),
            signer_private_key=load_private_key(private_b64),
            kid="kid-1",
            jti="  ",
        )
