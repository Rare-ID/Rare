#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PUBLIC_MARKDOWN_FILES = {
    "references/flows.md": "flows.md",
    "references/parameter-explanations.md": "parameter-explanations.md",
    "references/runtime-protocol.md": "runtime-protocol.md",
}
PUBLIC_BINARY_FILES = {
    "scripts/rare_sign.py": "rare_sign.py",
}


def build_public_skill_markdown(content: str) -> str:
    rewritten = content
    rewritten = rewritten.replace("./scripts/rare_sign.py", "./rare_sign.py")
    rewritten = rewritten.replace("./references/flows.md", "./flows.md")
    rewritten = rewritten.replace("./references/parameter-explanations.md", "./parameter-explanations.md")
    rewritten = rewritten.replace("./references/runtime-protocol.md", "./runtime-protocol.md")
    return rewritten


def build_public_reference_markdown(content: str) -> str:
    rewritten = content
    rewritten = rewritten.replace("skills/rare-agent/scripts/rare_sign.py", "./rare_sign.py")
    rewritten = rewritten.replace("https://rareid.cc/skills.md", "https://rareid.cc/skill.md")
    return rewritten


def export_public_bundle(source: Path, target: Path) -> None:
    skill_dir = source.parent
    content = build_public_skill_markdown(source.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    for relative_source, public_name in PUBLIC_MARKDOWN_FILES.items():
        current_source = skill_dir / relative_source
        current_target = target.parent / public_name
        current_target.write_text(
            build_public_reference_markdown(current_source.read_text(encoding="utf-8")),
            encoding="utf-8",
        )

    for relative_source, public_name in PUBLIC_BINARY_FILES.items():
        current_source = skill_dir / relative_source
        current_target = target.parent / public_name
        shutil.copyfile(current_source, current_target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a canonical skill markdown file and public bundle")
    parser.add_argument("source", help="Canonical SKILL.md path")
    parser.add_argument("target", help="Public mirror markdown path, usually landingpage/public/skill.md")
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    export_public_bundle(source, target)
    print(f"Exported public skill bundle from {source} -> {target.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
