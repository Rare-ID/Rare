from __future__ import annotations

import json
from pathlib import Path

from rare_identity_protocol import (
    build_action_payload,
    build_auth_challenge_payload,
    build_full_attestation_issue_payload,
    build_register_payload,
    build_set_name_payload,
    build_upgrade_request_payload,
)


def test_rip_v1_signing_input_vectors() -> None:
    root = Path(__file__).resolve().parent
    vectors_path = root / "fixtures" / "rip-v1-signing-inputs.json"
    vectors = json.loads(vectors_path.read_text(encoding="utf-8"))

    challenge = vectors["challenge"]
    assert build_auth_challenge_payload(**challenge["input"]) == challenge["expected"]

    set_name = vectors["set_name"]
    assert build_set_name_payload(**set_name["input"]) == set_name["expected"]

    set_name_nfkc_trim = vectors["set_name_nfkc_trim"]
    assert (
        build_set_name_payload(**set_name_nfkc_trim["input"])
        == set_name_nfkc_trim["expected"]
    )

    register = vectors["register"]
    assert build_register_payload(**register["input"]) == register["expected"]

    register_nfkc_trim = vectors["register_nfkc_trim"]
    assert (
        build_register_payload(**register_nfkc_trim["input"])
        == register_nfkc_trim["expected"]
    )

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
