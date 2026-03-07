#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/out/public-repos}"

mkdir -p "${OUT_DIR}"

sync_snapshot() {
  local repo_name="$1"
  local source_dir="$2"
  local target_dir="${OUT_DIR}/${repo_name}"

  rm -rf "${target_dir}"
  mkdir -p "${target_dir}"
  rsync -a --delete "${ROOT_DIR}/${source_dir}/" "${target_dir}/"
  echo "created ${target_dir}"
}

sync_snapshot "Rare-Identity-Core" "rare-identity-core"
sync_snapshot "Rare-Agent-SDK-Python" "rare-agent-sdk-python"
sync_snapshot "Rare-Platform-Kit-TS" "rare-platform-kit-ts"

echo "split completed under ${OUT_DIR}"
