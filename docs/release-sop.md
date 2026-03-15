# Rare Release SOP

这份 SOP 只覆盖当前已经验证通过的正式发布路径：

- 私有开发主仓：`Rare-Sors/Rare`
- 公开 OSS 仓：
  - `Rare-ID/rare-protocol-py`
  - `Rare-ID/rare-agent-python`
  - `Rare-ID/rare-platform-ts`
- 线上 API：`https://api.rareid.cc`

## Release Model

日常开发和集成测试在私有主仓完成。

正式对外发布分两步：

1. 合并私有主仓到 `main`
2. 在对应公开仓发 GitHub Release，触发公开仓自己的 `publish.yml`

不要把“同步到公开仓”和“发布到 PyPI/npm”混成一步。先确认同步，再发布。

## What Triggers Automatically

- `Rare-Sors/Rare main`
  - `sync-public-oss.yml`
  - 自动把公开白名单内容同步到 `Rare-ID` 公开仓
- `Rare-ID/*`
  - `ci.yml`
  - `publish.yml`
  - 公开仓发 Release 后，独立发布到 PyPI 或 npm

## Version Bump Rules

每次正式发布前都必须先改版本号，否则发布不会产生新版本。

- Python
  - `packages/python/rare-identity-protocol-python/pyproject.toml`
  - `packages/python/rare-agent-sdk-python/pyproject.toml`
- TypeScript
  - `packages/ts/rare-platform-kit-ts/packages/*/package.json`

如果只发布某一个公开仓，只改那个仓对应的版本号。

## Standard Release Paths

### 1. Python protocol

- 私有源目录：`packages/python/rare-identity-protocol-python/`
- 公开仓：`Rare-ID/rare-protocol-py`
- PyPI 包：
  - `rare-identity-protocol`

步骤：

1. 在私有主仓改版本号和代码
2. 本地运行：
   - `./scripts/test_all.sh`
   - `python -m build`（在 `packages/python/rare-identity-protocol-python/`）
3. 合并到 `Rare-Sors/Rare main`
4. 等 `sync-public-oss` 成功
5. 在 `Rare-ID/rare-protocol-py` 创建 GitHub Release
6. 等公开仓 `publish.yml` 成功

### 2. Python agent SDK

- 私有源目录：`packages/python/rare-agent-sdk-python/`
- 公开仓：`Rare-ID/rare-agent-python`
- PyPI 包：
  - `rare-agent-sdk`

当前已自动化：

1. 私有主仓改版本号和代码
2. 合并到 `Rare-Sors/Rare main`
3. 等 `sync-public-oss` 成功
4. 私有仓 `.github/workflows/release-public-agent-sdk.yml` 会检查 `Rare-ID/rare-agent-python` 当前版本
5. 如果对应 `v<version>` release 不存在，会自动创建公共 release
6. 公共仓 `publish.yml` 自动发布到 PyPI

如果自动化失败，再回退到手动在 `Rare-ID/rare-agent-python` 创建 GitHub Release。

### 3. TypeScript platform kit

- 私有源目录：`packages/ts/rare-platform-kit-ts/`
- 公开仓：`Rare-ID/rare-platform-ts`
- npm 包：
  - `@rare-id/platform-kit-client`
  - `@rare-id/platform-kit-core`
  - `@rare-id/platform-kit-web`
  - `@rare-id/platform-kit-express`
  - `@rare-id/platform-kit-fastify`
  - `@rare-id/platform-kit-nest`
  - `@rare-id/platform-kit-redis`

步骤：

1. 在私有主仓改相关 `package.json` 版本号和代码
2. 本地运行：
   - `(cd packages/ts/rare-platform-kit-ts && pnpm -r build && pnpm -r test)`
3. 合并到 `Rare-Sors/Rare main`
4. 等 `sync-public-oss` 成功
5. 在 `Rare-ID/rare-platform-ts` 创建 GitHub Release
6. 等公开仓 `publish.yml` 成功

## Minimum Verification

每次发版后至少做这些检查：

- 同步是否成功
  - 查看 `Rare-Sors/Rare` 的 `sync-public-oss`
- Python 包
  - `python -m pip index versions rare-identity-protocol`
  - `python -m pip index versions rare-agent-sdk`
- npm 包
  - `npm view @rare-id/platform-kit-client version`
  - `npm view @rare-id/platform-kit-core version`
- 线上 API
  - `curl -fsS https://api.rareid.cc/healthz`

## Fast Failure Checks

常见失败原因优先看这几项：

- 忘了改版本号
- `sync-public-oss` 没跑完就去发公开 Release
- PyPI trusted publisher 或 npm token 失效
- 公共 README / workflow 模板改动没有同步到公开仓

## Rollback

SDK 发布默认按 registry 版本管理回退，不直接删包。

- Python：发一个更高版本修复
- npm：发一个更高版本修复
- API：如有线上问题，按 Cloud Run revision 回滚

## Current Canonical Repositories

- 私有开发与运维：`Rare-Sors/Rare`
- 公开 Python protocol：`Rare-ID/rare-protocol-py`
- 公开 Python agent SDK：`Rare-ID/rare-agent-python`
- 公开 TypeScript platform kit：`Rare-ID/rare-platform-ts`
