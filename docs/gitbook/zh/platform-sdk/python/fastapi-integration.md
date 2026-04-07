# FastAPI 集成

FastAPI 是 Python 平台接入 Rare 的推荐路径，因为 SDK 已经内置路由和依赖辅助。

## 挂载 Rare 路由

```python
from fastapi import FastAPI
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    create_fastapi_rare_router_from_env,
)

app = FastAPI()
app.include_router(
    create_fastapi_rare_router_from_env(
        challenge_store=InMemoryChallengeStore(),
        replay_store=InMemoryReplayStore(),
        session_store=InMemorySessionStore(),
        prefix="/rare",
    )
)
```

## 会话依赖

```python
from fastapi import Depends
from rare_platform_sdk import create_fastapi_session_dependency

require_rare_session = create_fastapi_session_dependency(session_store)

@app.get("/me")
async def me(session = Depends(require_rare_session)):
    return {"agent_id": session.agent_id}
```

