# Rare OSS Split Plan

目标：公开协议、SDK 和平台接入能力，但不公开 Rare 内部服务实现、托管签名、基础设施和运营细节。

## Recommended Boundary

适合开源：

- 协议定义与公开文档
- 纯客户端 SDK
- 平台接入 SDK
- 示例代码、集成指南、测试向量

不适合开源：

- `services/rare-identity-core/services/rare_api/**`
- 托管 signer、生产 wiring、Secret Manager/KMS/SendGrid/GitHub OAuth 的服务端实现细节
- `infra/gcp/**`
- `.github/workflows/deploy-rare-core.yml`
- `docs/ops-inventory.md`
- 任何环境、域名、密钥命名、运维流程、回滚/告警细节

## Existing Rare-ID Repositories

当前 `Rare-ID` 组织已经有可直接利用的公开仓：

- `Rare-ID/rare-protocol-py`
  - 适合作为 Python 协议层公开仓
  - 当前 README 已说明包含：
    - `rare_identity_protocol`
    - `rare_identity_verifier`
    - RIP docs
    - tests
- `Rare-ID/rare-agent-python`
  - 适合作为 Agent SDK 公开仓
- `Rare-ID/rare-platform-ts`
  - 适合作为 TypeScript Platform Kit 公开仓

当前 `Rare-ID` 组织的私有仓：

- `Rare-ID/Rare-Identity-Core`
  - 适合作为内部服务实现仓
- `Rare-ID/LandingPage`
  - 官网/站点仓，与协议和 SDK 拆分无冲突

## Recommended Target Topology

### Public Repositories

- `Rare-ID/rare-protocol-py`
  - 对外发布：
    - `rare-identity-protocol`
    - `rare-identity-verifier`
  - 对外内容：
    - `src/rare_identity_protocol`
    - `src/rare_identity_verifier`
    - RIP 文档
    - 协议测试与向量

- `Rare-ID/rare-agent-python`
  - 对外发布：
    - `rare-agent-sdk`
  - 对外内容：
    - SDK
    - CLI
    - 面向公开 API 的示例
    - hosted-signer / self-hosted 接入文档

