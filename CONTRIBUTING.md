# Contributing

Thanks for contributing to Rare.

## Before You Start

- Open an issue or discussion for non-trivial changes.
- Keep protocol and security changes narrowly scoped and explicitly justified.
- Do not include secrets, private keys, session tokens, or production-only operating material in commits.

## Development Workflow

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r ./packages/shared/python/rare-identity-protocol-python/requirements-test.lock
pip install -r ./packages/shared/python/rare-identity-verifier-python/requirements-test.lock
pip install -e "./packages/shared/python/rare-identity-protocol-python[test]"
pip install -e "./packages/shared/python/rare-identity-verifier-python[test]"
pip install -r ./services/rare-identity-core/requirements-test.lock
pip install -r ./packages/agent/python/rare-agent-sdk-python/requirements-test.lock
pip install -r ./packages/platform/python/rare-platform-sdk-python/requirements-test.lock
pip install -e "./services/rare-identity-core[test]"
pip install -e "./packages/agent/python/rare-agent-sdk-python[test]"
pip install -e "./packages/platform/python/rare-platform-sdk-python[test]"
```

Run the standard checks before opening a PR:

```bash
python scripts/validate_rip_docs.py --strict
python scripts/check_repo_hygiene.py
./scripts/test_all.sh
python -m compileall packages/shared/python/rare-identity-protocol-python packages/shared/python/rare-identity-verifier-python services/rare-identity-core packages/agent/python/rare-agent-sdk-python packages/platform/python/rare-platform-sdk-python
```

If you touch the TypeScript platform kit, also run:

```bash
(cd packages/platform/ts/rare-platform-kit-ts && pnpm -r build && pnpm -r test)
```

## Protocol Changes

- Keep fixed signing inputs stable unless a new versioned prefix is introduced.
- Update the relevant RIP documents when protocol behavior changes.
- Add or update tests for any auth, delegation, attestation, replay, or upgrade flow changes.

## Pull Requests

- Prefer small PRs with a clear behavioral goal.
- Explain user-visible changes and compatibility impact.
- Call out any new protocol assumptions, migrations, or rollout constraints.
