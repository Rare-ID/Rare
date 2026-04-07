# 委托（RIP-0002）

委托令牌把一个短期会话公钥绑定到：

- 某个 `agent_id`
- 某个平台 `aud`
- 某组允许的 `scope`

## 格式

- JWS Compact Serialization
- `alg=EdDSA`
- Header `typ=rare.delegation+jws`

## 必需字段

- `typ=rare.delegation`
- `ver=1`
- `iss=agent|rare-signer`
- `agent_id`
- `session_pubkey`
- `aud`
- `scope`
- `iat`
- `exp`
- `act`

## 签名规则

- `iss=agent`：用 Agent 公钥验证
- `iss=rare-signer`：用 Rare delegation signer 公钥验证

## 平台必须校验

1. JWS 签名正确
2. `aud` 完全匹配
3. 请求动作在 `scope` 中
4. 时间窗口有效
5. `jti` 未被重放

## 三元一致性

```text
auth_complete.agent_id == delegation.agent_id == identity_attestation.sub
```

