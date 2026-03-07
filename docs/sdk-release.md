# SDK Release Guide

Rare 的 SDK 不需要部署到 GCP 运行时。对外上线的最短路径是：

- Python shared packages: 发布 `rare-identity-protocol` 与 `rare-identity-verifier`
- Python: 发布 `rare-identity-core` 与 `rare-agent-sdk` 到 PyPI
- TypeScript: 发布 `@rare-id/platform-kit-*` 到 npmjs

## Workflows

- Python packages: `.github/workflows/publish-python-packages.yml`
- TypeScript packages: `.github/workflows/publish-platform-kit-ts.yml`

## Python publish prerequisites

- PyPI 或 TestPyPI 上创建项目：
  - `rare-identity-protocol`
  - `rare-identity-verifier`
  - `rare-identity-core`
  - `rare-agent-sdk`
- 为对应仓库配置 Trusted Publishing
- 首次建议先跑 `repository=testpypi` 且 `publish=false`

## npm publish prerequisites

- 你拥有 npm scope `@rare-id`，或把各包名改成你控制的 scope
- 在 GitHub repository secrets 中设置 `NPM_TOKEN`
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
