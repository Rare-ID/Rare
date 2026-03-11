# SDK Release Guide

Rare 的 SDK 不需要部署到 GCP 运行时。对外上线的最短路径是：

- Python shared packages: 发布 `rare-identity-protocol` 与 `rare-identity-verifier`
- Python: 发布 `rare-identity-core` 与 `rare-agent-sdk` 到 PyPI
- TypeScript: 发布 `@rare-id/platform-kit-*` 到 npmjs

## Workflows

- Python packages: `.github/workflows/publish-python-packages.yml`
- TypeScript packages: `.github/workflows/publish-platform-kit-ts.yml`
- Public SDK release automation: `.github/workflows/release-public-agent-sdk.yml`
- `Rare-Sors/Rare` 的 `main` 分支现在会自动触发：
  - `rare-identity-protocol-python/**` 或 `rare-agent-sdk-python/**` 变更 -> 自动发布对应 PyPI 包
  - `rare-platform-kit-ts/**` 变更 -> 自动发布 `@rare-id/platform-kit-*`
  - `sync-public-oss` 成功后，如果 `Rare-ID/rare-agent-python` 的 `pyproject.toml` 版本号对应的 release tag 尚不存在，会自动创建公共 release 并触发公共仓 `publish.yml`

## Python publish prerequisites

- PyPI 或 TestPyPI 上准备项目：
  - `rare-identity-protocol`
  - `rare-identity-verifier`
  - `rare-identity-core`
  - `rare-agent-sdk`
- PyPI Trusted Publishing 建议按包拆环境，避免同一 workflow 的 OIDC token 被错误绑定到单个项目：
  - `rare-identity-protocol` -> environment `pypi-rare-identity-protocol`
  - `rare-identity-verifier` -> environment `pypi-rare-identity-verifier`
  - `rare-identity-core` -> environment `pypi-rare-identity-core`
  - `rare-agent-sdk` -> environment `pypi-rare-agent-sdk`
- TestPyPI 仍可继续使用统一环境 `testpypi`
- 首次建议先跑 `repository=testpypi` 且 `publish=false`

## npm publish prerequisites

- 你拥有 npm scope `@rare-id`，或把各包名改成你控制的 scope
- 二选一：
  - 在 GitHub repository secrets 中设置可发布的 npm automation token `NPM_TOKEN`
  - 或在 npm 为每个 `@rare-id/platform-kit-*` 包配置 trusted publishing
- 首次建议先手动跑 build job，确认 pack 产物正常

## Suggested release order

1. 发布 `rare-identity-protocol`
2. 发布 `rare-identity-verifier`
3. 发布 `rare-identity-core`
4. 发布 `rare-agent-sdk`
5. 发布 `@rare-id/platform-kit-*`

## Notes

- `rare-identity-core` 运行时依赖 `rare-identity-protocol` 与 `rare-identity-verifier`
- `rare-agent-sdk` 运行时依赖 `rare-identity-protocol`
- TypeScript monorepo 当前使用 workspace 依赖，发布时采用 `pnpm -r publish`
- SDK 现在推荐以公共仓 `Rare-ID/rare-agent-python` 为 PyPI 发布源；私有主仓仍负责开发、测试和同步
