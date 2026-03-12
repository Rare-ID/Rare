#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_OSS_OWNER="${PUBLIC_OSS_OWNER:-Rare-ID}"
OSS_SYNC_TOKEN="${OSS_SYNC_TOKEN:?OSS_SYNC_TOKEN is required}"
SOURCE_SHA="${GITHUB_SHA:-$(git -C "$ROOT_DIR" rev-parse HEAD)}"
SOURCE_SHORT_SHA="${SOURCE_SHA:0:7}"
WORK_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

RSYNC_EXCLUDES=(
  --exclude '.DS_Store'
  --exclude '.coverage'
  --exclude '.pytest_cache/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '*.pyo'
  --exclude '*.egg-info/'
  --exclude 'dist/'
  --exclude 'node_modules/'
  --exclude '.vite/'
)

log() {
  printf '[sync-public-oss] %s\n' "$*"
}

remove_junk() {
  local repo_dir="$1"

  rm -rf \
    "$repo_dir/.DS_Store" \
    "$repo_dir/.coverage"
}

clone_repo() {
  local repo_name="$1"
  local repo_dir="$WORK_DIR/$repo_name"
  local repo_url="https://x-access-token:${OSS_SYNC_TOKEN}@github.com/${PUBLIC_OSS_OWNER}/${repo_name}.git"

  git clone --depth 1 "$repo_url" "$repo_dir" >/dev/null 2>&1
  printf '%s\n' "$repo_dir"
}

remove_target() {
  local repo_dir="$1"
  local rel_path="$2"

  rm -rf "$repo_dir/$rel_path"
  mkdir -p "$(dirname "$repo_dir/$rel_path")"
}

copy_file() {
  local repo_dir="$1"
  local src_rel="$2"
  local dest_rel="$3"

  remove_target "$repo_dir" "$dest_rel"
  cp "$ROOT_DIR/$src_rel" "$repo_dir/$dest_rel"
}

copy_common_public_files() {
  local repo_dir="$1"
  local template_root="$2"

  copy_file "$repo_dir" "LICENSE" "LICENSE"
  copy_file "$repo_dir" "$template_root/CONTRIBUTING.md" "CONTRIBUTING.md"
  copy_file "$repo_dir" "$template_root/SECURITY.md" "SECURITY.md"
  copy_file "$repo_dir" "$template_root/CODE_OF_CONDUCT.md" "CODE_OF_CONDUCT.md"
  copy_file "$repo_dir" "$template_root/SUPPORT.md" "SUPPORT.md"
}

copy_dir() {
  local repo_dir="$1"
  local src_rel="$2"
  local dest_rel="$3"

  remove_target "$repo_dir" "$dest_rel"
  mkdir -p "$repo_dir/$dest_rel"
  rsync -a "${RSYNC_EXCLUDES[@]}" "$ROOT_DIR/$src_rel/" "$repo_dir/$dest_rel/"
}

commit_and_push() {
  local repo_dir="$1"
  local repo_name="$2"

  git -C "$repo_dir" config user.name "rare-sync-bot"
  git -C "$repo_dir" config user.email "rare-sync-bot@users.noreply.github.com"
  git -C "$repo_dir" add -A

  if git -C "$repo_dir" diff --cached --quiet; then
    log "$repo_name: no public changes to sync"
    return 0
  fi

  git -C "$repo_dir" commit -m "Sync from private Rare workspace (${SOURCE_SHORT_SHA})" >/dev/null
  git -C "$repo_dir" push origin HEAD:main >/dev/null
  log "$repo_name: synced to main"
}

sync_protocol_repo() {
  local repo_dir
  repo_dir="$(clone_repo "rare-protocol-py")"

  remove_junk "$repo_dir"
  copy_file "$repo_dir" "public-oss/rare-protocol-py/README.md" "README.md"
  copy_file "$repo_dir" "public-oss/rare-protocol-py/STATUS.md" "STATUS.md"
  copy_file "$repo_dir" "public-oss/rare-protocol-py/COMPATIBILITY.md" "COMPATIBILITY.md"
  copy_dir "$repo_dir" "public-oss/rare-protocol-py/.github" ".github"
  copy_common_public_files "$repo_dir" "public-oss/rare-protocol-py"

  copy_dir "$repo_dir" "rare-identity-protocol-python/src/rare_identity_protocol" "src/rare_identity_protocol"
  copy_dir "$repo_dir" "rare-identity-verifier-python/src/rare_identity_verifier" "src/rare_identity_verifier"

  remove_target "$repo_dir" "tests"
  mkdir -p "$repo_dir/tests"
  copy_file "$repo_dir" "rare-identity-protocol-python/tests/test_protocol_unit.py" "tests/test_protocol_unit.py"
  copy_file "$repo_dir" "rare-identity-protocol-python/tests/test_vectors.py" "tests/test_vectors.py"
  copy_file "$repo_dir" "rare-identity-verifier-python/tests/test_verifier_unit.py" "tests/test_verifier_unit.py"

  remove_target "$repo_dir" "docs"
  mkdir -p "$repo_dir/docs"
  copy_file "$repo_dir" "rare-identity-core/docs/RIP_INDEX.md" "docs/RIP_INDEX.md"
  copy_file "$repo_dir" "rare-identity-core/docs/CONTRIBUTING_RIP.md" "docs/CONTRIBUTING_RIP.md"
  copy_file "$repo_dir" "rare-identity-core/docs/rip-0000-rip-process.md" "docs/rip-0000-rip-process.md"
  copy_file "$repo_dir" "rare-identity-core/docs/rip-0001-identity-attestation.md" "docs/rip-0001-identity-attestation.md"
  copy_file "$repo_dir" "rare-identity-core/docs/rip-0002-delegation.md" "docs/rip-0002-delegation.md"
  copy_file "$repo_dir" "rare-identity-core/docs/rip-0003-challenge-auth.md" "docs/rip-0003-challenge-auth.md"
  copy_file "$repo_dir" "rare-identity-core/docs/rip-0004-key-rotation.md" "docs/rip-0004-key-rotation.md"
  copy_file "$repo_dir" "rare-identity-core/docs/rip-0005-platform-onboarding-and-events.md" "docs/rip-0005-platform-onboarding-and-events.md"

  commit_and_push "$repo_dir" "rare-protocol-py"
}

