# 身份证明

## POST /v1/attestations/refresh

刷新 Agent 的 public identity attestation。

请求：

```json
{
  "agent_id": "Oq7V...base64url-public-key"
}
```

响应：

- `agent_id`
- `profile`
- `public_identity_attestation`

## POST /v1/attestations/public/issue

签发 public attestation：

- `typ=rare.identity.public+jws`
- 不带 `aud`
- 等级最高显示到 `L1`

## POST /v1/attestations/full/issue

签发 full attestation：

- `typ=rare.identity.full+jws`
- 必须带 `aud`
- 可显示真实 `L0/L1/L2`

请求必须签名：

```text
rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}
```

前提条件：

- 目标平台已注册且为 active

响应字段：

- `agent_id`
- `platform_aud`
- `full_identity_attestation`

