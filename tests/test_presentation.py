"""The presentation contract (docs/presentation.md, AMB-045/046/047): a record list shows the entity type beside
every mention, the validation status as its own column, the author's qualifier verbatim and the claim strength.

The check runs on the page template, so removing one of those columns from the dashboard fails `bdc check` — the
rule is part of the repository, not a habit.
"""
from __future__ import annotations

import shutil

from breeding_contract.check import PRESENTATION_MARKERS, check_presentation


def test_the_dashboard_keeps_the_presentation_rules(root):
    assert check_presentation(root) == []


def test_the_rules_are_documented(root):
    text = (root / "docs/presentation.md").read_text(encoding="utf-8")
    for phrase in ("实体必须与它的类型一起显示", "验证状态是一个独立列", "原文限定语必须逐字显示", "结论强度"):
        assert phrase in text
    # the page template names the same rules in one place
    page = (root / "site/pages/papers.html").read_text(encoding="utf-8")
    assert "docs/presentation.md" in page


def test_a_missing_column_is_reported(root, tmp_path):
    copy = tmp_path / "repo"
    shutil.copytree(root / "site", copy / "site")
    shutil.copytree(root / "docs", copy / "docs")
    page = copy / "site/pages/papers.html"
    page.write_text(page.read_text(encoding="utf-8").replace('T("限定语", "Qualifier")', "Qualifier"), encoding="utf-8")
    findings = check_presentation(copy)
    assert [f.level for f in findings] == ["error"]
    assert "qualifier column" in findings[0].message


def test_every_marker_is_checked(root):
    page = (root / "site/pages/papers.html").read_text(encoding="utf-8")
    for label, marker in PRESENTATION_MARKERS:
        assert marker in page, f"{label}: {marker!r} missing from the dashboard"
