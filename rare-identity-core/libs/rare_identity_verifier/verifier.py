from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from rare_identity_protocol import (
    TokenValidationError,
    decode_jws,
    load_public_key,
    now_ts,
    verify_jws,
)


KeyResolver = Callable[[str], Ed25519PublicKey | None]


@dataclass(frozen=True)
class IdentityVerificationResult:
    header: dict
    payload: dict


@dataclass(frozen=True)
class DelegationVerificationResult:
    header: dict
    payload: dict


def parse_rare_jwks(jwks: dict) -> dict[str, Ed25519PublicKey]:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise TokenValidationError("invalid JWKS payload")

    resolved: dict[str, Ed25519PublicKey] = {}
    for item in keys:
        if not isinstance(item, dict):
            continue
        kid = item.get("kid")
        crv = item.get("crv")
        kty = item.get("kty")
        x = item.get("x")
        if not kid or not x:
            continue
        if kty != "OKP" or crv != "Ed25519":
            continue
        resolved[kid] = load_public_key(x)
    return resolved


def verify_identity_attestation(
    token: str,
    *,
    key_resolver: KeyResolver,
    expected_aud: str | None = None,
    current_ts: int | None = None,
    clock_skew_seconds: int = 30,
) -> IdentityVerificationResult:
    decoded = decode_jws(token)
    typ = decoded.header.get("typ")
    if typ not in {"rare.identity.public+jws", "rare.identity.full+jws"}:
        raise TokenValidationError("invalid identity token typ")

    kid = decoded.header.get("kid")
    if not isinstance(kid, str):
        raise TokenValidationError("missing key id")

    public_key = key_resolver(kid)
    if public_key is None:
        raise TokenValidationError("unknown identity key id")

    verified = verify_jws(token, public_key)
    payload = verified.payload

    if payload.get("typ") != "rare.identity":
        raise TokenValidationError("invalid identity payload typ")
    if payload.get("ver") != 1:
        raise TokenValidationError("unsupported identity payload version")
    if payload.get("iss") != "rare":
        raise TokenValidationError("invalid identity issuer")
    if typ == "rare.identity.full+jws":
        if not expected_aud:
            raise TokenValidationError("expected_aud required for full identity token")
        if payload.get("aud") != expected_aud:
            raise TokenValidationError("identity full token aud mismatch")
    elif "aud" in payload:
        raise TokenValidationError("public identity token must not contain aud")

    level = payload.get("lvl")
    if level not in {"L0", "L1", "L2"}:
        raise TokenValidationError("invalid identity level")

    now = current_ts or now_ts()
    iat = payload.get("iat")
    exp = payload.get("exp")

    if not isinstance(iat, int) or not isinstance(exp, int):
        raise TokenValidationError("identity timestamps must be integers")
    if iat - clock_skew_seconds > now:
        raise TokenValidationError("identity token not yet valid")
    if exp + clock_skew_seconds < now:
        raise TokenValidationError("identity token expired")

    return IdentityVerificationResult(header=verified.header, payload=payload)


def verify_delegation_token(
    token: str,
    *,
    expected_aud: str,
    required_scope: str,
    rare_signer_public_key: Ed25519PublicKey | None,
    current_ts: int | None = None,
    clock_skew_seconds: int = 30,
) -> DelegationVerificationResult:
    decoded = decode_jws(token)

    if decoded.header.get("typ") != "rare.delegation+jws":
        raise TokenValidationError("invalid delegation token typ")

    payload = decoded.payload
    if payload.get("typ") != "rare.delegation":
        raise TokenValidationError("invalid delegation payload typ")
    if payload.get("ver") != 1:
        raise TokenValidationError("unsupported delegation payload version")

    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str):
        raise TokenValidationError("delegation agent_id missing")

    issuer = payload.get("iss")
    if issuer == "rare-signer":
        if payload.get("act") != "delegated_by_rare":
            raise TokenValidationError("rare signer delegation missing act")
        if rare_signer_public_key is None:
            raise TokenValidationError("rare signer key unavailable")
        verified = verify_jws(token, rare_signer_public_key)
    elif issuer == "agent":
        if payload.get("act") != "delegated_by_agent":
            raise TokenValidationError("agent delegation missing act")
        agent_public_key = load_public_key(agent_id)
        verified = verify_jws(token, agent_public_key)
    else:
        raise TokenValidationError("unsupported delegation issuer")

    payload = verified.payload
    if payload.get("aud") != expected_aud:
        raise TokenValidationError("delegation aud mismatch")

    scope = payload.get("scope")
    if not isinstance(scope, list) or required_scope not in scope:
        raise TokenValidationError("delegation scope missing required action")

    session_pubkey = payload.get("session_pubkey")
    if not isinstance(session_pubkey, str):
        raise TokenValidationError("delegation missing session_pubkey")

    now = current_ts or now_ts()
    iat = payload.get("iat")
    exp = payload.get("exp")
    if not isinstance(iat, int) or not isinstance(exp, int):
        raise TokenValidationError("delegation timestamps must be integers")
    if iat - clock_skew_seconds > now:
        raise TokenValidationError("delegation token not yet valid")
    if exp + clock_skew_seconds < now:
        raise TokenValidationError("delegation token expired")

    return DelegationVerificationResult(header=verified.header, payload=payload)
