# AGENTS.md

## Overview

Rare is an identity and trust layer for AI agents.

Core ideas:

- `agent_id` is always the Ed25519 public key
- Rare issues trust attestations such as `L0`, `L1`, and `L2`
- platforms authenticate delegated session keys, not the long-term key directly
- replay protection and fixed signing inputs are protocol requirements

This repository is the canonical public monorepo for Rare.

Current production API:

- `https://api.rareid.cc`

Main workspace packages:

- `packages/python/rare-identity-protocol-python`
- `packages/python/rare-identity-verifier-python`
- `services/rare-identity-core`
- `packages/python/rare-agent-sdk-python`
- `packages/ts/rare-platform-kit-ts`

## Common Commands

Set up the Python workspace:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r ./packages/python/rare-identity-protocol-python/requirements-test.lock
pip install -r ./packages/python/rare-identity-verifier-python/requirements-test.lock
pip install -e "./packages/python/rare-identity-protocol-python[test]"
pip install -e "./packages/python/rare-identity-verifier-python[test]"
pip install -r ./services/rare-identity-core/requirements-test.lock
pip install -r ./packages/python/rare-agent-sdk-python/requirements-test.lock
pip install -e "./services/rare-identity-core[test]"
pip install -e "./packages/python/rare-agent-sdk-python[test]"
```

Run the full test suite:

```bash
./scripts/test_all.sh
```

Run core service locally:

```bash
cd services/rare-identity-core
uvicorn rare_api.main:app --reload --host 127.0.0.1 --port 8000
```

Build packages:

```bash
(cd packages/python/rare-identity-protocol-python && python -m build)
(cd packages/python/rare-identity-verifier-python && python -m build)
(cd services/rare-identity-core && python -m build)
(cd packages/python/rare-agent-sdk-python && python -m build)
(cd packages/ts/rare-platform-kit-ts && pnpm -r build)
```

## Agent CLI

Common commands:

```bash
rare register --name alice
rare request-upgrade --level L1 --email alice@example.com
rare request-upgrade --level L2
rare issue-full-attestation --aud platform
rare login --aud platform --platform-url http://127.0.0.1:8000/platform
rare login --aud platform --public-only
rare set-name --name alice-v2
rare refresh-attestation
rare show-state
```

## Protocol Red Lines

Do not change these casually.

- auth challenge signing input:
  `rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`
- name update signing input:
  `rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`
- full attestation signing input:
  `rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- upgrade request signing input:
  `rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}`

Required rules:

- `name` uses `trim + NFKC`, length `1..48`, no control characters, reserved-word checks
- platform auth must enforce triad consistency:
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`
- identity token `typ` only allows:
  - `rare.identity.public+jws`
  - `rare.identity.full+jws`
- delegation token `typ` is always `rare.delegation+jws`
- verifier must ignore unknown claims for forward compatibility

## Testing Expectations

At minimum, changes touching auth flows should preserve coverage for:

- nonce one-time use and replay rejection
- delegation `aud` / `scope` / `exp`
- identity attestation `kid` / `typ` / `lvl` / `aud` / `exp`
- identity triad consistency
- `set_name` signature, replay protection, and rate limiting
- L1/L2 upgrade flow signing and replay protection

Useful commands:

```bash
python scripts/validate_rip_docs.py --strict
python scripts/check_repo_hygiene.py
python -m compileall packages/python/rare-identity-protocol-python packages/python/rare-identity-verifier-python services/rare-identity-core packages/python/rare-agent-sdk-python
```

## Release Notes

- Source code lives in `Rare-ID/Rare`
- npm packages remain the main public install surface for the platform SDK
- `rare-agent-sdk` is the main public PyPI package for agents
- `rare-identity-verifier` and `rare-identity-core` are optional manual-release Python packages
- release process lives in `docs/release-guide.md`
