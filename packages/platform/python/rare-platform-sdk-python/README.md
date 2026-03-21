# rare-platform-sdk

Python toolkit for third-party platforms integrating Rare with local verification-first defaults.

## What It Is

`rare-platform-sdk` helps Python services issue Rare auth challenges, complete login, verify delegated signed actions, manage platform sessions, and optionally ingest signed negative-event signals back into Rare.

## Who It Is For

- Python and FastAPI platforms adding Rare login
- Backend teams that want local identity/delegation verification
- Integrators that need Redis-backed replay protection and session storage

## Quick Start

```bash
pip install rare-platform-sdk
```

```python
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    RareApiClient,
    RarePlatformKitConfig,
    create_rare_platform_kit,
)

rare = RareApiClient(rare_base_url="https://api.rareid.cc")
kit = create_rare_platform_kit(
    RarePlatformKitConfig(
        aud="platform",
        rare_api_client=rare,
        challenge_store=InMemoryChallengeStore(),
        replay_store=InMemoryReplayStore(),
        session_store=InMemorySessionStore(),
    )
)
```

FastAPI integration:

```python
from fastapi import FastAPI
from rare_platform_sdk import create_fastapi_rare_router

app = FastAPI()
app.include_router(create_fastapi_rare_router(kit, prefix="/rare"))
```

## Production Notes

- Challenge nonces must be one-time use.
- Delegation replay protection must be atomic.
- Full identity mode requires `payload.aud == expected_aud`.
- Identity triad must match:
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`
- Public identity mode is capped to `L1` effective governance.

## Development

```bash
pip install -r requirements-test.lock
pip install -e .[test] --no-deps
pytest -q
python -m build
```
