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

audit_python_lock() {
  local requirements_file="$1"
  local attempt
  local filtered_requirements=""

  echo "==> pip-audit: ${requirements_file}"
  if grep -Eq '^rare-(identity-protocol|identity-verifier|identity-core|agent-sdk|platform-sdk)([<>=!~ ].*)?$' "$requirements_file"; then
    filtered_requirements="$(mktemp)"
    grep -Ev '^rare-(identity-protocol|identity-verifier|identity-core|agent-sdk|platform-sdk)([<>=!~ ].*)?$' "$requirements_file" > "$filtered_requirements"
  fi
  for attempt in 1 2 3; do
    if "$PYTHON_BIN" -m pip_audit --progress-spinner off -r "${filtered_requirements:-$requirements_file}"; then
      if [[ -n "$filtered_requirements" ]]; then
        rm -f "$filtered_requirements"
      fi
      return 0
    fi
    if [[ "$attempt" -lt 3 ]]; then
      echo "pip-audit failed for ${requirements_file} on attempt ${attempt}; retrying..." >&2
      sleep "$attempt"
    fi
  done

  if [[ -n "$filtered_requirements" ]]; then
    rm -f "$filtered_requirements"
  fi
  echo "pip-audit failed for ${requirements_file} after 3 attempts" >&2
  return 1
}

audit_python_lock packages/shared/python/rare-identity-protocol-python/requirements.lock
audit_python_lock packages/shared/python/rare-identity-protocol-python/requirements-test.lock
audit_python_lock packages/shared/python/rare-identity-verifier-python/requirements.lock
audit_python_lock packages/shared/python/rare-identity-verifier-python/requirements-test.lock
audit_python_lock services/rare-identity-core/requirements.lock
audit_python_lock services/rare-identity-core/requirements-test.lock
audit_python_lock packages/agent/python/rare-agent-sdk-python/requirements.lock
audit_python_lock packages/agent/python/rare-agent-sdk-python/requirements-test.lock
audit_python_lock packages/platform/python/rare-platform-sdk-python/requirements.lock
audit_python_lock packages/platform/python/rare-platform-sdk-python/requirements-test.lock

if [[ -d packages/platform/ts/rare-platform-kit-ts ]] && command -v pnpm >/dev/null 2>&1; then
  (
    cd packages/platform/ts/rare-platform-kit-ts
    echo "==> pnpm audit: packages/platform/ts/rare-platform-kit-ts"
    pnpm config set registry https://registry.npmjs.org
    pnpm audit --prod --audit-level=high
  )
fi
