#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_PYTHONPATH="${ROOT_DIR}/packages/shared/python/rare-identity-protocol-python/src:${ROOT_DIR}/packages/shared/python/rare-identity-verifier-python/src:${ROOT_DIR}/services/rare-identity-core/services:${ROOT_DIR}/packages/agent/python/rare-agent-sdk-python/src"
WORKSPACE_PYTHONPATH="${WORKSPACE_PYTHONPATH}:${ROOT_DIR}/packages/platform/python/rare-platform-sdk-python/src"

python3 "${ROOT_DIR}/scripts/check_repo_hygiene.py"

(
  cd packages/shared/python/rare-identity-protocol-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" pytest -q
)
(
  cd packages/shared/python/rare-identity-verifier-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" pytest -q
)
(
  cd services/rare-identity-core
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" pytest -q
)
(
  cd packages/agent/python/rare-agent-sdk-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" pytest -q
)
(
  cd packages/platform/python/rare-platform-sdk-python
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" pytest -q
)

if [[ -d packages/platform/ts/rare-platform-kit-ts ]] && command -v pnpm >/dev/null 2>&1; then
  (
    cd packages/platform/ts/rare-platform-kit-ts
    pnpm -r build
    pnpm -r test
  )
fi
