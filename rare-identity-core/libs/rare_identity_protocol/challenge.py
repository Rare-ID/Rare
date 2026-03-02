from rare_identity_protocol.name_policy import normalize_name


def build_auth_challenge_payload(
    *,
    aud: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    return f"rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}"


def build_set_name_payload(
    *,
    agent_id: str,
    name: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    normalized_name = normalize_name(name)
    return f"rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}"


def build_register_payload(
    *,
    agent_id: str,
    name: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    normalized_name = normalize_name(name)
    return f"rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}"


def build_platform_grant_payload(
    *,
    agent_id: str,
    platform_aud: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    return f"rare-grant-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}"


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
    return (
        f"rare-upgrade-v1:{agent_id}:{target_level}:"
        f"{request_id}:{nonce}:{issued_at}:{expires_at}"
    )


def build_agent_auth_payload(
    *,
    agent_id: str,
    operation: str,
    resource_id: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    return (
        f"rare-agent-auth-v1:{agent_id}:{operation}:{resource_id}:"
        f"{nonce}:{issued_at}:{expires_at}"
    )
