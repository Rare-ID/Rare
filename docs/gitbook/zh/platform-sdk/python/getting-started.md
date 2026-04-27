# Python 入门

Python SDK 适合把 Rare 登录接入 FastAPI 或其他 Python Web 服务。

## 安装

```bash
pip install rare-platform-sdk
```

## 必填环境变量

最小接入只要求一个环境变量：

```bash
export PLATFORM_AUD=platform.example.com
```

可选环境变量：

```bash
export RARE_BASE_URL=https://api.rareid.cc
export RARE_SIGNER_PUBLIC_KEY_B64=<rare signer public key>
export PLATFORM_ID=platform-example-com
```

说明：

- `PLATFORM_AUD` 是登录受众标识，平台和 Agent CLI 登录时必须一致
- 未提供 `RARE_SIGNER_PUBLIC_KEY_B64` 时，SDK 会通过 Rare JWKS 自动发现
- `PLATFORM_ID` 主要用于 full-mode 相关流程；quickstart 可不填

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

1. 平台签发 challenge：

```python
challenge = await kit.issue_challenge()
```

2. Agent 完成签名后，平台用提交结果换取 Rare session：

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

返回结果里包含平台 session token，以及平台侧常用的身份字段：

- `session_token`
- `agent_id`
- `identity_mode`
- `level`
- `display_name`

## 非 FastAPI 场景的会话读取

如果你不是用 FastAPI，也可以直接解析 Bearer token 或 cookie：

```python
from rare_platform_sdk import resolve_platform_session

session = await resolve_platform_session(
    session_store,
    authorization=authorization_header,
    cookie_value=cookie_value,
)
```

## 本地验证

平台启动后，可以直接用 Rare CLI 跑通 quickstart：

```bash
rare register --name alice
rare login --platform-url http://127.0.0.1:8000/rare --public-only
rare platform-check --platform-url http://127.0.0.1:8000/rare
```

challenge 响应必须包含 `aud`；只有需要 pin 预期值时才加 `--aud platform.example.com`。

## 下一步

- [FastAPI 集成](fastapi-integration.md)
- [API 参考](api-reference.md)
