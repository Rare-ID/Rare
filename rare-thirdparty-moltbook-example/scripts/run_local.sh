#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_DIR="$(cd "$ROOT_DIR/.." && pwd)"

export PYTHONPATH="$ROOT_DIR/apps:$WORKSPACE_DIR/rare-identity-core/libs:$WORKSPACE_DIR/rare-identity-core/services:${PYTHONPATH:-}"

uvicorn apps.dev:app --reload --host 127.0.0.1 --port 8000
