# Release Guide

The main Rare repository is `https://github.com/Rare-ID/Rare`.

Repository boundaries for release metadata:

- Python protocol, verifier, core, and Agent CLI packages point to `Rare-ID/Rare`
- TypeScript Platform SDK packages also point to `Rare-ID/Rare`

## Before Releasing

1. Update the package version(s) you intend to publish.
2. Run:

```bash
python scripts/validate_rip_docs.py --strict
python scripts/check_repo_hygiene.py
./scripts/test_all.sh
python -m compileall packages/python/rare-identity-protocol-python packages/python/rare-identity-verifier-python services/rare-identity-core packages/python/rare-agent-sdk-python
```

3. If you changed the TypeScript platform kit, also run:

```bash
(cd packages/ts/rare-platform-kit-ts && pnpm -r build && pnpm -r test)
```

## Python Packages

Packages in this repo:

- `rare-identity-protocol`
- `rare-identity-verifier`
- `rare-identity-core`
- `rare-agent-sdk` (CLI package; historical name retained)

Build locally:

```bash
python -m pip install -U build twine
(cd packages/python/rare-identity-protocol-python && python -m build)
(cd packages/python/rare-identity-verifier-python && python -m build)
(cd services/rare-identity-core && python -m build)
(cd packages/python/rare-agent-sdk-python && python -m build)
python -m twine check packages/python/rare-identity-protocol-python/dist/*
python -m twine check packages/python/rare-identity-verifier-python/dist/*
python -m twine check services/rare-identity-core/dist/*
python -m twine check packages/python/rare-agent-sdk-python/dist/*
```

CI workflow:

- `.github/workflows/publish-python-packages.yml`

Usage:

- automatic publish on `main` only targets `rare-agent-sdk`
- manual `workflow_dispatch` can publish `rare-agent-sdk`, `rare-identity-verifier`, or `rare-identity-core`
- `rare-agent-sdk` is the primary public PyPI package; `rare-identity-protocol` stays in-repo and is not a normal release target
- `rare-identity-verifier` and `rare-identity-core` are optional Python distributions for backend or self-hosted service use

## TypeScript Platform Packages

Packages live under `packages/ts/rare-platform-kit-ts/packages/*`.

Build and test locally:

```bash
(cd packages/ts/rare-platform-kit-ts && pnpm install --frozen-lockfile)
(cd packages/ts/rare-platform-kit-ts && pnpm -r build)
(cd packages/ts/rare-platform-kit-ts && pnpm -r lint)
(cd packages/ts/rare-platform-kit-ts && pnpm -r typecheck)
(cd packages/ts/rare-platform-kit-ts && pnpm -r test)
```

CI workflow:

- `.github/workflows/publish-platform-kit-ts.yml`

Usage:

- automatic publish runs from `main`
- manual `workflow_dispatch` is available when you want to build and publish deliberately

## Notes

- Keep deploy infrastructure and hosted-service operations outside this public repo.
- If a release changes protocol behavior, update the relevant RIP docs and tests in the same change.
