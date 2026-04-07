# Python Getting Started

The Python SDK targets web applications that want Rare login with minimal ceremony, especially FastAPI services.

## Install

```bash
pip install rare-platform-sdk
```

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

## Required Environment

```bash
PLATFORM_AUD=platform.example.com
```

Optional:

```bash
RARE_BASE_URL=https://api.rareid.cc
RARE_SIGNER_PUBLIC_KEY_B64=<rare signer public key>
PLATFORM_ID=platform-example-com
```

## Auth Flow

Issue a challenge:

```python
challenge = await kit.issue_challenge()
```

Complete login:

```python
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

## Session Lookup

For non-FastAPI code, resolve a session manually:

```python
session = await resolve_platform_session(
    session_store,
    authorization=authorization_header,
    cookie_value=cookie_value,
)
```

## Next Pages

- [FastAPI Integration](fastapi-integration.md)
- [Python API Reference](api-reference.md)

