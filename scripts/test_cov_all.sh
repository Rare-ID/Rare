#!/usr/bin/env bash
set -euo pipefail

(
  cd rare-identity-core
  python -m pytest -q --cov=libs/rare_identity_protocol --cov-report=term-missing --cov-fail-under=95
  python -m pytest -q --cov=libs/rare_identity_verifier --cov-report=term-missing --cov-fail-under=95
  python -m pytest -q --cov=services/rare_api --cov-report=term-missing --cov-fail-under=85
)

(
  cd rare-sdk-python
  python -m pytest -q --cov=src/rare_sdk --cov-report=term-missing --cov-fail-under=85
)

(
  cd rare-thirdparty-moltbook-example
  python -m pytest -q --cov=apps/moltbook_api --cov-report=term-missing --cov-fail-under=90
)
