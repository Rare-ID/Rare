# FastAPI Integration

FastAPI is the preferred Python integration path because the SDK already ships router and dependency helpers.

## Mount Rare Auth Routes

```python
from fastapi import Depends, FastAPI
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    create_fastapi_rare_router_from_env,
    create_fastapi_session_dependency,
)

challenge_store = InMemoryChallengeStore()
replay_store = InMemoryReplayStore()
session_store = InMemorySessionStore()

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

@app.get("/me")
async def me(session = Depends(require_rare_session)):
    return {
        "agent_id": session.agent_id,
        "display_name": session.display_name,
        "level": session.effective_level,
    }
```

This exposes:

- `POST /rare/auth/challenge`
- `POST /rare/auth/complete`

## Login Request Body

The platform should accept the following JSON payload from a Rare agent login:

```json
{
  "nonce": "challenge nonce",
  "agent_id": "ed25519 public key",
  "session_pubkey": "delegated session public key",
  "delegation_token": "rare.delegation+jws",
  "signature_by_session": "detached signature over rare-auth-v1 payload",
  "public_identity_attestation": "rare.identity.public+jws",
  "full_identity_attestation": "rare.identity.full+jws"
}
```

Notes:

- provide at least one of `public_identity_attestation` or `full_identity_attestation`
- for quickstart / `public-only`, public identity is usually enough
- the router already handles challenge consumption, delegation validation, identity validation, and replay protection

## Require a Session

By default the dependency reads:

- `Authorization: Bearer <session_token>`
- the `rare_session` cookie

You can also override the cookie name:

```python
require_rare_session = create_fastapi_session_dependency(
    session_store,
    cookie_name="my_rare_session",
)
```

## Custom Router Setup

If you want to construct the kit yourself, use:

```python
from rare_platform_sdk import create_fastapi_rare_router

app.include_router(create_fastapi_rare_router(kit, prefix="/rare"))
```

## Production Note

Replace in-memory stores before running multiple FastAPI instances behind a load balancer.
