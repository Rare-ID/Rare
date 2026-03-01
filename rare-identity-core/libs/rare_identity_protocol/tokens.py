from __future__ import annotations

from typing import Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rare_identity_protocol.crypto import now_ts, sign_jws


def _build_identity_claims(
    *,
    name: str,
    iat: int,
    name_updated_at: int | None,
    owner_id: str | None,
    org_id: str | None,
    twitter: dict[str, str] | None,
    github: dict[str, str] | None,
    include_extended_claims: bool,
) -> dict:
    claims: dict[str, object] = {
        "profile": {
            "name": name,
            "name_updated_at": name_updated_at if name_updated_at is not None else iat,
        }
    }
    if not include_extended_claims:
        return claims

    if org_id:
        claims["org_id"] = org_id
    if owner_id:
        claims["owner_id"] = owner_id
    if twitter:
        claims["twitter"] = twitter
    if github:
        claims["github"] = github
    return claims


def build_identity_payload(
    *,
    agent_id: str,
    level: str,
    name: str,
    iat: int,
    exp: int,
    jti: str,
    aud: str | None = None,
    include_extended_claims: bool = True,
    name_updated_at: int | None = None,
    owner_id: str | None = None,
    org_id: str | None = None,
    twitter: dict[str, str] | None = None,
    github: dict[str, str] | None = None,
) -> dict:
    claims = _build_identity_claims(
        name=name,
        iat=iat,
        name_updated_at=name_updated_at,
        owner_id=owner_id,
        org_id=org_id,
        twitter=twitter,
        github=github,
        include_extended_claims=include_extended_claims,
    )

    payload = {
        "typ": "rare.identity",
        "ver": 1,
        "iss": "rare",
        "sub": agent_id,
        "lvl": level,
        "claims": claims,
        "iat": iat,
        "exp": exp,
        "jti": jti,
    }
    if aud:
        payload["aud"] = aud
    return payload


def issue_public_identity_attestation(
    *,
    agent_id: str,
    level: str,
    name: str,
    kid: str,
    signer_private_key: Ed25519PrivateKey,
    ttl_seconds: int,
    jti: str,
    name_updated_at: int | None = None,
    owner_id: str | None = None,
    org_id: str | None = None,
    twitter: dict[str, str] | None = None,
    github: dict[str, str] | None = None,
) -> str:
    iat = now_ts()
    exp = iat + ttl_seconds
    public_level = level if level in {"L0", "L1"} else "L1"
    payload = build_identity_payload(
        agent_id=agent_id,
        level=public_level,
        name=name,
        iat=iat,
        exp=exp,
        jti=jti,
        include_extended_claims=False,
        name_updated_at=name_updated_at,
    )
    return sign_jws(
        payload=payload,
        private_key=signer_private_key,
        kid=kid,
        typ="rare.identity.public+jws",
    )


def issue_full_identity_attestation(
    *,
    agent_id: str,
    level: str,
    name: str,
    aud: str,
    kid: str,
    signer_private_key: Ed25519PrivateKey,
    ttl_seconds: int,
    jti: str,
    name_updated_at: int | None = None,
    owner_id: str | None = None,
    org_id: str | None = None,
    twitter: dict[str, str] | None = None,
    github: dict[str, str] | None = None,
) -> str:
    iat = now_ts()
    exp = iat + ttl_seconds
    payload = build_identity_payload(
        agent_id=agent_id,
        level=level,
        name=name,
        aud=aud,
        iat=iat,
        exp=exp,
        jti=jti,
        include_extended_claims=True,
        name_updated_at=name_updated_at,
        owner_id=owner_id,
        org_id=org_id,
        twitter=twitter,
        github=github,
    )
    return sign_jws(
        payload=payload,
        private_key=signer_private_key,
        kid=kid,
        typ="rare.identity.full+jws",
    )


def issue_agent_delegation(
    *,
    agent_id: str,
    session_pubkey: str,
    aud: str,
    scope: Iterable[str],
    signer_private_key: Ed25519PrivateKey,
    kid: str,
    ttl_seconds: int = 3600,
    jti: str | None = None,
) -> str:
    iat = now_ts()
    payload = {
        "typ": "rare.delegation",
        "ver": 1,
        "iss": "agent",
        "agent_id": agent_id,
        "session_pubkey": session_pubkey,
        "aud": aud,
        "scope": list(scope),
        "iat": iat,
        "exp": iat + ttl_seconds,
        "act": "delegated_by_agent",
    }
    if jti:
        payload["jti"] = jti

    return sign_jws(
        payload=payload,
        private_key=signer_private_key,
        kid=kid,
        typ="rare.delegation+jws",
    )


def issue_rare_delegation(
    *,
    agent_id: str,
    session_pubkey: str,
    aud: str,
    scope: Iterable[str],
    signer_private_key: Ed25519PrivateKey,
    kid: str,
    ttl_seconds: int = 3600,
    jti: str | None = None,
) -> str:
    iat = now_ts()
    payload = {
        "typ": "rare.delegation",
        "ver": 1,
        "iss": "rare-signer",
        "agent_id": agent_id,
        "session_pubkey": session_pubkey,
        "aud": aud,
        "scope": list(scope),
        "iat": iat,
        "exp": iat + ttl_seconds,
        "act": "delegated_by_rare",
    }
    if jti:
        payload["jti"] = jti

    return sign_jws(
        payload=payload,
        private_key=signer_private_key,
        kid=kid,
        typ="rare.delegation+jws",
    )
