from __future__ import annotations

import base64
import binascii
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from rare_identity_protocol.errors import SignatureError, TokenValidationError


RAW_KEY_SIZE = 32


def now_ts() -> int:
    return int(time.time())


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def json_dumps_compact(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def generate_ed25519_keypair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64url_encode(private_raw), b64url_encode(public_raw)


def load_private_key(raw_b64url: str) -> Ed25519PrivateKey:
    try:
        key_bytes = b64url_decode(raw_b64url)
    except (ValueError, binascii.Error) as exc:
        raise TokenValidationError("invalid Ed25519 private key encoding") from exc
    if len(key_bytes) != RAW_KEY_SIZE:
        raise TokenValidationError("invalid Ed25519 private key length")
    return Ed25519PrivateKey.from_private_bytes(key_bytes)


def load_public_key(raw_b64url: str) -> Ed25519PublicKey:
    try:
        key_bytes = b64url_decode(raw_b64url)
    except (ValueError, binascii.Error) as exc:
        raise TokenValidationError("invalid Ed25519 public key encoding") from exc
    if len(key_bytes) != RAW_KEY_SIZE:
        raise TokenValidationError("invalid Ed25519 public key length")
    return Ed25519PublicKey.from_public_bytes(key_bytes)


def public_key_to_b64(public_key: Ed25519PublicKey) -> str:
    return b64url_encode(
        public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )


def sign_detached(message: str, private_key: Ed25519PrivateKey) -> str:
    signature = private_key.sign(message.encode("utf-8"))
    return b64url_encode(signature)


def verify_detached(message: str, signature_b64url: str, public_key: Ed25519PublicKey) -> None:
    try:
        signature = b64url_decode(signature_b64url)
        public_key.verify(signature, message.encode("utf-8"))
    except (InvalidSignature, ValueError) as exc:
        raise SignatureError("invalid detached signature") from exc


@dataclass(frozen=True)
class DecodedJWS:
    header: dict[str, Any]
    payload: dict[str, Any]
    signing_input: bytes
    signature: bytes


def sign_jws(
    *,
    payload: dict[str, Any],
    private_key: Ed25519PrivateKey,
    kid: str,
    typ: str,
) -> str:
    header = {"alg": "EdDSA", "kid": kid, "typ": typ}
    encoded_header = b64url_encode(json_dumps_compact(header))
    encoded_payload = b64url_encode(json_dumps_compact(payload))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = private_key.sign(signing_input)
    encoded_signature = b64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_jws(token: str) -> DecodedJWS:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise TokenValidationError("invalid compact JWS format") from exc

    try:
        header = json.loads(b64url_decode(encoded_header))
        payload = json.loads(b64url_decode(encoded_payload))
        signature = b64url_decode(encoded_signature)
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenValidationError("invalid JWS encoding") from exc

    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise TokenValidationError("JWS header/payload must be JSON objects")

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    return DecodedJWS(
        header=header,
        payload=payload,
        signing_input=signing_input,
        signature=signature,
    )


def verify_jws(token: str, public_key: Ed25519PublicKey) -> DecodedJWS:
    decoded = decode_jws(token)

    if decoded.header.get("alg") != "EdDSA":
        raise TokenValidationError("unsupported JWS alg")

    try:
        public_key.verify(decoded.signature, decoded.signing_input)
    except InvalidSignature as exc:
        raise SignatureError("invalid JWS signature") from exc

    return decoded


def generate_nonce(length: int = 24) -> str:
    return secrets.token_urlsafe(length)
