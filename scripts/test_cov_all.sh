#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_PYTHONPATH="${ROOT_DIR}/packages/shared/python/rare-identity-protocol-python/src:${ROOT_DIR}/packages/shared/python/rare-identity-verifier-python/src:${ROOT_DIR}/services/rare-identity-core/services:${ROOT_DIR}/packages/agent/python/rare-agent-sdk-python/src"
WORKSPACE_PYTHONPATH="${WORKSPACE_PYTHONPATH}:${ROOT_DIR}/packages/platform/python/rare-platform-sdk-python/src"

(
  cd packages/shared/python/rare-identity-protocol-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q tests --cov=src/rare_identity_protocol --cov-report=term-missing --cov-fail-under=95
)

(
  cd packages/shared/python/rare-identity-verifier-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q tests --cov=src/rare_identity_verifier --cov-report=term-missing --cov-fail-under=95
)

(
  cd services/rare-identity-core
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q tests/test_core.py --cov=services/rare_api --cov-report=term-missing --cov-fail-under=85
)

(
  cd packages/agent/python/rare-agent-sdk-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q --cov=src/rare_agent_sdk --cov-report=term-missing --cov-fail-under=85
)

(
  cd packages/platform/python/rare-platform-sdk-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q --cov=src/rare_platform_sdk --cov-report=term-missing --cov-fail-under=85
)

if [[ -d packages/platform/ts/rare-platform-kit-ts ]] && command -v pnpm >/dev/null 2>&1; then
  (
    cd packages/platform/ts/rare-platform-kit-ts
    pnpm -r build
    pnpm -r test
  )
fi
