# FastAPI Integration

FastAPI is the preferred Python integration path because the SDK already ships router and dependency helpers.

## Mount Rare Auth Routes

```python
from fastapi import FastAPI
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    create_fastapi_rare_router_from_env,
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
```

This exposes:

- `POST /rare/auth/challenge`
- `POST /rare/auth/complete`

## Require a Session

```python
from fastapi import Depends
from rare_platform_sdk import create_fastapi_session_dependency

require_rare_session = create_fastapi_session_dependency(session_store)

@app.get("/me")
async def me(session = Depends(require_rare_session)):
    return {
        "agent_id": session.agent_id,
        "display_name": session.display_name,
        "level": session.effective_level,
    }
```

By default the dependency reads:

- `Authorization: Bearer <session_token>`
- the `rare_session` cookie

## Custom Router Setup

If you want to construct the kit yourself, use:

```python
from rare_platform_sdk import create_fastapi_rare_router

app.include_router(create_fastapi_rare_router(kit, prefix="/rare"))
```

## Production Note

Replace in-memory stores before running multiple FastAPI instances behind a load balancer.

