set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

workspace_pythonpath := "packages/shared/python/rare-identity-protocol-python/src:packages/shared/python/rare-identity-verifier-python/src:services/rare-identity-core/services:packages/agent/python/rare-agent-sdk-python/src:packages/platform/python/rare-platform-sdk-python/src"

setup:
    python3.11 -m venv .venv
    . .venv/bin/activate && python -m pip install -U pip setuptools wheel
    . .venv/bin/activate && pip install -r ./packages/shared/python/rare-identity-protocol-python/requirements-test.lock
    . .venv/bin/activate && pip install -r ./packages/shared/python/rare-identity-verifier-python/requirements-test.lock
    . .venv/bin/activate && pip install -e "./packages/shared/python/rare-identity-protocol-python[test]"
    . .venv/bin/activate && pip install -e "./packages/shared/python/rare-identity-verifier-python[test]"
    . .venv/bin/activate && pip install -r ./services/rare-identity-core/requirements-test.lock
    . .venv/bin/activate && pip install -r ./packages/agent/python/rare-agent-sdk-python/requirements-test.lock
    . .venv/bin/activate && pip install -r ./packages/platform/python/rare-platform-sdk-python/requirements-test.lock
    . .venv/bin/activate && pip install -e "./services/rare-identity-core[test]"
    . .venv/bin/activate && pip install -e "./packages/agent/python/rare-agent-sdk-python[test]"
    . .venv/bin/activate && pip install -e "./packages/platform/python/rare-platform-sdk-python[test]"

test:
    ./scripts/test_all.sh

security:
    ./scripts/security_check.sh

security-full:
    RARE_SECURITY_FULL=1 ./scripts/security_check.sh

run-core:
    cd services/rare-identity-core && uvicorn rare_api.main:app --reload --host 127.0.0.1 --port 8000

ts:
    cd packages/platform/ts/rare-platform-kit-ts && pnpm -r build && pnpm -r lint && pnpm -r typecheck && pnpm -r test

clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    find . -type d -name .pytest_cache -prune -exec rm -rf {} +
    find . -type f -name '*.pyc' -delete
