#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/out/public-repos}"
ORG="${GITHUB_ORG:-Rare-ID}"
TARGET_BRANCH="${TARGET_BRANCH:-main}"
SOURCE_MODE="${SOURCE_MODE:-workspace}"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rare-publish-XXXXXX")"

cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

repo_source_dir() {
  case "$1" in
    "Rare-Identity-Core") echo "rare-identity-core" ;;
    "Rare-Agent-SDK-Python") echo "rare-agent-sdk-python" ;;
    "Rare-Platform-Kit-TS") echo "rare-platform-kit-ts" ;;
    *)
      echo "unknown repo: $1" >&2
      exit 1
      ;;
  esac
}

repo_input_dir() {
  local repo_name="$1"
  if [[ "${SOURCE_MODE}" == "out" ]]; then
    echo "${OUT_DIR}/${repo_name}"
  else
    echo "${ROOT_DIR}/$(repo_source_dir "${repo_name}")"
  fi
}

publish_one() {
  local repo_name="$1"
  local source_dir
  local target_dir

  source_dir="$(repo_input_dir "${repo_name}")"
  target_dir="${WORK_DIR}/${repo_name}"

  if [[ ! -d "${source_dir}" ]]; then
    echo "missing source directory: ${source_dir}" >&2
    exit 1
  fi

  git clone --branch "${TARGET_BRANCH}" "https://github.com/${ORG}/${repo_name}.git" "${target_dir}" >/dev/null

  (
    cd "${target_dir}"
    rsync -a --delete --exclude .git "${source_dir}/" "${target_dir}/"
    git config user.name "Codex"
    git config user.email "codex@local"
    git add .
    if git diff --cached --quiet; then
      echo "no changes for ${repo_name}"
      return
    fi
    git commit -m "Sync from Rare workspace" >/dev/null
    git push origin "HEAD:refs/heads/${TARGET_BRANCH}"
    echo "published ${repo_name}"
  )
}

publish_one "Rare-Identity-Core"
publish_one "Rare-Agent-SDK-Python"
publish_one "Rare-Platform-Kit-TS"

echo "publish completed"
