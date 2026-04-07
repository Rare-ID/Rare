# Python 入门

Python SDK 适合把 Rare 登录接入 FastAPI 或其他 Python Web 服务。

## 安装

```bash
pip install rare-platform-sdk
```

## 最小初始化

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

## 认证流程

```python
challenge = await kit.issue_challenge()
```

```python
result = await kit.complete_auth(...)
```

