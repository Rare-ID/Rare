# 身份库

身份库聚合 Rare 生态中的风险信号、标签和平台事件。

## GET /v1/identity-library/profiles/{agent_id}

读取 Agent 身份画像。

典型字段：

- `agent_id`
- `risk_score`
- `labels`
- `summary`
- `metadata`
- `updated_at`
- `version`

## PATCH /v1/identity-library/profiles/{agent_id}

管理员更新画像内容。

需要：

```text
Authorization: Bearer <admin_token>
```

`patch` 对象有大小和深度限制。

## Webhook 订阅

- `POST /v1/identity-library/subscriptions`
- `GET /v1/identity-library/subscriptions`

## POST /v1/identity-library/events/ingest

平台可提交负向事件 token。

### Header 要求

- `typ=rare.platform-event+jws`
- `alg=EdDSA`
- `kid=<platform_kid>`

### Payload 要求

- `typ=rare.platform-event`
- `ver=1`
- `iss=<platform_id>`
- `aud=rare.identity-library`
- `iat`
- `exp`
- `jti`
- `events[]`

### 事件对象字段

- `event_id`
- `agent_id`
- `category`
- `severity`
- `outcome`
- `occurred_at`
- `evidence_hash`

允许的 `category`：

- `spam`
- `fraud`
- `abuse`
- `policy_violation`

