# Release Guide

The main Rare repository is `https://github.com/Rare-ID/Rare`.

Repository boundaries for release metadata:

- Python protocol, verifier, core, Agent CLI, and platform SDK packages point to `Rare-ID/Rare`
- TypeScript Platform SDK packages also point to `Rare-ID/Rare`

## Before Releasing

1. Update the package version(s) you intend to publish.
2. Run:

```bash
python scripts/validate_rip_docs.py --strict
python scripts/check_repo_hygiene.py
./scripts/test_all.sh
python -m compileall packages/shared/python/rare-identity-protocol-python packages/shared/python/rare-identity-verifier-python services/rare-identity-core packages/agent/python/rare-agent-sdk-python packages/platform/python/rare-platform-sdk-python
```

3. If you changed the TypeScript platform kit, also run:

```bash
(cd packages/platform/ts/rare-platform-kit-ts && pnpm -r build && pnpm -r test)
```

## Python Packages

Packages in this repo:

- `rare-identity-protocol`
- `rare-identity-verifier`
- `rare-identity-core`
- `rare-agent-sdk` (CLI package; historical name retained)
- `rare-platform-sdk`

Build locally:

```bash
python -m pip install -U build twine
(cd packages/shared/python/rare-identity-protocol-python && python -m build)
(cd packages/shared/python/rare-identity-verifier-python && python -m build)
(cd services/rare-identity-core && python -m build)
(cd packages/agent/python/rare-agent-sdk-python && python -m build)
(cd packages/platform/python/rare-platform-sdk-python && python -m build)
python -m twine check packages/shared/python/rare-identity-protocol-python/dist/*
python -m twine check packages/shared/python/rare-identity-verifier-python/dist/*
python -m twine check services/rare-identity-core/dist/*
python -m twine check packages/agent/python/rare-agent-sdk-python/dist/*
python -m twine check packages/platform/python/rare-platform-sdk-python/dist/*
```

CI workflow:

- `.github/workflows/publish-python-packages.yml`

Usage:

- automatic publish on `main` targets `rare-agent-sdk` and `rare-platform-sdk`
- manual `workflow_dispatch` may be used for the Python packages you choose to publish from this repo
- `rare-agent-sdk` is the primary public PyPI package; `rare-identity-protocol` stays in-repo and is not a normal release target
- `rare-platform-sdk` is the primary public PyPI package for Python platform integrations
- `rare-identity-verifier` and `rare-identity-core` are optional Python distributions for backend or self-hosted service use

## TypeScript Platform Packages

Packages live under `packages/platform/ts/rare-platform-kit-ts/packages/*`.

Build and test locally:

```bash
(cd packages/platform/ts/rare-platform-kit-ts && pnpm install --frozen-lockfile)
(cd packages/platform/ts/rare-platform-kit-ts && pnpm -r build)
(cd packages/platform/ts/rare-platform-kit-ts && pnpm -r lint)
(cd packages/platform/ts/rare-platform-kit-ts && pnpm -r typecheck)
(cd packages/platform/ts/rare-platform-kit-ts && pnpm -r test)
```

CI workflow:

- `.github/workflows/publish-platform-kit-ts.yml`

Usage:

- automatic publish runs from `main`
- manual `workflow_dispatch` is available when you want to build and publish deliberately

## Notes

- Rare Core service deploys are manual via `.github/workflows/deploy-rare-core.yml`.
- The current GitHub deploy workflow is wired for production only; do not assume a separate staging service exists unless staging-specific GCP resources and GitHub environment configuration are added.
- If a release changes protocol behavior, update the relevant RIP docs and tests in the same change.
