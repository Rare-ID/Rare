# Agent 管理

## POST /v1/agents/self_register

创建 Agent，支持：

- `hosted-signer`
- `self-hosted`

请求字段：

| 字段 | 说明 |
|---|---|
| `name` | 显示名 |
| `key_mode` | `hosted-signer` 或 `self-hosted` |
| `agent_public_key` | 自托管时必填 |
| `nonce` / `issued_at` / `expires_at` / `signature_by_agent` | 自托管注册证明 |

响应字段：

| 字段 | 说明 |
|---|---|
| `agent_id` | Agent 的 Ed25519 公钥 |
| `profile.name` | 显示名 |
| `key_mode` | 密钥模式 |
| `public_identity_attestation` | 初始 public 证明 |
| `hosted_management_token` | 托管模式才返回 |
| `hosted_management_token_expires_at` | 托管 token 过期时间 |

## POST /v1/agents/set_name

更新显示名。请求必须带签名：

```text
rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

成功响应会返回：

- `name`
- `updated_at`
- `public_identity_attestation`

名称校验规则：

- `trim + NFKC`
- 长度 `1..48`
- 不允许控制字符
- 保留词会被拒绝

