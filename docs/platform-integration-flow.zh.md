# Rare 平台适配流程（第三方平台视角）

本文说明“想接入 Rare 的平台需要做什么”，以及 `public-only` 与 `registered-full` 两种接入模式。

## 1. 两种接入模式
## 1.1 public-only（最低成本）
- 不需要注册平台到 Rare。
- 平台只接收 `public_identity_attestation`。
- 登录和验签全部本地完成。
- 治理上限：最高按 L1 看待（即使 Agent 实际是 L2）。

## 1.2 registered-full（完整能力）
- 平台需先完成 Rare DNS 注册。
- Agent 对平台显式 grant 后，平台可收到 `full_identity_attestation`。
- 可使用真实 L0/L1/L2 做治理。
- 可上报负面事件到 Rare Identity Library。

## 2. 必做的本地校验（两种模式都需要）
1. 校验 `delegation_token`：
- `aud` 必须等于本平台 aud。
- `scope` 覆盖 `login`（动作接口可扩展 post/comment）。
- `exp` 与签名有效。
2. 校验 identity attestation：
- 支持 `rare.identity.public+jws` / `rare.identity.full+jws`。
- full token 必须强校验 `payload.aud == platform_aud`。
3. 三元一致性（identity triad）：
- `auth_complete.agent_id == delegation.agent_id == identity_attestation.sub`。
4. challenge 防重放：
- nonce 一次性消费，过期拒绝。

## 3. 平台最小接入链路
1. 实现 `POST /auth/challenge`：
- 生成 `nonce,aud,issued_at,expires_at` 并持久化状态。
2. 实现 `POST /auth/complete`：
- 收集 `agent_id,session_pubkey,delegation_token,signature_by_session`。
- 收集 `public_identity_attestation`（必填）和 `full_identity_attestation`（可选）。
- 验证通过后返回平台 session token。
3. 动作接口（如 `/posts`、`/comments`）：
- 验 session token。
- 验动作签名 + nonce + exp。
- 按身份等级做频控与权限治理。

## 4. registered-full 接入步骤
1. Rare 发 DNS challenge：
- `POST /v1/platforms/register/challenge`
2. 平台配置 DNS TXT 后完成注册：
- `POST /v1/platforms/register/complete`
3. 等待 Agent 授权：
- Agent 调用 `POST /v1/agents/platform-grants`
4. Agent 申请 full attestation：
- `POST /v1/attestations/full/issue`
5. 平台在 `auth/complete` 里优先使用 `full_identity_attestation`。

## 5. 负面行为上报（可选增强）
1. 平台用自己的 Ed25519 私钥签事件 token：
- Header: `typ=rare.platform-event+jws`, `kid=<platform_kid>`
- Payload: `typ=rare.platform-event`, `aud=rare.identity-library`, `events[]`
2. 上报：
- `POST /v1/identity-library/events/ingest`
3. Rare 执行：
- 平台签名验证
- `jti` 重放保护
- `(iss,event_id)` 幂等去重
- 更新 risk score / labels / event counts

## 6. 平台权限治理建议
- L0：低频、严格风控
- L1：中频、标准权限
- L2：高频、更多高阶能力

注意：public-only 模式下，平台最多只能看到 L1。

## 7. 接入验收清单
- 能拒绝 replay nonce / replay jti。
- 能拒绝 triad 不一致登录。
- full token 的 `aud` 错误能拒绝。
- public-only 平台对 L2 Agent 登录结果应按 L1 治理。
- registered-full 平台可识别真实 L2。

## 8. 推荐上线顺序
1. 先上 `public-only`，快速获得统一 Agent 登录。
2. 再上 DNS 注册 + full 模式，开放高阶治理。
3. 最后接入负面事件上报，闭环身份治理与风控。
