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
    raise SystemExit("lock_deps.sh requires Python 3.11+ (set PYTHON_BIN to a compatible interpreter)")
PY

"$PYTHON_BIN" -m pip install -q build pip-tools

WHEELHOUSE="$(mktemp -d)"
cleanup() {
  rm -rf "$WHEELHOUSE"
}
trap cleanup EXIT

for repo in \
  packages/shared/python/rare-identity-protocol-python \
  packages/shared/python/rare-identity-verifier-python
do
  (
    cd "$repo"
    "$PYTHON_BIN" -m build --wheel --outdir "$WHEELHOUSE"
  )
done

for repo in \
  packages/shared/python/rare-identity-protocol-python \
  packages/shared/python/rare-identity-verifier-python \
  services/rare-identity-core \
  packages/agent/python/rare-agent-sdk-python \
  packages/platform/python/rare-platform-sdk-python
do
  (
    cd "$repo"
    PIP_DEFAULT_TIMEOUT=120 PIP_FIND_LINKS="$WHEELHOUSE" "$PYTHON_BIN" -m piptools compile --no-strip-extras --generate-hashes --output-file requirements.lock pyproject.toml
    PIP_DEFAULT_TIMEOUT=120 PIP_FIND_LINKS="$WHEELHOUSE" "$PYTHON_BIN" -m piptools compile --no-strip-extras --generate-hashes --extra test --output-file requirements-test.lock pyproject.toml
  )
done

"$PYTHON_BIN" - <<'PY'
from pathlib import Path

ROOT = Path.cwd()
INTERNAL_PACKAGES = {
    "rare-identity-protocol",
    "rare-identity-verifier",
}
LOCK_FILES = [
    ROOT / "packages/shared/python/rare-identity-protocol-python" / "requirements.lock",
    ROOT / "packages/shared/python/rare-identity-protocol-python" / "requirements-test.lock",
    ROOT / "packages/shared/python/rare-identity-verifier-python" / "requirements.lock",
    ROOT / "packages/shared/python/rare-identity-verifier-python" / "requirements-test.lock",
    ROOT / "services/rare-identity-core" / "requirements.lock",
    ROOT / "services/rare-identity-core" / "requirements-test.lock",
    ROOT / "packages/agent/python/rare-agent-sdk-python" / "requirements.lock",
    ROOT / "packages/agent/python/rare-agent-sdk-python" / "requirements-test.lock",
    ROOT / "packages/platform/python/rare-platform-sdk-python" / "requirements.lock",
    ROOT / "packages/platform/python/rare-platform-sdk-python" / "requirements-test.lock",
]


def should_drop_package(line: str) -> bool:
    for package in INTERNAL_PACKAGES:
        if line.startswith(f"{package}=="):
            return True
    return False


def sanitize_lockfile(path: Path) -> None:
    lines = path.read_text().splitlines()
    cleaned: list[str] = []
    skip_entry = False

    for line in lines:
        if line.startswith("--find-links "):
            continue

        if should_drop_package(line):
            skip_entry = True
            continue

        if skip_entry:
            if line.startswith("    ") or line.startswith("#"):
                continue
            skip_entry = False

        cleaned.append(line)

    path.write_text("\n".join(cleaned) + "\n")


for lock_file in LOCK_FILES:
    sanitize_lockfile(lock_file)
PY
