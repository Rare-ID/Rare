# Python Getting Started

The Python SDK targets web applications that want Rare login with minimal ceremony, especially FastAPI services.

## Install

```bash
pip install rare-platform-sdk
```

## Required Environment

Quickstart requires exactly one environment variable:

```bash
export PLATFORM_AUD=platform.example.com
```

Optional:

```bash
export RARE_BASE_URL=https://api.rareid.cc
export RARE_SIGNER_PUBLIC_KEY_B64=<rare signer public key>
export PLATFORM_ID=platform-example-com
```

Notes:

- `PLATFORM_AUD` is the audience your platform expects during login
- if `RARE_SIGNER_PUBLIC_KEY_B64` is omitted, the SDK discovers it from Rare JWKS
- `PLATFORM_ID` is mainly needed for full-mode workflows

## Minimal Setup

```python
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    create_rare_platform_kit_from_env,
)

challenge_store = InMemoryChallengeStore()
replay_store = InMemoryReplayStore()
session_store = InMemorySessionStore()

kit = create_rare_platform_kit_from_env(
    challenge_store=challenge_store,
    replay_store=replay_store,
    session_store=session_store,
)
```

## Auth Flow

1. Issue a challenge:

```python
challenge = await kit.issue_challenge()
```

2. Complete login with the agent-submitted payload:

```python
from rare_platform_sdk import AuthCompleteInput

result = await kit.complete_auth(
    AuthCompleteInput(
        nonce=payload["nonce"],
        agent_id=payload["agent_id"],
        session_pubkey=payload["session_pubkey"],
        delegation_token=payload["delegation_token"],
        signature_by_session=payload["signature_by_session"],
        public_identity_attestation=payload.get("public_identity_attestation"),
        full_identity_attestation=payload.get("full_identity_attestation"),
    )
)
```

The result includes the platform session token plus common identity fields:

- `session_token`
- `agent_id`
- `identity_mode`
- `level`
- `display_name`

## Session Lookup

For non-FastAPI code, resolve a session manually:

```python
session = await resolve_platform_session(
    session_store,
    authorization=authorization_header,
    cookie_value=cookie_value,
)
```

## Local Validation

Once your platform is running, validate the quickstart path with the Rare CLI:

```bash
rare register --name alice
rare login --aud platform.example.com --platform-url http://127.0.0.1:8000/rare --public-only
```

## Next Pages

- [FastAPI Integration](fastapi-integration.md)
- [Python API Reference](api-reference.md)
