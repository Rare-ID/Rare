# 平台管理

Rare 通过 DNS TXT 验证平台所有权，然后允许平台接入 full attestation 和事件上报。

## POST /v1/platforms/register/challenge

申请平台注册 challenge。

请求字段：

- `platform_aud`
- `domain`

响应字段：

- `challenge_id`
- `txt_name`
- `txt_value`
- `expires_at`

当前 TXT 名称格式示例：

```text
_rare-challenge.example.com
```

## POST /v1/platforms/register/complete

在 DNS 记录生效后完成注册。

请求字段：

- `challenge_id`
- `platform_id`
- `platform_aud`
- `domain`
- `keys[]`

每个 key 项包括：

- `kid`
- `public_key`

校验点：

1. TXT 记录值匹配
2. challenge 未过期
3. challenge 只能消费一次
4. `kid` 不能重复

