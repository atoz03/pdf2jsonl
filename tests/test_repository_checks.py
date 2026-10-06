"""`bdc check --strict` is the CI gate; these tests prove it passes here and catches drift in a copy."""
from __future__ import annotations

import pytest
import yaml

from breeding_contract.check import check_docs, run_checks
from breeding_contract.compile import compile_contract
from breeding_contract.docs_gen import generate_docs, load_field_examples
from breeding_contract.sources import load_sources
from breeding_contract.util import load_yaml

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
        assert (root / rel).read_text(encoding="utf-8") == text, rel


@pytest.mark.parametrize("path,value", [
    ("common.extraction_confidence", 1.5),
    ("common.record_kind", "not_a_record_kind"),
    ("agent.supporting_evidence", [{"source_page": 3}]),
    ("skills.workflow_steps", [{"step_no": 0, "step_desc": "invalid step"}]),
])
def test_invalid_documentation_examples_are_reported(repo_copy, path, value):
    file = repo_copy / "docs/field_examples.yaml"
    examples = load_yaml(file)
    examples[path] = value
    file.write_text(yaml.safe_dump(examples, allow_unicode=True), encoding="utf-8")
    assert any(f.level == "error" and path in f.message for f in check_docs(load_sources(repo_copy)))


def test_missing_documentation_example_is_reported(repo_copy):
    file = repo_copy / "docs/field_examples.yaml"
    examples = load_yaml(file)
    del examples["common.source_page"]
    file.write_text(yaml.safe_dump(examples, allow_unicode=True), encoding="utf-8")
    assert any("missing examples ['common.source_page']" in f.message for f in check_docs(load_sources(repo_copy)))


def test_documentation_examples_follow_version_and_preserve_false_and_zero(repo_copy):
    contract = compile_contract(load_sources(repo_copy))
    contract["version"] = "9.0.0"
    file = repo_copy / "docs/field_examples.yaml"
    examples = load_yaml(file)
    examples["transform.qa_answerable"] = False
    examples["agent.p_value"] = 0
    file.write_text(yaml.safe_dump(examples, allow_unicode=True), encoding="utf-8")
    loaded = load_field_examples(repo_copy, contract)
    assert loaded["common.schema_version"] == "9.0.0"
    assert loaded["transform.qa_answerable"] is False
    assert loaded["agent.p_value"] == 0


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
    root_doc = repo_copy / "FIELD_DEFINITIONS.md"
    root_doc.write_text(root_doc.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    rec = repo_copy / "examples/records/tool_spec.jsonl"
    rec.write_text(rec.read_text(encoding="utf-8").replace('"crop_name": "rice", ', ""), encoding="utf-8")
    errs = errors(repo_copy)
    assert any("[docs]" in e and "stale" in e for e in errs)
    assert any("[docs]" in e and "FIELD_DEFINITIONS.md is stale" in e for e in errs)
    assert any("[examples]" in e and "SCHEMA_REQUIRED" in e for e in errs)
