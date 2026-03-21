#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python3"
  fi
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("audit_deps.sh requires Python 3.11+ (set PYTHON_BIN to a compatible interpreter)")
PY

"$PYTHON_BIN" -m pip install -q pip-audit

"$PYTHON_BIN" -m pip_audit -r packages/shared/python/rare-identity-protocol-python/requirements.lock
"$PYTHON_BIN" -m pip_audit -r packages/shared/python/rare-identity-protocol-python/requirements-test.lock
"$PYTHON_BIN" -m pip_audit -r packages/shared/python/rare-identity-verifier-python/requirements.lock
"$PYTHON_BIN" -m pip_audit -r packages/shared/python/rare-identity-verifier-python/requirements-test.lock
"$PYTHON_BIN" -m pip_audit -r services/rare-identity-core/requirements.lock
"$PYTHON_BIN" -m pip_audit -r services/rare-identity-core/requirements-test.lock
"$PYTHON_BIN" -m pip_audit -r packages/agent/python/rare-agent-sdk-python/requirements.lock
"$PYTHON_BIN" -m pip_audit -r packages/agent/python/rare-agent-sdk-python/requirements-test.lock
"$PYTHON_BIN" -m pip_audit -r packages/platform/python/rare-platform-sdk-python/requirements.lock
"$PYTHON_BIN" -m pip_audit -r packages/platform/python/rare-platform-sdk-python/requirements-test.lock

if [[ -d packages/platform/ts/rare-platform-kit-ts ]] && command -v pnpm >/dev/null 2>&1; then
  (
    cd packages/platform/ts/rare-platform-kit-ts
    pnpm config set registry https://registry.npmjs.org
    pnpm audit --prod --audit-level=high
  )
fi
