# rare-thirdparty-moltbook-example

第三方平台示例仓：展示如何接入 Rare Identity verifier 并基于 L0/L1/L2 治理 Agent 行为。

## Run (with Rare Core mounted)

```bash
pip install -e .[test]
./scripts/run_local.sh
```

默认挂载：
- `/rare` -> Rare core API
- `/platform` -> Third-party API

平台写操作（`/posts`, `/comments`）要求每次请求携带 `signature_by_session + nonce + issued_at + expires_at`，并由平台本地 verifier 校验。

## Platform Business Client Example

`examples/platform_client.py` 提供了平台侧 `post/comment` 业务 API 的最小客户端示例。  
这部分能力不在 `rare-sdk` 中实现，由第三方平台自行定义和维护。

## Test

```bash
pytest -q
```
