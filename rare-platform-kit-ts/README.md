# Rare Platform Kit (TypeScript)

TypeScript monorepo for third-party platforms integrating Rare with local verification-first defaults.

## Packages

- `@rare-id/platform-kit-core`
- `@rare-id/platform-kit-client`
- `@rare-id/platform-kit-web`
- `@rare-id/platform-kit-redis`
- `@rare-id/platform-kit-express`
- `@rare-id/platform-kit-fastify`
- `@rare-id/platform-kit-nest`

## Quick Start Docs

- `QUICKSTART.md`
- `FULL_MODE_GUIDE.md`
- `EVENTS_GUIDE.md`

## Install

```bash
pnpm install
pnpm -r build
pnpm -r test
```

## Development

```bash
pnpm -r lint
pnpm -r typecheck
```

## Notes

- 所有适配包已包含最小契约测试，`pnpm -r test` 会真实执行并对失败返回非零退出码。
- 生产集成前建议阅读：
  - `../rare-identity-core/docs/rip-0005-platform-onboarding-and-events.md`
  - `./QUICKSTART.md`
  - `./FULL_MODE_GUIDE.md`