sync_overview_repo() {
  local repo_dir
  repo_dir="$(clone_repo "Rare")"

  remove_junk "$repo_dir"
  copy_file "$repo_dir" "public-oss/Rare/README.md" "README.md"
  remove_target "$repo_dir" ".github"
  remove_target "$repo_dir" "CONTRIBUTING.md"
  remove_target "$repo_dir" "SECURITY.md"
  remove_target "$repo_dir" "CODE_OF_CONDUCT.md"
  remove_target "$repo_dir" "SUPPORT.md"
  remove_target "$repo_dir" "LICENSE"

  commit_and_push "$repo_dir" "Rare"
}

sync_agent_repo() {
  local repo_dir
  repo_dir="$(clone_repo "rare-agent-python")"

  remove_junk "$repo_dir"
  copy_file "$repo_dir" "public-oss/rare-agent-python/README.md" "README.md"
  copy_file "$repo_dir" "public-oss/rare-agent-python/STATUS.md" "STATUS.md"
  copy_file "$repo_dir" "public-oss/rare-agent-python/HOSTED_VS_SELF_HOSTED.md" "HOSTED_VS_SELF_HOSTED.md"
  copy_dir "$repo_dir" "public-oss/rare-agent-python/.github" ".github"
  copy_common_public_files "$repo_dir" "public-oss/rare-agent-python"

  copy_file "$repo_dir" "rare-agent-sdk-python/pyproject.toml" "pyproject.toml"
  copy_file "$repo_dir" "rare-agent-sdk-python/requirements.lock" "requirements.lock"
  copy_file "$repo_dir" "rare-agent-sdk-python/requirements-test.lock" "requirements-test.lock"
  copy_dir "$repo_dir" "rare-agent-sdk-python/src/rare_agent_sdk" "src/rare_agent_sdk"
  copy_dir "$repo_dir" "rare-agent-sdk-python/tests" "tests"

  commit_and_push "$repo_dir" "rare-agent-python"
}

sync_platform_repo() {
  local repo_dir
  repo_dir="$(clone_repo "rare-platform-ts")"

  remove_junk "$repo_dir"
  copy_file "$repo_dir" "public-oss/rare-platform-ts/README.md" "README.md"
  copy_file "$repo_dir" "public-oss/rare-platform-ts/STATUS.md" "STATUS.md"
  copy_file "$repo_dir" "public-oss/rare-platform-ts/TRUST_MODEL.md" "TRUST_MODEL.md"
  copy_dir "$repo_dir" "public-oss/rare-platform-ts/.github" ".github"
  copy_common_public_files "$repo_dir" "public-oss/rare-platform-ts"

  copy_file "$repo_dir" "rare-platform-kit-ts/QUICKSTART.md" "QUICKSTART.md"
  copy_file "$repo_dir" "rare-platform-kit-ts/FULL_MODE_GUIDE.md" "FULL_MODE_GUIDE.md"
  copy_file "$repo_dir" "rare-platform-kit-ts/EVENTS_GUIDE.md" "EVENTS_GUIDE.md"
  copy_file "$repo_dir" "rare-platform-kit-ts/.gitignore" ".gitignore"
  copy_file "$repo_dir" "rare-platform-kit-ts/biome.json" "biome.json"
  copy_file "$repo_dir" "rare-platform-kit-ts/eslint.config.mjs" "eslint.config.mjs"
  copy_file "$repo_dir" "rare-platform-kit-ts/package.json" "package.json"
  copy_file "$repo_dir" "rare-platform-kit-ts/pnpm-lock.yaml" "pnpm-lock.yaml"
  copy_file "$repo_dir" "rare-platform-kit-ts/pnpm-workspace.yaml" "pnpm-workspace.yaml"
  copy_file "$repo_dir" "rare-platform-kit-ts/tsconfig.base.json" "tsconfig.base.json"
  copy_dir "$repo_dir" "rare-platform-kit-ts/.changeset" ".changeset"
  copy_dir "$repo_dir" "rare-platform-kit-ts/examples" "examples"
  copy_dir "$repo_dir" "rare-platform-kit-ts/packages" "packages"

  commit_and_push "$repo_dir" "rare-platform-ts"
}

sync_overview_repo
sync_protocol_repo
sync_agent_repo
sync_platform_repo
