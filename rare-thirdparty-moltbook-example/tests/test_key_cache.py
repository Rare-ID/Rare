from __future__ import annotations

from rare_identity_protocol import generate_ed25519_keypair
from rare_identity_verifier import parse_rare_jwks

from moltbook_api.key_cache import RareKeyCache


def _make_jwks(kid: str, public_key_b64: str) -> dict:
    return {
        "issuer": "rare",
        "keys": [
            {
                "kid": kid,
                "kty": "OKP",
                "crv": "Ed25519",
                "x": public_key_b64,
                "retire_at": 1800000000,
            }
        ],
    }


def test_key_cache_resolves_initial_key() -> None:
    _, pub = generate_ed25519_keypair()
    cache = RareKeyCache(initial_jwks=_make_jwks("kid-1", pub))

    assert cache.resolve("kid-1") is not None


def test_key_cache_refreshes_on_unknown_kid() -> None:
    _, pub1 = generate_ed25519_keypair()
    _, pub2 = generate_ed25519_keypair()

    states = [_make_jwks("kid-2", pub2)]

    def refresh() -> dict:
        return states.pop(0) if states else _make_jwks("kid-2", pub2)

    cache = RareKeyCache(initial_jwks=_make_jwks("kid-1", pub1), refresh_fn=refresh)

    assert cache.resolve("kid-2") is not None


def test_key_cache_without_refresh_returns_none() -> None:
    _, pub = generate_ed25519_keypair()
    cache = RareKeyCache(initial_jwks=_make_jwks("kid-1", pub), refresh_fn=None)

    assert cache.resolve("kid-404") is None


def test_parse_rare_jwks_accepts_cache_payload() -> None:
    _, pub = generate_ed25519_keypair()
    parsed = parse_rare_jwks(_make_jwks("kid-1", pub))
    assert "kid-1" in parsed
