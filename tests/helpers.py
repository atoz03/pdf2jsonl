"""Helpers for tests that evolve the contract inside a repository copy."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

from breeding_contract.util import load_yaml

PROBE = "common.source_probe_note"
# Version-relative so the evolution tests keep working after every real release.
CURRENT = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
_major, _minor, _ = (int(x) for x in CURRENT.split("."))
NEXT = f"{_major}.{_minor + 1}.0"
NEXT_MAJOR = f"{_major + 1}.0.0"


def add_probe_field(repo: Path, since: str) -> str:
    """Add a D-availability common field (picked up by pdf_extraction's all_active/D selection)."""
    cat_path = repo / "field_catalog/field_catalog.yaml"
    cat = load_yaml(cat_path)
    base = next(f for f in cat["fields"] if f["path"] == "common.source_journal")
    f = copy.deepcopy(base)
    f.update(path=PROBE, since=since, definition_zh="测试探针字段：论文首页的探针说明（仅用于测试）")
    f.pop("origin_paths", None)
    cat["fields"].append(f)
    cat_path.write_text(yaml.safe_dump(cat, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return PROBE


def bump_version(repo: Path, version: str, date: str = "2026-10-01") -> None:
    (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
    cl = repo / "CHANGELOG.md"
    text = cl.read_text(encoding="utf-8")
    head, sep, rest = text.partition("\n## [")
    cl.write_text(f"{head}\n## [{version}] - {date}\n\n### Added\n- {PROBE} (test)\n{sep}{rest}", encoding="utf-8")
