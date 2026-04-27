#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_PYTHONPATH="${ROOT_DIR}/packages/shared/python/rare-identity-protocol-python/src:${ROOT_DIR}/packages/shared/python/rare-identity-verifier-python/src:${ROOT_DIR}/services/rare-identity-core/services:${ROOT_DIR}/packages/agent/python/rare-agent-sdk-python/src"
WORKSPACE_PYTHONPATH="${WORKSPACE_PYTHONPATH}:${ROOT_DIR}/packages/platform/python/rare-platform-sdk-python/src"

cd "${ROOT_DIR}"

python scripts/validate_rip_docs.py --strict
python scripts/check_repo_hygiene.py

PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q \
  packages/shared/python/rare-identity-protocol-python/tests/test_vectors.py \
  packages/shared/python/rare-identity-verifier-python/tests/test_verifier_unit.py \
  packages/platform/python/rare-platform-sdk-python/tests/test_kit.py

if [[ "${RARE_SECURITY_FULL:-0}" == "1" ]]; then
  PYTHONPATH="${WORKSPACE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}" python -m pytest -q \
    services/rare-identity-core/tests/test_core.py
fi

if command -v pnpm >/dev/null 2>&1; then
  (
    cd packages/platform/ts/rare-platform-kit-ts
    pnpm --filter @rare-id/platform-kit-core test -- vectors.test.ts
    pnpm --filter @rare-id/platform-kit-web test -- kit.test.ts
  )
else
  echo "pnpm not found; skipped TypeScript security checks" >&2
fi
