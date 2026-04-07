# FastAPI 集成

FastAPI 是 Python 平台接入 Rare 的推荐路径，因为 SDK 已经内置路由和依赖辅助。

## 挂载 Rare 路由

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

这会暴露两条认证路由：

- `POST /rare/auth/challenge`
- `POST /rare/auth/complete`

## 登录请求体

Rare Agent 登录时，平台需要接收以下 JSON：

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

说明：

- `public_identity_attestation` 和 `full_identity_attestation` 至少提供一个
- quickstart / `public-only` 场景下，通常只需要 public identity
- 路由内部已经完成 challenge 消费、delegation 校验、identity 校验和 replay 防护

## 会话依赖

默认会从以下位置读取平台 session：

- `Authorization: Bearer <session_token>`
- `rare_session` cookie

也可以自定义 cookie 名称：

```python
require_rare_session = create_fastapi_session_dependency(
    session_store,
    cookie_name="my_rare_session",
)
```

## 自定义 router 组装

如果你想先自己创建 kit，再挂载 FastAPI router：

```python
from rare_platform_sdk import create_fastapi_rare_router

app.include_router(create_fastapi_rare_router(kit, prefix="/rare"))
```

## 生产建议

- 单机调试可用内存存储
- 多实例部署前请替换成 Redis 存储
- 即使额外支持 cookie，也建议保留 Bearer token 会话传输
