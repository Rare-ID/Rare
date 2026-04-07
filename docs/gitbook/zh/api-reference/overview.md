# API 参考概览

本页说明 Rare API 的通用约定：基础 URL、认证方式、请求格式、错误格式和 JWKS 发现。

## 基础 URL

| 环境 | URL |
|---|---|
| 生产 | `https://api.rareid.cc` |
| 本地开发 | `http://127.0.0.1:8000` |

## 认证方式

### 1. 无认证

例如：

- Agent 自注册
- public attestation 签发
- attestation 刷新

### 2. Hosted signer Bearer Token

```text
Authorization: Bearer <hosted_management_token>
```

### 3. Admin Bearer Token

```text
Authorization: Bearer <admin_token>
```

### 4. Agent Proof Headers

自托管 Agent 也可通过签名证明访问部分接口：

- `X-Rare-Agent-Id`
- `X-Rare-Agent-Nonce`
- `X-Rare-Agent-Issued-At`
- `X-Rare-Agent-Expires-At`
- `X-Rare-Agent-Signature`

当前 proof 载荷格式：

```text
rare-agent-auth-v1:{agent_id}:{op}:{resource}:{nonce}:{issued_at}:{expires_at}
```

## 请求与错误

- Body 必须是 JSON
- 最大请求体大小：`256 KB`

错误统一返回：

```json
{
  "detail": "error message"
}
```

常见状态码：

- `400`
- `401`
- `403`
- `404`
- `409`
- `413`
- `422`
- `429`
- `500`

## 密钥发现

Rare 通过以下端点暴露 JWKS：

```text
GET /.well-known/rare-keys.json
```

平台可据此本地验证 Rare 身份证明和 Rare 签发的委托令牌。

