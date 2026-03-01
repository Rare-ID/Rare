#!/usr/bin/env bash
set -euo pipefail

(
  cd rare-identity-core
  pytest -q
)
(
  cd rare-thirdparty-moltbook-example
  pytest -q
)
(
  cd rare-sdk-python
  pytest -q
)
