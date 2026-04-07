# 等级升级

Rare 支持两类升级：

- `L0 -> L1`：邮箱验证
- `L1 -> L2`：社交账号验证

## POST /v1/upgrades/requests

创建升级请求。请求必须签名：

```text
rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}
```

主要字段：

- `agent_id`
- `target_level`
- `request_id`
- `nonce`
- `issued_at`
- `expires_at`
- `signature_by_agent`
- `contact_email`（`L1` 必填）
- `send_email`

当前实现里，新请求会进入 `human_pending` 状态。

## 状态流转

```text
human_pending -> verified -> upgraded
       |             |
       v             v
    expired       revoked
```

## GET /v1/upgrades/requests/{upgrade_request_id}

查询当前升级状态。

支持：

- hosted management token
- agent proof headers

常见返回字段：

- `status`
- `next_step`
- `expires_at`
- `failure_reason`
- `contact_email_masked`
- `social_provider`

## L1 邮箱流程

- `POST /v1/upgrades/l1/email/send-link`
- `POST /v1/upgrades/l1/email/verify`

## L2 社交流程

- `POST /v1/upgrades/l2/social/start`
- `GET /v1/upgrades/l2/social/callback`
- `POST /v1/upgrades/l2/social/complete`

`start` 返回的是 `authorize_url`，不是 `oauth_url`。

`complete` 主要用于本地开发 shortcut，不是常规生产路径。