- `Rare-ID/rare-platform-ts`
  - 对外发布：
    - `@rare-id/platform-kit-*`
  - 对外内容：
    - packages/*
    - QUICKSTART / FULL_MODE_GUIDE / EVENTS_GUIDE
    - examples

### Private Repositories

- `Rare-ID/Rare-Identity-Core`
  - 保留：
    - `rare-identity-core`
    - 部署配置
    - 生产 secrets / infra / ops docs
    - 服务端集成与内部测试

## Best Practice For Your Constraint

如果你“不想公开内部实现方式”，最合适的模式不是把当前私有工作区直接公开，而是：

1. 把公开能力的 source of truth 放到 `Rare-ID` 的公开仓
2. 私有仓只保留服务端实现与部署
3. PyPI/npm 的发布动作最终从公开仓触发，而不是长期由私有仓代发

原因：

- 用户能看到自己安装包对应的真实源码
- 开源仓的 issue/PR/版本记录更干净
- 私有仓不需要暴露服务端实现、部署和运维历史
- 法务和对外叙事更清晰：公开的是协议与 SDK，不是 Rare 的内部后端

## Immediate Recommendation

### Phase 1: Keep Current Private Ops Repo

短期内继续保留当前私有运营仓作为发布和部署控制面：

- `Rare-Sors/Rare`
  - 继续负责：
    - GCP deploy
    - 当前自动 PyPI/npm 发布
    - 内部工作区开发

这样不需要立即搬迁 secrets、trusted publisher、GCP workflow。

同时可以启用“私有仓 -> 公开仓”的自动同步：

- 私有主仓：`Rare-Sors/Rare`
- 公开目标仓：
  - `Rare-ID/rare-protocol-py`
  - `Rare-ID/rare-agent-python`
  - `Rare-ID/rare-platform-ts`
- 同步方式：
  - 只同步白名单目录和公开文档
  - 不同步 `rare-identity-core` 服务实现
  - 不同步 `infra/gcp`、ops 文档、部署 workflow

仓库内对应资产：

- workflow: `.github/workflows/sync-public-oss.yml`
- script: `scripts/sync_public_repos.sh`
- public repo templates:
  - `open-source/public-oss/rare-protocol-py/**`
  - `open-source/public-oss/rare-agent-python/**`
  - `open-source/public-oss/rare-platform-ts/**`

需要的 GitHub secret：

- `OSS_SYNC_TOKEN`
  - 需要对 `Rare-ID` 组织下 3 个公开仓具备 push 权限
  - 推荐使用 fine-grained PAT，只授权：
    - `Rare-ID/rare-protocol-py`
    - `Rare-ID/rare-agent-python`
    - `Rare-ID/rare-platform-ts`

公开仓独立发布还需要各自补配置：

- `Rare-ID/rare-protocol-py`
  - GitHub environment: `pypi`
  - PyPI trusted publisher
- `Rare-ID/rare-agent-python`
  - GitHub environment: `pypi`
  - PyPI trusted publisher
- `Rare-ID/rare-platform-ts`
  - GitHub secret: `NPM_TOKEN`

### Phase 2: Promote Rare-ID Public Repos To Canonical OSS Sources

按仓逐步完成：

1. `rare-protocol-py`
   - 校正 README 和包发布说明
   - 明确它同时发布 protocol 和 verifier
   - 配好独立 CI / PyPI trusted publishing

2. `rare-agent-python`
   - 去掉 README 里对私有 workspace 路径的依赖描述
   - 改成公开安装路径：
     - `pip install rare-agent-sdk`
   - 配好独立 CI / PyPI trusted publishing

3. `rare-platform-ts`
   - 配好独立 CI / npm 发布
   - 保持 `@rare-id/platform-kit-*` 作为唯一公开来源

4. 私有仓只保留：
   - `rare-identity-core`
   - `infra/gcp`
   - 内部 ops docs

## Files To Move By Repository

### Move To `Rare-ID/rare-protocol-py`

- `packages/python/rare-identity-protocol-python/**`
- `packages/python/rare-identity-verifier-python/**`
- `services/rare-identity-core/docs/**` 中与 RIP / protocol / verifier 直接相关的公开文档

### Move To `Rare-ID/rare-agent-python`

- `packages/python/rare-agent-sdk-python/**`
- `skills/rare-agent/` 的公开 skill 内容与 public mirror

### Move To `Rare-ID/rare-platform-ts`

- `packages/ts/rare-platform-kit-ts/**`
- `FOR_PLATFORM.md` 的公开接入部分

### Keep Private

- `services/rare-identity-core/**`
- `infra/**`
- `docs/deployment-gcp.md`
- `docs/ops-inventory.md`
- `.github/workflows/deploy-rare-core.yml`

## Release Ownership Recommendation

最终建议：

- PyPI
  - `rare-identity-protocol` / `rare-identity-verifier` 由 `Rare-ID/rare-protocol-py` 发布
  - `rare-agent-sdk` 由 `Rare-ID/rare-agent-python` 发布
- npm
  - `@rare-id/platform-kit-*` 由 `Rare-ID/rare-platform-ts` 发布
- Private repo
  - 只做 `rare-core-api` 的容器构建和 GCP 部署

## Cleanup Tasks In Current Public Repositories

现有公开仓至少应清理这些问题：

- 删除 `.DS_Store`
- 删除 `.coverage`
- 补仓库 description
- 补 LICENSE / SECURITY / CONTRIBUTING / CODE_OF_CONDUCT
- 补独立 CI
- 补从 tag 或 release 触发的发布流
- 确保 README 不再要求用户依赖私有 `rare-identity-core` workspace

## Suggested Next Step

最稳的执行顺序：

1. 先保留当前私有工作区作为开发主仓
2. 把 `Rare-ID` 三个公开仓整理成真正可独立发布的 OSS 仓
3. 把发布权从私有仓迁到公开仓
4. 最后再决定是否继续保留当前私有工作区，或把它收缩成纯 `Rare-Identity-Core`

## Decision

如果你的目标是：

- “公开协议和 SDK，但绝不公开后端实现”

那最合适的答案就是：

- 直接复用 `Rare-ID/rare-protocol-py`
- 直接复用 `Rare-ID/rare-agent-python`
- 直接复用 `Rare-ID/rare-platform-ts`
- 把 `Rare-ID/Rare-Identity-Core` 或当前私有运营仓保留为私有后端仓

不要把当前大工作区直接转 public。
