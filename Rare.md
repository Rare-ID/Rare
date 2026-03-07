# Rare v1（当前生效）总览

Rare 是面向 AI Agent 的身份与治理基础设施，核心目标是：
- 让 Agent 用公私钥签名完成跨平台身份登录
- 让平台在本地完成 verifier 校验（无需每次依赖 Rare 在线鉴权）
- 让平台治理能力从低成本接入逐步升级到完整治理闭环

## 1. 当前协议与能力（v1 clean）
- Identity Attestation 双类型：
  - `rare.identity.public+jws`：低成本登录，最高显示到 L1
  - `rare.identity.full+jws`：平台绑定完整身份（含 `aud`，可包含真实 L2）
- Delegation：
  - `rare.delegation+jws`，支持 `iss=agent|rare-signer`
- 平台接入分层：
  - `public-only`：不注册平台即可接入
  - `registered-full`：完成 DNS 注册后可获取 full 与事件治理能力
- Identity Library：
  - 支持平台负面行为事件上报并更新风险字段

## 2. Agent 生命周期（简版）
1. 注册 L0：
- `POST /v1/agents/self_register`
2. 可选升级：
- L1：Agent 发起升级请求，人类邮箱 Magic Link 验证后自动升级
- L2：Agent 发起升级请求，人类连接 X 或 GitHub 任一后自动升级
3. 平台完整身份：
- `full attestation`：仅注册平台生效时可签发
4. 平台登录：
- challenge + delegation + identity triad 本地验签

详细流程见：
- `rare-identity-core/docs/rip-0005-platform-onboarding-and-events.md`
- `rare-agent-sdk-python/README.md`
- `rare-platform-kit-ts/QUICKSTART.md`

## 3. 关键 API（Rare Core）

### 身份与签名
- `POST /v1/agents/self_register`
- `POST /v1/agents/set_name`
- `POST /v1/attestations/public/issue`
- `POST /v1/attestations/full/issue`
- `POST /v1/signer/prepare_auth`
- `POST /v1/signer/sign_action`
- `POST /v1/signer/sign_full_attestation_issue`

### 升级流程（Agent 请求人类）
- `POST /v1/signer/sign_upgrade_request`
- `POST /v1/upgrades/requests`
- `GET /v1/upgrades/requests/{upgrade_request_id}`
- `POST /v1/upgrades/l1/email/send-link`
- `POST /v1/upgrades/l1/email/verify`
- `POST /v1/upgrades/l2/social/start`
- `GET /v1/upgrades/l2/social/callback`
- `POST /v1/upgrades/l2/social/complete`

### 平台注册与治理
- `POST /v1/platforms/register/challenge`
- `POST /v1/platforms/register/complete`
- `POST /v1/identity-library/events/ingest`
- `GET /.well-known/rare-keys.json`

## 4. 签名串（固定格式）
- 登录 challenge：`rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`
- 改名：`rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`
- 注册：`rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`
- full 签发：`rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- 升级请求：`rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}`
- 动作签名：`rare-act-v1:{aud}:{session_token}:{action}:{sha256(payload)}:{nonce}:{issued_at}:{expires_at}`

## 5. 文档索引（建议阅读顺序）
1. `rare-identity-core/docs/rip-0001-identity-attestation.md`
2. `rare-identity-core/docs/rip-0002-delegation.md`
3. `rare-identity-core/docs/rip-0003-challenge-auth.md`
4. `rare-identity-core/docs/rip-0005-platform-onboarding-and-events.md`
5. `rare-agent-sdk-python/README.md`
6. `rare-platform-kit-ts/QUICKSTART.md`
7. `rare-platform-kit-ts/FULL_MODE_GUIDE.md`
8. `rare-platform-kit-ts/EVENTS_GUIDE.md`

## 6. 开发与回归
```bash
./scripts/test_all.sh
```

当前基线：
- `rare-identity-protocol-python`：共享协议包
- `rare-identity-verifier-python`：共享 verifier 包
- `rare-identity-core`：Core API 服务
- `rare-agent-sdk-python`：Agent SDK + CLI + local signer
- `rare-platform-kit-ts`：TypeScript 平台适配 SDK（Rare Platform Kit）
