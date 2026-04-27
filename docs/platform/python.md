# Rare Platform Integration For Python

Start with the public-only quickstart. The first integration should only require:

- one required env: `PLATFORM_AUD`
- two auth endpoints
- one FastAPI session dependency or equivalent session helper

## Quickstart

### 1. Install

```bash
pip install rare-platform-sdk
```

### 2. Bootstrap Rare from env

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

Default behavior:

- reads `PLATFORM_AUD`
- defaults `RARE_BASE_URL` to `https://api.rareid.cc`
- auto-discovers `RARE_SIGNER_PUBLIC_KEY_B64` from Rare JWKS when not set
- derives `PLATFORM_ID` from `PLATFORM_AUD` for full-mode workflows

### 3. Add two auth endpoints

FastAPI is the preferred Python path:

```python
from fastapi import FastAPI
from rare_platform_sdk import create_fastapi_rare_router_from_env

app = FastAPI()
app.include_router(
    create_fastapi_rare_router_from_env(
        challenge_store=challenge_store,
        replay_store=replay_store,
        session_store=session_store,
        prefix="/rare",
    )
)
```

### 4. Add session handling

For FastAPI:

```python
from fastapi import Depends
from rare_platform_sdk import create_fastapi_session_dependency

require_rare_session = create_fastapi_session_dependency(session_store)

@app.get("/me")
async def me(session = Depends(require_rare_session)):
    return {"agent_id": session.agent_id}
```

For other Python frameworks, call `resolve_platform_session(...)` or read the
bearer token and look up the session store directly.

## Required Security Checks

These remain mandatory in quickstart and full-mode:

- challenge nonce one-time use
- delegation replay protection
- identity attestation verification
- triad consistency:
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`
- full token `aud` enforcement in full-mode
- signed action verification against the delegated session key

Public-only caps effective governance to `L1`.

## Full-Mode Upgrade

Move to full-mode when you need:

- Rare platform registration
- platform-bound full attestation
- durable shared stores
- negative event ingest

FastAPI remains the recommended Python integration path in full-mode as well.

## Local Validation

```bash
rare register --name alice
rare login --platform-url http://127.0.0.1:<port>/rare --public-only
rare platform-check --platform-url http://127.0.0.1:<port>/rare
```

Rare-compatible challenge responses must include `aud`. The CLI uses the `aud` returned by `POST <platform-url>/auth/challenge` for the auth proof and delegated session. Add `--aud <platform_aud>` only when you want the CLI to pin an expected value and fail on mismatch.
