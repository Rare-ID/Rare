# 挑战与签名（RIP-0003）

Rare 通过固定签名输入来防止重放和跨流程复用。

## 核心签名输入

挑战登录：

```text
rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}
```

自托管注册：

```text
rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

改名：

```text
rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

Full attestation 签发：

```text
rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}
```

升级请求：

```text
rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}
```

动作签名：

```text
rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(action_payload))}:{nonce}:{issued_at}:{expires_at}
```

## 校验要求

- nonce 一次性消费
- 有效期很短
- `expires_at > issued_at`
- 最多允许 30 秒时钟偏差
- `aud`、`request_id`、`target_level` 等上下文必须完全匹配

