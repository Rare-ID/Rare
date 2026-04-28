#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


RAW_KEY_SIZE = 32
RESERVED_NAMES = {"admin", "root", "support", "official", "rare"}


def now_ts() -> int:
    return int(time.time())


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def json_dumps_compact(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def generate_nonce(length: int = 12) -> str:
    return secrets.token_urlsafe(length)


def public_key_to_b64(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64url_encode(raw)


def generate_keypair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return b64url_encode(private_raw), public_key_to_b64(private_key.public_key())


def load_private_key(raw_b64url: str) -> Ed25519PrivateKey:
    key_bytes = b64url_decode(raw_b64url)
    if len(key_bytes) != RAW_KEY_SIZE:
        raise ValueError("invalid Ed25519 private key length")
    return Ed25519PrivateKey.from_private_bytes(key_bytes)


def require_agent_match(private_key: Ed25519PrivateKey, agent_id: str) -> None:
    derived = public_key_to_b64(private_key.public_key())
    if derived != agent_id:
        raise ValueError("agent_id does not match the provided private key")


def sign_detached(message: str, private_key: Ed25519PrivateKey) -> str:
    return b64url_encode(private_key.sign(message.encode("utf-8")))


def sign_jws(*, payload: dict[str, Any], private_key: Ed25519PrivateKey, kid: str, typ: str) -> str:
    header = {"alg": "EdDSA", "kid": kid, "typ": typ}
    encoded_header = b64url_encode(json_dumps_compact(header))
    encoded_payload = b64url_encode(json_dumps_compact(payload))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = b64url_encode(private_key.sign(signing_input))
    return f"{encoded_header}.{encoded_payload}.{signature}"


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name.strip())
    if len(normalized) < 1 or len(normalized) > 48:
        raise ValueError("name length must be between 1 and 48")
    if normalized.casefold() in {item.casefold() for item in RESERVED_NAMES}:
        raise ValueError("name is reserved")
    for char in normalized:
        if unicodedata.category(char).startswith("C"):
            raise ValueError("name must not include control characters")
    return normalized


def build_register_payload(*, agent_id: str, name: str, nonce: str, issued_at: int, expires_at: int) -> str:
    return f"rare-register-v1:{agent_id}:{normalize_name(name)}:{nonce}:{issued_at}:{expires_at}"


def build_set_name_payload(*, agent_id: str, name: str, nonce: str, issued_at: int, expires_at: int) -> str:
    return f"rare-name-v1:{agent_id}:{normalize_name(name)}:{nonce}:{issued_at}:{expires_at}"


def build_full_attestation_issue_payload(
    *,
    agent_id: str,
    platform_aud: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    return f"rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}"


def build_upgrade_request_payload(
    *,
    agent_id: str,
    target_level: str,
    request_id: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    return f"rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}"


def build_auth_challenge_payload(*, aud: str, nonce: str, issued_at: int, expires_at: int) -> str:
    return f"rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}"


def build_action_payload(
    *,
    aud: str,
    session_token: str,
    action: str,
    action_payload: dict[str, Any],
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    body = json.dumps(action_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_hash = hashlib.sha256(body).hexdigest()
    return f"rare-act-v1:{aud}:{session_token}:{action}:{body_hash}:{nonce}:{issued_at}:{expires_at}"


def issue_agent_delegation(
    *,
    agent_id: str,
    session_pubkey: str,
    aud: str,
    scope: list[str],
    signer_private_key: Ed25519PrivateKey,
    kid: str,
    ttl_seconds: int,
    jti: str,
) -> str:
    iat = now_ts()
    payload = {
        "typ": "rare.delegation",
        "ver": 1,
        "iss": "agent",
        "agent_id": agent_id,
        "session_pubkey": session_pubkey,
        "aud": aud,
        "scope": scope,
        "iat": iat,
        "exp": iat + ttl_seconds,
        "act": "delegated_by_agent",
        "jti": jti,
    }
    return sign_jws(payload=payload, private_key=signer_private_key, kid=kid, typ="rare.delegation+jws")


def write_secret_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def load_key_value(raw_value: str | None, path_value: str | None, label: str) -> str:
    if raw_value and path_value:
        raise ValueError(f"provide either --{label} or --{label}-file, not both")
    if raw_value:
        return raw_value
    if path_value:
        return Path(path_value).read_text(encoding="utf-8").strip()
    raise ValueError(f"missing --{label} or --{label}-file")


def issued_window(ttl_seconds: int, issued_at: int | None, expires_at: int | None) -> tuple[int, int]:
    resolved_issued = now_ts() if issued_at is None else issued_at
    resolved_expires = resolved_issued + ttl_seconds if expires_at is None else expires_at
    if resolved_expires <= resolved_issued:
        raise ValueError("expires_at must be greater than issued_at")
    return resolved_issued, resolved_expires


def emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_gen_keypair(args: argparse.Namespace) -> int:
    private_key, public_key = generate_keypair()
    payload: dict[str, Any] = {"public_key": public_key}
    if args.private_key_file:
        write_secret_file(Path(args.private_key_file), private_key)
        payload["private_key_file"] = str(Path(args.private_key_file))
    if args.show_private_key:
        payload["private_key"] = private_key
    return emit(payload)


def cmd_register(args: argparse.Namespace) -> int:
    private_key_value = load_key_value(args.private_key, args.private_key_file, "private-key")
    private_key = load_private_key(private_key_value)
    agent_id = public_key_to_b64(private_key.public_key())
    issued_at, expires_at = issued_window(args.ttl_seconds, args.issued_at, args.expires_at)
    nonce = args.nonce or generate_nonce(10)
    sign_input = build_register_payload(
        agent_id=agent_id,
        name=args.name,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return emit(
        {
            "agent_id": agent_id,
            "name": args.name,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": sign_detached(sign_input, private_key),
        }
    )


def cmd_set_name(args: argparse.Namespace) -> int:
    private_key_value = load_key_value(args.private_key, args.private_key_file, "private-key")
    private_key = load_private_key(private_key_value)
    require_agent_match(private_key, args.agent_id)
    issued_at, expires_at = issued_window(args.ttl_seconds, args.issued_at, args.expires_at)
    nonce = args.nonce or generate_nonce(10)
    sign_input = build_set_name_payload(
        agent_id=args.agent_id,
        name=args.name,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return emit(
        {
            "agent_id": args.agent_id,
            "name": args.name,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": sign_detached(sign_input, private_key),
        }
    )


def cmd_issue_full_attestation(args: argparse.Namespace) -> int:
    private_key_value = load_key_value(args.private_key, args.private_key_file, "private-key")
    private_key = load_private_key(private_key_value)
    require_agent_match(private_key, args.agent_id)
    issued_at, expires_at = issued_window(args.ttl_seconds, args.issued_at, args.expires_at)
    nonce = args.nonce or generate_nonce(10)
    sign_input = build_full_attestation_issue_payload(
        agent_id=args.agent_id,
        platform_aud=args.platform_aud,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return emit(
        {
            "agent_id": args.agent_id,
            "platform_aud": args.platform_aud,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_agent": sign_detached(sign_input, private_key),
        }
    )


def cmd_upgrade_request(args: argparse.Namespace) -> int:
    private_key_value = load_key_value(args.private_key, args.private_key_file, "private-key")
    private_key = load_private_key(private_key_value)
    require_agent_match(private_key, args.agent_id)
    request_id = args.request_id or generate_nonce(12)
    issued_at, expires_at = issued_window(args.ttl_seconds, args.issued_at, args.expires_at)
    nonce = args.nonce or generate_nonce(10)
    sign_input = build_upgrade_request_payload(
        agent_id=args.agent_id,
        target_level=args.target_level,
        request_id=request_id,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    payload: dict[str, Any] = {
        "agent_id": args.agent_id,
        "target_level": args.target_level,
        "request_id": request_id,
        "nonce": nonce,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "signature_by_agent": sign_detached(sign_input, private_key),
    }
    if args.contact_email:
        payload["contact_email"] = args.contact_email
    payload["send_email"] = not args.no_send_email
    return emit(payload)


def cmd_prepare_auth(args: argparse.Namespace) -> int:
    private_key_value = load_key_value(args.private_key, args.private_key_file, "private-key")
    private_key = load_private_key(private_key_value)
    require_agent_match(private_key, args.agent_id)
    session_private_key_value, session_pubkey = generate_keypair()
    session_private_key = load_private_key(session_private_key_value)
    sign_input = build_auth_challenge_payload(
        aud=args.aud,
        nonce=args.nonce,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
    )
    signature = sign_detached(sign_input, session_private_key)
    session_payload: dict[str, Any] = {
        "agent_id": args.agent_id,
        "session_pubkey": session_pubkey,
        "delegation_token": issue_agent_delegation(
            agent_id=args.agent_id,
            session_pubkey=session_pubkey,
            aud=args.aud,
            scope=args.scope,
            signer_private_key=private_key,
            kid=args.kid or f"agent-{args.agent_id[:8]}",
            ttl_seconds=args.delegation_ttl_seconds,
            jti=args.jti or generate_nonce(12),
        ),
        "signature_by_session": signature,
    }
    if args.session_private_key_file:
        write_secret_file(Path(args.session_private_key_file), session_private_key_value)
        session_payload["session_private_key_file"] = str(Path(args.session_private_key_file))
    elif args.show_session_private_key:
        session_payload["session_private_key"] = session_private_key_value
    else:
        raise ValueError("prepare-auth requires --session-private-key-file or --show-session-private-key")
    return emit(session_payload)


def parse_json_object(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("action payload must be a JSON object")
    return parsed


def cmd_sign_action(args: argparse.Namespace) -> int:
    private_key_value = load_key_value(args.session_private_key, args.session_private_key_file, "session-private-key")
    private_key = load_private_key(private_key_value)
    session_pubkey = public_key_to_b64(private_key.public_key())
    action_payload = parse_json_object(args.action_payload)
    issued_at, expires_at = issued_window(args.ttl_seconds, args.issued_at, args.expires_at)
    nonce = args.nonce or generate_nonce(10)
    sign_input = build_action_payload(
        aud=args.aud,
        session_token=args.session_token,
        action=args.action,
        action_payload=action_payload,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return emit(
        {
            "aud": args.aud,
            "action": args.action,
            "action_payload": action_payload,
            "session_pubkey": session_pubkey,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_by_session": sign_detached(sign_input, private_key),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal Rare signing helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen_keypair = subparsers.add_parser("gen-keypair", help="Generate an Ed25519 keypair")
    gen_keypair.add_argument("--private-key-file", default=None)
    gen_keypair.add_argument("--show-private-key", action="store_true")
    gen_keypair.set_defaults(func=cmd_gen_keypair)

    register = subparsers.add_parser("register", help="Sign self-hosted registration input")
    register.add_argument("--private-key", default=None)
    register.add_argument("--private-key-file", default=None)
    register.add_argument("--name", required=True)
    register.add_argument("--nonce", default=None)
    register.add_argument("--issued-at", type=int, default=None)
    register.add_argument("--expires-at", type=int, default=None)
    register.add_argument("--ttl-seconds", type=int, default=120)
    register.set_defaults(func=cmd_register)

    set_name = subparsers.add_parser("set-name", help="Sign set-name input")
    set_name.add_argument("--private-key", default=None)
    set_name.add_argument("--private-key-file", default=None)
    set_name.add_argument("--agent-id", required=True)
    set_name.add_argument("--name", required=True)
    set_name.add_argument("--nonce", default=None)
    set_name.add_argument("--issued-at", type=int, default=None)
    set_name.add_argument("--expires-at", type=int, default=None)
    set_name.add_argument("--ttl-seconds", type=int, default=120)
    set_name.set_defaults(func=cmd_set_name)

    issue_full = subparsers.add_parser("issue-full-attestation", help="Sign full attestation issue input")
    issue_full.add_argument("--private-key", default=None)
    issue_full.add_argument("--private-key-file", default=None)
    issue_full.add_argument("--agent-id", required=True)
    issue_full.add_argument("--platform-aud", required=True)
    issue_full.add_argument("--nonce", default=None)
    issue_full.add_argument("--issued-at", type=int, default=None)
    issue_full.add_argument("--expires-at", type=int, default=None)
    issue_full.add_argument("--ttl-seconds", type=int, default=120)
    issue_full.set_defaults(func=cmd_issue_full_attestation)

    upgrade = subparsers.add_parser("upgrade-request", help="Sign an upgrade request input")
    upgrade.add_argument("--private-key", default=None)
    upgrade.add_argument("--private-key-file", default=None)
    upgrade.add_argument("--agent-id", required=True)
    upgrade.add_argument("--target-level", required=True, choices=["L1", "L2"])
    upgrade.add_argument("--request-id", default=None)
    upgrade.add_argument("--nonce", default=None)
    upgrade.add_argument("--issued-at", type=int, default=None)
    upgrade.add_argument("--expires-at", type=int, default=None)
    upgrade.add_argument("--ttl-seconds", type=int, default=120)
    upgrade.add_argument("--contact-email", default=None)
    upgrade.add_argument("--no-send-email", action="store_true")
    upgrade.set_defaults(func=cmd_upgrade_request)

    prepare_auth = subparsers.add_parser("prepare-auth", help="Generate session proof for platform login")
    prepare_auth.add_argument("--private-key", default=None)
    prepare_auth.add_argument("--private-key-file", default=None)
    prepare_auth.add_argument("--agent-id", required=True)
    prepare_auth.add_argument("--aud", required=True)
    prepare_auth.add_argument("--nonce", required=True)
    prepare_auth.add_argument("--issued-at", required=True, type=int)
    prepare_auth.add_argument("--expires-at", required=True, type=int)
    prepare_auth.add_argument("--scope", nargs="*", default=["login"])
    prepare_auth.add_argument("--delegation-ttl-seconds", type=int, default=3600)
    prepare_auth.add_argument("--kid", default=None)
    prepare_auth.add_argument("--jti", default=None)
    prepare_auth.add_argument("--session-private-key-file", default=None)
    prepare_auth.add_argument("--show-session-private-key", action="store_true")
    prepare_auth.set_defaults(func=cmd_prepare_auth)

    sign_action = subparsers.add_parser("sign-action", help="Sign a platform action with a session key")
    sign_action.add_argument("--session-private-key", default=None)
    sign_action.add_argument("--session-private-key-file", default=None)
    sign_action.add_argument("--aud", required=True)
    sign_action.add_argument("--session-token", required=True)
    sign_action.add_argument("--action", required=True)
    sign_action.add_argument("--action-payload", required=True)
    sign_action.add_argument("--nonce", default=None)
    sign_action.add_argument("--issued-at", type=int, default=None)
    sign_action.add_argument("--expires-at", type=int, default=None)
    sign_action.add_argument("--ttl-seconds", type=int, default=120)
    sign_action.set_defaults(func=cmd_sign_action)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
