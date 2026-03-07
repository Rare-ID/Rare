#!/usr/bin/env bash
set -euo pipefail

(
  cd rare-identity-protocol-python
  pytest -q
)
(
  cd rare-identity-verifier-python
  pytest -q
)
(
  cd rare-identity-core
  pytest -q
)
(
  cd rare-agent-sdk-python
  pytest -q
)

if [[ -d rare-platform-kit-ts ]] && command -v pnpm >/dev/null 2>&1; then
  (
    cd rare-platform-kit-ts
    pnpm -r build
    pnpm -r test
  )
fi
