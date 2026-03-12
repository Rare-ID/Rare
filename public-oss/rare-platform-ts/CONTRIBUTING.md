# Contributing

## Scope

This repository is the public TypeScript platform integration kit for Rare.

Out of scope:

- private Rare backend implementation
- infrastructure and deployment details
- internal hosted signer service implementation
- secrets, private keys, or production credentials

## Before You Start

- Open an issue for public API changes, framework adapters, or verification behavior changes.
- Keep platform behavior aligned with the public Rare protocol rules.
- If you change verification behavior, update tests and the user-facing guides in the same pull request.

## Development

```bash
pnpm install
pnpm -r build
pnpm -r lint
pnpm -r typecheck
pnpm -r test
```

## Pull Requests

- Add tests for platform behavior changes.
- Call out any breaking package changes explicitly.
- Keep examples and guide docs in sync with public API changes.
