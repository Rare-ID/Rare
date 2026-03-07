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
    load_private_key,
    load_public_key,
    sign_detached,
    sign_jws,
    validate_name,
    verify_detached,
    verify_jws,
)


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
