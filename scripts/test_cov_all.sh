#!/usr/bin/env bash
set -euo pipefail

(
  cd rare-identity-protocol-python
  python -m pytest -q tests --cov=src/rare_identity_protocol --cov-report=term-missing --cov-fail-under=95
)

(
  cd rare-identity-verifier-python
  python -m pytest -q tests --cov=src/rare_identity_verifier --cov-report=term-missing --cov-fail-under=95
)

(
  cd rare-identity-core
  python -m pytest -q tests/test_core.py --cov=services/rare_api --cov-report=term-missing --cov-fail-under=85
)

(
  cd rare-agent-sdk-python
  python -m pytest -q --cov=src/rare_agent_sdk --cov-report=term-missing --cov-fail-under=85
)

if [[ -d rare-platform-kit-ts ]] && command -v pnpm >/dev/null 2>&1; then
  (
    cd rare-platform-kit-ts
    pnpm -r build
    pnpm -r test
  )
fi
