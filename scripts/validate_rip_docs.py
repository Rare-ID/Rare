#!/usr/bin/env python3
"""Validate Rare RIP documentation structure and governance constraints."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DOCS_DIR = Path("services/rare-identity-core/docs")
INDEX_FILE = DOCS_DIR / "RIP_INDEX.md"

RE_NUMBERED = re.compile(r"^rip-(\d{4})-[a-z0-9-]+\.md$")
RE_DRAFT = re.compile(r"^rip-draft-[a-z0-9-]+\.md$")
RE_METADATA = re.compile(r"^([A-Za-z][A-Za-z-]*):\s*(.+)$")
RE_TABLE_SEPARATOR = re.compile(r"^:?-{3,}:?$")

REQUIRED_METADATA_KEYS = (
    "RIP",
    "Title",
    "Status",
    "Type",
    "Author",
    "Created",
    "Updated",
    "Requires",
    "Replaces",
    "Superseded-By",
    "Discussion",
)

ALLOWED_STATUSES = {
    "Draft",
    "Review",
    "Accepted",
    "Final",
    "Withdrawn",
    "Superseded",
}

REQUIRED_SECTIONS = (
    "Abstract",
    "Motivation",
    "Specification",
    "Backward Compatibility",
    "Security Considerations",
    "Test Vectors/Examples",
    "Reference Implementation",
)

REFERENCE_KEYS = ("Requires", "Replaces", "Superseded-By")


@dataclass
class RipDoc:
    path: Path
    rel_path: str
    is_draft: bool
    file_id: str
    metadata: dict[str, str]


def _contains_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def _parse_metadata(lines: list[str], rel_path: str, errors: list[str]) -> dict[str, str]:
    if not lines:
        errors.append(f"{rel_path}: empty file")
        return {}

    if not lines[0].startswith("# "):
        errors.append(f"{rel_path}: first line must be a level-1 heading")

    i = 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    metadata: dict[str, str] = {}
    saw_metadata = False

    while i < len(lines):
        line = lines[i].strip()
        if line == "":
            break
        if line.startswith("## "):
            errors.append(f"{rel_path}: missing metadata block before sections")
            return {}

        match = RE_METADATA.match(line)
        if not match:
            errors.append(f"{rel_path}: invalid metadata line: {line}")
            return {}

        key, value = match.group(1), match.group(2).strip()
        if key in metadata:
            errors.append(f"{rel_path}: duplicate metadata key: {key}")
        metadata[key] = value
        saw_metadata = True
        i += 1

    if not saw_metadata:
        errors.append(f"{rel_path}: metadata block is required")

    return metadata


def _parse_reference_ids(value: str, rel_path: str, key: str, errors: list[str]) -> list[str]:
    if value == "None":
        return []

    result: list[str] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        if not re.fullmatch(r"\d{4}", item):
            errors.append(f"{rel_path}: {key} contains invalid RIP id: {item}")
            continue
        result.append(item)
    return result


def _validate_sections(text: str, rel_path: str, errors: list[str]) -> None:
    for section in REQUIRED_SECTIONS:
        pattern = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.MULTILINE)
        if pattern.search(text) is None:
            errors.append(f"{rel_path}: missing required section '## {section}'")


def _collect_rip_docs(errors: list[str], strict: bool) -> list[RipDoc]:
    if not DOCS_DIR.exists():
        errors.append(f"docs directory not found: {DOCS_DIR}")
        return []

    rip_docs: list[RipDoc] = []

    for path in sorted(DOCS_DIR.glob("rip-*.md")):
        name = path.name
        match = RE_NUMBERED.match(name)
        if not match:
            errors.append(f"{path}: invalid numbered RIP filename")
            continue
        rip_docs.append(RipDoc(path=path, rel_path=str(path.relative_to(DOCS_DIR)), is_draft=False, file_id=match.group(1), metadata={}))

    drafts_dir = DOCS_DIR / "drafts"
    if drafts_dir.exists():
        for path in sorted(drafts_dir.glob("*.md")):
            name = path.name
            if not RE_DRAFT.match(name):
                errors.append(f"{path}: invalid draft RIP filename")
                continue
            rip_docs.append(
                RipDoc(
                    path=path,
                    rel_path=str(path.relative_to(DOCS_DIR)),
                    is_draft=True,
                    file_id="TBA",
                    metadata={},
                )
            )

    for doc in rip_docs:
        text = doc.path.read_text(encoding="utf-8")
        if strict and _contains_non_ascii(text):
            errors.append(f"{doc.rel_path}: contains non-ASCII characters (strict mode)")

        lines = text.splitlines()
        metadata = _parse_metadata(lines, doc.rel_path, errors)
        doc.metadata = metadata

        for key in REQUIRED_METADATA_KEYS:
            if key not in metadata:
                errors.append(f"{doc.rel_path}: missing metadata key '{key}'")

        status = metadata.get("Status")
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{doc.rel_path}: invalid Status '{status}'")

        if doc.is_draft:
            if metadata.get("RIP") != "TBA":
                errors.append(f"{doc.rel_path}: draft RIP must set 'RIP: TBA'")
            if metadata.get("Status") != "Draft":
                errors.append(f"{doc.rel_path}: draft RIP must set 'Status: Draft'")
        else:
            if metadata.get("RIP") != doc.file_id:
                errors.append(f"{doc.rel_path}: RIP metadata id does not match filename id {doc.file_id}")

        for ref_key in REFERENCE_KEYS:
            if ref_key in metadata:
                _parse_reference_ids(metadata[ref_key], doc.rel_path, ref_key, errors)

        _validate_sections(text, doc.rel_path, errors)

    return rip_docs


def _validate_cross_references(rip_docs: list[RipDoc], errors: list[str]) -> None:
    numbered_ids = {doc.file_id for doc in rip_docs if not doc.is_draft}

    replaces_map: dict[str, set[str]] = {}
    superseded_by_map: dict[str, set[str]] = {}

    for doc in rip_docs:
        if doc.is_draft:
            continue
        doc_id = doc.file_id
        replaces = set(_parse_reference_ids(doc.metadata.get("Replaces", "None"), doc.rel_path, "Replaces", errors))
        superseded_by = set(
            _parse_reference_ids(doc.metadata.get("Superseded-By", "None"), doc.rel_path, "Superseded-By", errors)
        )
        replaces_map[doc_id] = replaces
        superseded_by_map[doc_id] = superseded_by

        for ref in replaces.union(superseded_by).union(
            _parse_reference_ids(doc.metadata.get("Requires", "None"), doc.rel_path, "Requires", errors)
        ):
            if ref not in numbered_ids:
                errors.append(f"{doc.rel_path}: references unknown RIP id {ref}")

        if doc.metadata.get("Status") == "Superseded" and not superseded_by:
            errors.append(f"{doc.rel_path}: status Superseded requires non-empty Superseded-By")

    for doc_id, superseded_by in superseded_by_map.items():
        for new_id in superseded_by:
            if doc_id not in replaces_map.get(new_id, set()):
                errors.append(
                    f"rip-{doc_id}: Superseded-By includes {new_id}, but rip-{new_id} Replaces does not include {doc_id}"
                )


def _parse_index_entries(errors: list[str]) -> dict[str, tuple[str, str]]:
    if not INDEX_FILE.exists():
        errors.append(f"missing index file: {INDEX_FILE}")
        return {}

    entries: dict[str, tuple[str, str]] = {}
    for raw_line in INDEX_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 4:
            continue

        if cells[0] == "RIP":
            continue
        if all(RE_TABLE_SEPARATOR.match(cell) for cell in cells):
            continue

        rip_id, status, _title, file_cell = cells
        entries[file_cell] = (rip_id, status)

    return entries


def _validate_index_consistency(rip_docs: list[RipDoc], errors: list[str]) -> None:
    entries = _parse_index_entries(errors)
    if not entries:
        return

    docs_by_path = {doc.rel_path: doc for doc in rip_docs}

    for rel_path, doc in docs_by_path.items():
        if rel_path not in entries:
            errors.append(f"RIP_INDEX.md: missing entry for {rel_path}")
            continue

        index_id, index_status = entries[rel_path]
        expected_id = "TBA" if doc.is_draft else doc.file_id
        expected_status = doc.metadata.get("Status", "")
        if index_id != expected_id:
            errors.append(f"RIP_INDEX.md: id mismatch for {rel_path}: expected {expected_id}, got {index_id}")
        if index_status != expected_status:
            errors.append(
                f"RIP_INDEX.md: status mismatch for {rel_path}: expected {expected_status}, got {index_status}"
            )

    for rel_path in entries:
        if rel_path not in docs_by_path:
            errors.append(f"RIP_INDEX.md: references missing file {rel_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RIP docs")
    parser.add_argument("--strict", action="store_true", help="Enable strict checks (including ASCII-only content)")
    args = parser.parse_args()

    errors: list[str] = []
    rip_docs = _collect_rip_docs(errors=errors, strict=args.strict)
    _validate_cross_references(rip_docs, errors)
    _validate_index_consistency(rip_docs, errors)

    if errors:
        print("RIP documentation validation failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(f"RIP documentation validation passed ({len(rip_docs)} files checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
