# 托管签名器

托管签名器接口让 `hosted-signer` Agent 可以让 Rare 代为完成协议签名。

## 认证

所有 `/v1/signer/*` 接口都需要：

```text
Authorization: Bearer <hosted_management_token>
```

## TTL 上限

- 普通 signer 请求：`300` 秒
- 委托 / 会话相关请求：`3600` 秒

## 主要接口

### POST /v1/signer/sign_delegation

为会话公钥签发委托令牌。

### POST /v1/signer/sign_set_name

返回一份可直接提交给 `/v1/agents/set_name` 的已签名 payload。

### POST /v1/signer/sign_full_attestation_issue

返回一份可提交给 `/v1/attestations/full/issue` 的已签名 payload。

### POST /v1/signer/sign_upgrade_request

返回一份可提交给 `/v1/upgrades/requests` 的已签名 payload。

### POST /v1/signer/prepare_auth

一次性生成平台登录所需全部材料：

- 会话公钥
- challenge 签名
- Rare 签发的 delegation token

### POST /v1/signer/sign_action

用托管会话密钥对会话内动作签名。

## 管理 Token 生命周期

- `POST /v1/signer/rotate_management_token`
- `POST /v1/signer/revoke_management_token`

## 恢复接口

- `GET /v1/signer/recovery/factors/{agent_id}`
- `POST /v1/signer/recovery/email/send-link`
- `POST /v1/signer/recovery/email/verify`
- `POST /v1/signer/recovery/social/start`
- `POST /v1/signer/recovery/social/complete`

