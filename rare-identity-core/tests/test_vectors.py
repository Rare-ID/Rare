from __future__ import annotations

import json
from pathlib import Path

from rare_identity_protocol import (
    build_action_payload,
    build_auth_challenge_payload,
    build_full_attestation_issue_payload,
    build_platform_grant_payload,
    build_register_payload,
    build_set_name_payload,
    build_upgrade_request_payload,
)


def test_rip_v1_signing_input_vectors() -> None:
    root = Path(__file__).resolve().parents[1]
    vectors_path = root / "docs" / "test-vectors" / "rip-v1-signing-inputs.json"
    vectors = json.loads(vectors_path.read_text(encoding="utf-8"))

    challenge = vectors["challenge"]
    assert build_auth_challenge_payload(**challenge["input"]) == challenge["expected"]

    set_name = vectors["set_name"]
    assert build_set_name_payload(**set_name["input"]) == set_name["expected"]

    register = vectors["register"]
    assert build_register_payload(**register["input"]) == register["expected"]

    platform_grant = vectors["platform_grant"]
    assert build_platform_grant_payload(**platform_grant["input"]) == platform_grant["expected"]

    full_attestation_issue = vectors["full_attestation_issue"]
    assert (
        build_full_attestation_issue_payload(**full_attestation_issue["input"])
        == full_attestation_issue["expected"]
    )

    upgrade_request = vectors["upgrade_request"]
    assert (
        build_upgrade_request_payload(**upgrade_request["input"])
        == upgrade_request["expected"]
    )

    action_post = vectors["action_post"]
    assert build_action_payload(**action_post["input"]) == action_post["expected"]
