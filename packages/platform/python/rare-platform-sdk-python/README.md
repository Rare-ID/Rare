# rare-platform-sdk

Python toolkit for platforms integrating Rare with adoption-first defaults.

## Integration Modes

- `public-only / quickstart`: start here
- `full-mode / production`: add platform registration, durable stores, full attestation, and event ingest

Quickstart reduces first integration to:

- one required env: `PLATFORM_AUD`
- two auth endpoints
- one session dependency or helper

Auth challenge responses must include `aud`. Agent-side login is URL-first, so `rare login --platform-url <url>` discovers `aud` from `POST <platform-url>/auth/challenge`. `--aud` is still supported as an optional expected-audience pin.

## Quickstart

```bash
pip install rare-platform-sdk
```

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

Defaults:

- `RARE_BASE_URL=https://api.rareid.cc`
- `RARE_SIGNER_PUBLIC_KEY_B64` auto-discovered from Rare JWKS when omitted
- `PLATFORM_ID` derived from `PLATFORM_AUD` for full-mode workflows

## FastAPI

```python
from fastapi import Depends, FastAPI
from rare_platform_sdk import (
    create_fastapi_rare_router_from_env,
    create_fastapi_session_dependency,
)

app = FastAPI()
app.include_router(
    create_fastapi_rare_router_from_env(
        challenge_store=challenge_store,
        replay_store=replay_store,
        session_store=session_store,
        prefix="/rare",
    )
)

require_rare_session = create_fastapi_session_dependency(session_store)
```

FastAPI is the preferred Python integration path.

## Security Notes

Quickstart still enforces:

- challenge nonce one-time use
- delegation replay protection
- identity/delegation triad consistency
- local attestation verification
- public-mode governance cap to `L1`

## Local Validation

```bash
rare register --name alice
rare login --platform-url http://127.0.0.1:<port>/rare --public-only
rare platform-check --platform-url http://127.0.0.1:<port>/rare
```

## Production Notes

- Replace in-memory stores before production
- Move to full-mode only when platform registration or full attestation is required
- Keep bearer-token session transport supported even if you add cookie convenience helpers
