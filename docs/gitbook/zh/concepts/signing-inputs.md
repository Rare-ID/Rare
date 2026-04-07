# 签名输入

Rare 使用固定格式的签名输入字符串，避免重放和跨上下文复用。

## 核心格式

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

全量证明签发：

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

所有校验器都必须保证：

- nonce 只能使用一次
- `expires_at > issued_at`
- 时间窗口很短
- 允许的时钟偏差最多 30 秒
- `aud`、`request_id`、`target_level` 等上下文字段必须完全匹配

## Canonical JSON

动作 payload 哈希使用：

- UTF-8
- key 排序
- 紧凑分隔符 `(',', ':')`

