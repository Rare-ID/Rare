# Rare 用户使用流程（Agent 视角）

本文是 Rare v1 的当前生效流程说明，覆盖从注册到平台登录，再到 L1/L2 升级与完整身份授权。

## 1. 角色与凭证
- `agent_id`：Agent 长期身份（Ed25519 公钥，base64url）。
- `agent private key`：只用于签名，不应泄露给平台。
- `public_identity_attestation`：Rare 签发的基础身份票据，最高展示到 L1。
- `full_identity_attestation`：Rare 签发的平台绑定完整票据，带 `aud`，可含真实 L2。
- `delegation_token`：把会话公钥授权给平台的短期 token。

## 2. 注册（L0）
### 2.1 托管密钥（hosted-signer）
1. Agent 调用 `POST /v1/agents/self_register`，传 `name`（可选）。
2. Rare 生成 `agent_id` 和托管私钥。
3. 返回：
- `agent_id`
- `profile.name`
- `public_identity_attestation`
- `key_mode=hosted-signer`
- `hosted_management_token`（仅注册响应返回一次；用于调用 `/v1/signer/*`）
- `hosted_management_token_expires_at`（Unix 秒级时间戳，token 过期时间）

### 2.2 自托管密钥（self-hosted）
1. Agent 本地生成 Ed25519 密钥对。
2. 构造并签名注册串：`rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`。
3. 调用 `POST /v1/agents/self_register` 提交公钥和签名。
4. Rare 验签通过后注册成功，返回同上（不返回私钥）。

## 3. 可选升级（Agent 请求人类验证）
## 3.1 升级到 L1（邮箱 Magic Link）
1. Agent 发起升级请求：
- 签名串：`rare-upgrade-v1:{agent_id}:L1:{request_id}:{nonce}:{issued_at}:{expires_at}`
- 接口：`POST /v1/upgrades/requests`
- 必填：`contact_email`
2. Rare 创建 `upgrade_request_id`，状态进入 `human_pending`。
3. 发送邮箱链接（本地 stub）：
- `POST /v1/upgrades/l1/email/send-link`
- 需要管理鉴权（hosted bearer 或 self-hosted 签名证明头）
- 仅当 `RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS=1` 时才会回传原始 `token/magic_link`。
4. 人类点击链接：
- `GET /v1/upgrades/l1/email/verify?token=...`
5. Rare 自动升级到 L1，并更新：
- `owner_id=email:<sha256(lower(email))>`
- `level=L1`
- 签发新的 `public_identity_attestation`

## 3.2 升级到 L2（X 或 GitHub 任一）
前置：当前已是 L1。

路径 A（OAuth 回调）：
1. Agent 发起升级请求（`target_level=L2`，同样用 `rare-upgrade-v1` 签名）。
2. `POST /v1/upgrades/l2/social/start` 获取 `authorize_url,state`。
- 需要管理鉴权（hosted bearer 或 self-hosted 签名证明头）
3. 社交回调：`GET /v1/upgrades/l2/social/callback?provider=x|github&code=...&state=...`。
4. Rare 自动升级到 L2，写入对应社交 claim。

路径 B（本地联调捷径）：
1. `POST /v1/upgrades/l2/social/complete` 直接提交 `provider_user_snapshot`。
- 需要管理鉴权（hosted bearer 或 self-hosted 签名证明头）
- 默认关闭；仅在本地联调时通过 `RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS=1` 开启。
2. Rare 校验后自动升级到 L2。

## 4. 平台完整身份授权（grant + full）
默认只有 `public_identity_attestation`。  
如果要让某个平台拿到完整身份（含真实 L2），Agent 需要显式授权。

1. Agent 对平台授权（grant）：
- 签名串：`rare-grant-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- 接口：`POST /v1/agents/platform-grants`
2. Agent 请求完整 attestation：
- 签名串：`rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- 接口：`POST /v1/attestations/full/issue`
3. Rare 前置检查：
- 平台已注册（DNS 证明）
- grant 未撤销
4. 返回 `full_identity_attestation`（绑定 `aud`）。

## 5. 登录第三方平台
1. 平台发 challenge：`POST /auth/challenge`。
2. Agent 准备会话证明：
- challenge 签名串：`rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`
- 生成会话密钥对，签名 challenge。
- 生成 delegation（`aud/scope/exp`）。
3. Agent 调用平台 `POST /auth/complete`，携带：
- `agent_id`
- `session_pubkey`
- `delegation_token`
- `signature_by_session`
- `public_identity_attestation`
- 可选 `full_identity_attestation`
4. 平台本地 verifier 验证通过后完成登录。

## 6. 登录后动作签名
1. Agent 对每次动作签名：
- `rare-act-v1:{aud}:{session_token}:{action}:{sha256(payload)}:{nonce}:{issued_at}:{expires_at}`
2. 平台使用会话公钥验证动作签名并校验 nonce 防重放。

## 7. 常用查询与管理
- 查看授权平台：`GET /v1/agents/platform-grants/{agent_id}`（需要 `Authorization: Bearer <admin_or_bound_hosted_token>`）
- 撤销授权平台：`DELETE /v1/agents/platform-grants/{platform_aud}`
- 刷新 public attestation：`POST /v1/attestations/public/issue`
- 查询升级状态：`GET /v1/upgrades/requests/{upgrade_request_id}`（需要 `Authorization: Bearer <admin_or_bound_hosted_token>`）
- 对上述两个读接口，self-hosted 也可使用签名证明头：
- `X-Rare-Agent-Id`
- `X-Rare-Agent-Nonce`
- `X-Rare-Agent-Issued-At`
- `X-Rare-Agent-Expires-At`
- `X-Rare-Agent-Signature`

### Hosted signer 调用鉴权（新增）
- 所有 `/v1/signer/*` 请求必须携带 `Authorization: Bearer <hosted_management_token>`。
- token 与 `agent_id` 强绑定：`caller token` 对应的 agent 必须与请求体 `agent_id` 一致。
- token 仅适用于 `hosted-signer` 账户；`self-hosted` 账户走本地签名。
- token 有有效期（默认 30 天），过期时间为 `hosted_management_token_expires_at`。
- 轮换 token：`POST /v1/signer/rotate_management_token`。
- 吊销 token：`POST /v1/signer/revoke_management_token`。

## 8. CLI 对应命令
```bash
rare register --name alice
rare rotate-hosted-token
rare revoke-hosted-token
rare request-upgrade --level L1 --email alice@example.com
rare request-upgrade --level L2
rare start-social --request-id <id> --provider github
rare grant-platform --aud platform
rare issue-full-attestation --aud platform
rare login --aud platform
```
