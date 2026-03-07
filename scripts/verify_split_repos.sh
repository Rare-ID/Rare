#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/out/public-repos}"

if [[ ! -d "${OUT_DIR}" ]]; then
  echo "split output not found: ${OUT_DIR}" >&2
  echo "run scripts/split_repos.sh first" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

run_python_repo_checks() {
  local repo="$1"
  (
    cd "${OUT_DIR}/${repo}"
    ${PYTHON_BIN} -m pip install -q -U pip setuptools wheel
    if [[ -f pyproject.toml ]]; then
      ${PYTHON_BIN} -m pip install -q -e ".[test]" --no-deps || ${PYTHON_BIN} -m pip install -q -e . --no-deps
    fi
    ${PYTHON_BIN} -m compileall src tests
    if [[ -d tests ]]; then
      pytest -q
    fi
  )
}

run_ts_repo_checks() {
  (
    cd "${OUT_DIR}/rare-platform-kit-ts"
    pnpm install --frozen-lockfile
    pnpm -r build
    pnpm -r lint
    pnpm -r typecheck
    pnpm -r test
  )
}

run_python_repo_checks "rare-identity-protocol-py"
run_python_repo_checks "rare-agent-sdk-python"

if command -v pnpm >/dev/null 2>&1; then
  run_ts_repo_checks
else
  echo "pnpm not found; skipped rare-platform-kit-ts verification"
fi

echo "split repo verification completed"
