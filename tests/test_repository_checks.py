"""`bdc check --strict` is the CI gate; these tests prove it passes here and catches drift in a copy."""
from __future__ import annotations

from breeding_contract.check import run_checks
from breeding_contract.docs_gen import generate_docs
from breeding_contract.sources import load_sources

from conftest import run_bdc


def errors(root, **kw):
    return [str(f) for f in run_checks(root, **kw) if f.level == "error"]


def test_strict_check_passes(root):
    findings = run_checks(root, strict=True)
    assert [str(f) for f in findings if f.level in ("error", "warning")] == []


def test_cli_check_exit_code(root):
    assert run_bdc(root, "check", "--strict").returncode == 0


def test_generated_docs_are_fresh(root):
    src = load_sources(root)
    for rel, text in generate_docs(src).items():
        assert (root / "docs/generated" / rel).read_text(encoding="utf-8") == text, rel


def test_skill_must_not_hard_code_field_paths(repo_copy):
    md = repo_copy / "skills/pdf2jsonl/SKILL.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nAlways fill common.source_page.\n", encoding="utf-8")
    py = repo_copy / "skills/pdf2jsonl/scripts/pdf2jsonl_skill/repair.py"
    py.write_text(py.read_text(encoding="utf-8") + '\nPAGE = "common.source_page"\n', encoding="utf-8")
    errs = errors(repo_copy)
    assert any("SKILL.md hard-codes field paths" in e for e in errs)
    assert any("repair.py hard-codes field paths" in e for e in errs)


def test_skill_must_not_pin_contract_versions(repo_copy):
    md = repo_copy / "skills/pdf2jsonl/prompts/extraction_brief.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nUse contract 3.1.0.\n", encoding="utf-8")
    assert any("pins contract version 3.1.0" in e for e in errors(repo_copy))


def test_unimplemented_fill_rule_is_caught(repo_copy):
    prof = repo_copy / "profiles/pdf_extraction.yaml"
    text = prof.read_text(encoding="utf-8").replace("rule: run_id", "rule: telepathy", 1)
    assert "telepathy" in text
    prof.write_text(text, encoding="utf-8")
    assert any("telepathy" in e for e in errors(repo_copy))


def test_stale_docs_and_broken_examples_are_caught(repo_copy):
    doc = next((repo_copy / "docs/generated").glob("*.md"))
    doc.write_text(doc.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    rec = repo_copy / "examples/records/tool_spec.jsonl"
    rec.write_text(rec.read_text(encoding="utf-8").replace('"crop_name": "rice", ', ""), encoding="utf-8")
    errs = errors(repo_copy)
    assert any("[docs]" in e and "stale" in e for e in errs)
    assert any("[examples]" in e and "SCHEMA_REQUIRED" in e for e in errs)
