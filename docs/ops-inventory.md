# Rare Ops Inventory

这份文档记录当前 Rare 工作区、发布链路和线上基础设施的实际状态，避免后续操作时依赖聊天记录。

## GitHub Repositories

- 个人 fork：`Rare-Sid/Rare`
  - 本地 git remote：`origin`
  - 用途：个人开发分支
- 运营主仓：`Rare-Sors/Rare`
  - 本地 git remote：`work`
  - 用途：线上发布、GitHub Actions、GCP deploy、PyPI/npm 发布
  - 自动发布和自动部署应以这个仓库的 `main` 分支为准

## Repository Layout

- `services/rare-identity-core/`
  - Rare Core API 服务代码
  - 关键部署文件：`services/rare-identity-core/Dockerfile`
- `packages/python/rare-identity-protocol-python/`
  - Python 协议包
- `packages/python/rare-identity-verifier-python/`
  - Python verifier 包
- `packages/python/rare-agent-sdk-python/`
  - Python Agent SDK 与 CLI
- `packages/ts/rare-platform-kit-ts/`
  - TypeScript 平台 SDK monorepo
- `infra/gcp/terraform/`
  - GCP Terraform 资产
- `docs/deployment-gcp.md`
  - GCP 部署说明
- `docs/sdk-release.md`
  - SDK 发布说明
- `docs/oss-split-plan.md`
  - 公开仓/私有仓拆分建议
- `docs/release-sop.md`
  - 正式发布 SOP
- `open-source/`
  - 公开仓 README / CI / release workflow 模板
- `skills/rare-agent/`
  - Rare Agent canonical skill（curl-first）
- `FOR_PLATFORM.md`
  - Platform 接入说明

## GitHub Workflows

- `.github/workflows/tests.yml`
  - Python 工作区测试
- `.github/workflows/platform-kit-ts.yml`
  - TypeScript build/test
- `.github/workflows/deploy-rare-core.yml`
  - `main` 分支更新 `services/rare-identity-core/**` 后自动部署到 `staging`
  - 支持手动 `workflow_dispatch` 到 `staging` 或 `prod`
- `.github/workflows/publish-python-packages.yml`
  - 现在支持两种触发方式：
    - 手动发布到 `testpypi` 或 `pypi`
    - `main` 分支更新 `packages/python/rare-identity-protocol-python/**` 或 `packages/python/rare-agent-sdk-python/**` 后自动发布到 PyPI
  - 自动发布范围当前只包含：
    - `rare-identity-protocol`
    - `rare-agent-sdk`
- `.github/workflows/publish-platform-kit-ts.yml`
  - 现在支持两种触发方式：
    - 手动发布
    - `main` 分支更新 `packages/ts/rare-platform-kit-ts/**` 后自动发布 npm 包
- `.github/workflows/sync-public-oss.yml`
  - `main` 分支更新公开相关目录后，自动同步到 `Rare-ID` 组织下的公开仓
  - 需要 secret：`OSS_SYNC_TOKEN`

## GitHub Secrets And Environments

- Repository secrets
  - `NPM_TOKEN`
  - `OSS_SYNC_TOKEN`
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_SERVICE_ACCOUNT_EMAIL`
- Repository variables
  - `GCP_PROJECT_ID`
  - `GCP_REGION`
  - `CLOUD_RUN_SERVICE`
  - `ARTIFACT_REGISTRY_REPOSITORY`
- GitHub environments
  - `staging`
  - `prod`
  - `pypi-rare-identity-protocol`
  - `pypi-rare-agent-sdk`
  - 预留但当前未启用自动发布：
    - `pypi-rare-identity-verifier`
    - `pypi-rare-identity-core`

## Published Packages

- PyPI
  - `rare-identity-protocol==0.1.0`
  - `rare-agent-sdk==0.1.0`
- npm
  - `@rare-id/platform-kit-client@0.1.0`
  - `@rare-id/platform-kit-core@0.1.0`
  - `@rare-id/platform-kit-web@0.1.0`
  - `@rare-id/platform-kit-express@0.1.0`
  - `@rare-id/platform-kit-fastify@0.1.0`
  - `@rare-id/platform-kit-nest@0.1.0`
  - `@rare-id/platform-kit-redis@0.1.0`

## GCP

- GCP project: `rare-489504`
- Region: `us-central1`
- Cloud Run service
  - Name: `rare-core-api`
  - Region: `us-central1`
  - Service URL: `https://rare-core-api-621182855536.us-central1.run.app`
- External HTTPS Load Balancer
  - Forwarding rule: `rare-core-api-prod-https`
  - Public IP: `136.110.131.55`
- Active public domain
  - `https://api.rareid.cc`
- Health endpoint
  - `GET https://api.rareid.cc/healthz`
- Current health response
  - `{"status":"ok","issuer":"rare","public_base_url":"https://api.rareid.cc","enabled_social_providers":["github"]}`

## GCP Certificates

- Active
  - `rare-core-api-prod-cert-rareid`
  - Domain: `api.rareid.cc`
- Stale / cleanup candidate
  - `rare-core-api-prod-cert`
  - Domain: `api.rare.cc`
  - Status: `FAILED_NOT_VISIBLE`

## GCP Secret Manager

- `rare-core-api-prod-admin-token`
- `rare-core-api-prod-github-client-id`
- `rare-core-api-prod-github-client-secret`
- `rare-core-api-prod-keyring`
- `rare-core-api-prod-postgres-dsn`
- `rare-core-api-prod-redis-url`
- `rare-core-api-prod-sendgrid-api-key`

## GCP KMS

- Key ring
  - `projects/rare-489504/locations/us-central1/keyRings/rare-core-api-prod-keyring`

## DNS / Cloudflare

- Zone: `rareid.cc`
- Nameservers
  - `melinda.ns.cloudflare.com`
  - `randall.ns.cloudflare.com`
- App domain
  - `api.rareid.cc`
- Important note
  - 当前 `api.rareid.cc` 的公开解析值是 `198.18.0.13`
  - 这表示域名当前经过 Cloudflare 代理
  - GCP 真实负载均衡 IP 仍然是 `136.110.131.55`
  - 如果要绕过 Cloudflare，需把 `api` 的 `A` 记录切回 `DNS only -> 136.110.131.55`

## Auto Release Rules

- 自动发布只会在 `Rare-Sors/Rare` 的 `main` 分支发生
- 仍然需要显式更新包版本号
  - Python：若版本未变化，PyPI publish 会 `skip-existing`
  - npm：若版本未变化，`pnpm publish` 会直接 no-op
- 当前自动发布覆盖范围
  - Python：`rare-identity-protocol`、`rare-agent-sdk`
  - npm：全部 `@rare-id/platform-kit-*`
- 当前未自动发布
  - `rare-identity-verifier`
  - `rare-identity-core`
  - 如果未来要公开发布它们，需要补：
    - PyPI 项目
    - 对应 trusted publisher environment

## Recommended Operating Flow

1. 在 `Rare-Sors/Rare` 修改代码
2. 更新对应包的版本号
3. 合并到 `main`
4. GitHub Actions 自动同步到 `Rare-ID` 公开仓，或自动部署 Rare Core
5. 在对应公开仓创建 GitHub Release，触发独立发布
6. 发布后验证：
   - `npm dist-tag ls @rare-id/<package>`
   - `python -m pip index versions rare-agent-sdk`
   - `curl https://api.rareid.cc/healthz`
