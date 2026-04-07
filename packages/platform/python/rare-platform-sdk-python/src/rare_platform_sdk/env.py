from __future__ import annotations

import os
import re
from typing import Mapping

from rare_platform_sdk.types import RarePlatformEnv

DEFAULT_RARE_BASE_URL = "https://api.rareid.cc"


def _require_env_string(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ValueError(f"missing required environment variable {key}")
    return value


def derive_platform_id_from_aud(aud: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", aud.strip().lower()).strip("-")
    if not normalized:
        raise ValueError("PLATFORM_AUD must contain at least one alphanumeric character")
    return normalized


def read_rare_platform_env(
    env: Mapping[str, str] | None = None,
) -> RarePlatformEnv:
    resolved_env = os.environ if env is None else env
    platform_aud = _require_env_string(resolved_env, "PLATFORM_AUD")
    rare_base_url = resolved_env.get("RARE_BASE_URL", DEFAULT_RARE_BASE_URL).strip().rstrip("/")
    platform_id = resolved_env.get("PLATFORM_ID", "").strip() or derive_platform_id_from_aud(
        platform_aud
    )
    rare_signer_public_key_b64 = resolved_env.get("RARE_SIGNER_PUBLIC_KEY_B64", "").strip() or None

    return RarePlatformEnv(
        platform_aud=platform_aud,
        platform_id=platform_id,
        rare_base_url=rare_base_url,
        rare_signer_public_key_b64=rare_signer_public_key_b64,
    )
