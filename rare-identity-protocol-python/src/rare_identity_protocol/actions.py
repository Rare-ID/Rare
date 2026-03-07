from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


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
    body_hash = hashlib.sha256(_canonical_json(action_payload).encode("utf-8")).hexdigest()
    return (
        f"rare-act-v1:{aud}:{session_token}:{action}:{body_hash}:{nonce}:{issued_at}:{expires_at}"
    )
