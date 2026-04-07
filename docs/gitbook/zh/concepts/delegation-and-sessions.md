# 委托与会话

Rare 登录时，Agent 不直接拿长期身份私钥和平台交互，而是委托一个短期会话密钥。

## 委托令牌

委托令牌是一个 JWS，把会话公钥绑定到：

- 某个 `agent_id`
- 某个平台 `aud`
- 某组 `scope`

固定要求：

- Header `typ=rare.delegation+jws`
- Payload `typ=rare.delegation`
- `iss=agent` 或 `iss=rare-signer`

## 登录时序

1. 平台发放一次性 challenge
2. Agent 用会话私钥签 `rare-auth-v1:...`
3. Agent 生成或请求委托令牌
4. 平台校验 challenge、delegation、identity attestation
5. 平台建立 session

## 三元一致性

这是平台侧必须强制校验的安全不变量：

```text
auth_complete.agent_id == delegation.agent_id == attestation.sub
```

这样可以防止攻击者把不同身份材料拼接混用。

## 会话内动作签名

会话建立后，后续动作由会话密钥签名，而不是身份长期密钥：

```text
rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(payload))}:{nonce}:{issued_at}:{expires_at}
```

