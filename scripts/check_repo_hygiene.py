#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

BANNED_PATHS = {
    ".gcloudignore",
    ".github/workflows/deploy-rare-core.yml",
    ".github/workflows/release-public-agent-sdk.yml",
    ".github/workflows/sync-public-oss.yml",
    "docs/contact-and-dashboard.md",
    "docs/deployment-gcp.md",
    "docs/open-source-overview.md",
    "docs/ops-inventory.md",
    "docs/oss-split-plan.md",
    "docs/release-sop.md",
    "docs/sdk-release.md",
    "infra/gcp/terraform/README.md",
    "infra/gcp/terraform/main.tf",
    "infra/gcp/terraform/outputs.tf",
    "infra/gcp/terraform/providers.tf",
    "infra/gcp/terraform/terraform.tfvars.example",
    "infra/gcp/terraform/variables.tf",
    "open-source/public-oss/Rare/README.md",
    "open-source/public-oss/rare-agent-python/.github/ISSUE_TEMPLATE/bug_report.yml",
    "open-source/public-oss/rare-agent-python/.github/ISSUE_TEMPLATE/config.yml",
    "open-source/public-oss/rare-agent-python/.github/ISSUE_TEMPLATE/feature_request.yml",
    "open-source/public-oss/rare-agent-python/.github/PULL_REQUEST_TEMPLATE.md",
    "open-source/public-oss/rare-agent-python/.github/workflows/ci.yml",
    "open-source/public-oss/rare-agent-python/.github/workflows/publish.yml",
    "open-source/public-oss/rare-agent-python/CODE_OF_CONDUCT.md",
    "open-source/public-oss/rare-agent-python/CONTRIBUTING.md",
    "open-source/public-oss/rare-agent-python/HOSTED_VS_SELF_HOSTED.md",
    "open-source/public-oss/rare-agent-python/README.md",
    "open-source/public-oss/rare-agent-python/SECURITY.md",
    "open-source/public-oss/rare-agent-python/STATUS.md",
    "open-source/public-oss/rare-agent-python/SUPPORT.md",
    "open-source/public-oss/rare-platform-ts/.github/ISSUE_TEMPLATE/bug_report.yml",
    "open-source/public-oss/rare-platform-ts/.github/ISSUE_TEMPLATE/config.yml",
    "open-source/public-oss/rare-platform-ts/.github/ISSUE_TEMPLATE/feature_request.yml",
    "open-source/public-oss/rare-platform-ts/.github/PULL_REQUEST_TEMPLATE.md",
    "open-source/public-oss/rare-platform-ts/.github/workflows/ci.yml",
    "open-source/public-oss/rare-platform-ts/.github/workflows/publish.yml",
    "open-source/public-oss/rare-platform-ts/CODE_OF_CONDUCT.md",
    "open-source/public-oss/rare-platform-ts/CONTRIBUTING.md",
    "open-source/public-oss/rare-platform-ts/README.md",
    "open-source/public-oss/rare-platform-ts/SECURITY.md",
    "open-source/public-oss/rare-platform-ts/STATUS.md",
    "open-source/public-oss/rare-platform-ts/SUPPORT.md",
    "open-source/public-oss/rare-platform-ts/TRUST_MODEL.md",
    "open-source/public-oss/rare-protocol-py/.github/ISSUE_TEMPLATE/bug_report.yml",
    "open-source/public-oss/rare-protocol-py/.github/ISSUE_TEMPLATE/config.yml",
    "open-source/public-oss/rare-protocol-py/.github/ISSUE_TEMPLATE/feature_request.yml",
    "open-source/public-oss/rare-protocol-py/.github/PULL_REQUEST_TEMPLATE.md",
    "open-source/public-oss/rare-protocol-py/.github/workflows/ci.yml",
    "open-source/public-oss/rare-protocol-py/.github/workflows/publish.yml",
    "open-source/public-oss/rare-protocol-py/CODE_OF_CONDUCT.md",
    "open-source/public-oss/rare-protocol-py/COMPATIBILITY.md",
    "open-source/public-oss/rare-protocol-py/CONTRIBUTING.md",
    "open-source/public-oss/rare-protocol-py/README.md",
    "open-source/public-oss/rare-protocol-py/SECURITY.md",
    "open-source/public-oss/rare-protocol-py/STATUS.md",
    "open-source/public-oss/rare-protocol-py/SUPPORT.md",
    "packages/ts/rare-platform-kit-ts/E2E_TEST_REPORT_2026-03-14.md",
    "scripts/legacy/split_repos.sh",
    "scripts/legacy/verify_split_repos.sh",
    "scripts/publish_public_repos.sh",
    "scripts/show_stats.py",
    "scripts/sync_public_repos.sh",
}

BANNED_PATTERNS = {
    r"Rare-ID/rare-agent-python": "legacy Agent split-repo reference",
    r"Rare-ID/rare-protocol-py": "legacy protocol split-repo reference",
    r"github\.com/rare-project/rare": "legacy placeholder repo URL",
    r"Rare-Sors/": "private repo reference",
    r"sync-public-oss": "legacy public sync workflow reference",
    r"open-source/public-oss": "legacy public template reference",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        return None


def main() -> int:
    failures: list[str] = []
    files = tracked_files()
    tracked_relpaths = {str(path.relative_to(ROOT)) for path in files}

    for relative in sorted(BANNED_PATHS):
        if relative in tracked_relpaths and (ROOT / relative).exists():
            failures.append(f"banned path still tracked: {relative}")

    for path in files:
        if path == SELF:
            continue
        text = read_text(path)
        if text is None:
            continue
        relative = path.relative_to(ROOT)
        for pattern, reason in BANNED_PATTERNS.items():
            if re.search(pattern, text):
                failures.append(f"{relative}: {reason} ({pattern})")

    if failures:
        print("Repo hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Repo hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
