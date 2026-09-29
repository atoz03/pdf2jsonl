"""Record validation: invalid cases, JSON Schema/validator agreement, omit-missing policy, version routing."""
from __future__ import annotations

import copy
import json

import jsonschema

from breeding_contract import resolve_schema, validate_record
from breeding_contract.check import load_invalid_case
from breeding_contract.rules import rule_to_json_schema
from breeding_contract.util import load_yaml

from conftest import read_jsonl


def valid_records(root):
    files = sorted(root.glob("examples/records/*.jsonl")) + [root / "examples/output/synthetic_rice_qtl.jsonl"] + \
        sorted(root.glob("examples/migration/*/*.migrated.jsonl"))
    return [(f"{p.name}:{i + 1}", r) for p in files for i, r in enumerate(read_jsonl(p))]


def cases(root):
    return load_yaml(root / "examples/invalid/cases.yaml")["cases"]


def test_example_records_are_valid(root):
    recs = valid_records(root)
    assert len(recs) > 20
    for label, rec in recs:
        res = validate_record(rec, root=root)
        assert res.valid, (label, [i.to_dict() for i in res.errors])


def test_invalid_cases_fail_with_expected_codes(root):
    for case in cases(root):
        rc = resolve_schema(case["version"], root)
        res = rc.validator(case.get("profile")).validate(load_invalid_case(root, case))
        codes = {i.code for i in res.errors}
        assert codes and set(case["expect"]) <= codes, (case["id"], sorted(codes))


def test_generated_json_schema_agrees_with_validator(root):
    """The published record.schema.json (structure + expressible rules) must accept every valid record and
    reject every invalid case whose expected issues are expressible in JSON Schema."""
    by_version = {}
    for label, rec in valid_records(root):
        rc = resolve_schema(rec["common"]["schema_version"], root)
        v = by_version.setdefault(rc.version, jsonschema.Draft202012Validator(rc.record_schema()))
        errs = [e.message for e in v.iter_errors(rec)]
        assert not errs, (label, errs[:3])
    for case in cases(root):
        if case.get("profile"):
            continue
        rc = resolve_schema(case["version"], root)
        schema = rc.record_schema()
        only = set(schema["x-validator-only-rules"])
        if any(c.startswith("RULE_") and c[5:] in only for c in case["expect"]):
            continue
        assert not jsonschema.Draft202012Validator(schema).is_valid(load_invalid_case(root, case)), case["id"]


def test_forbid_pattern_schema_is_type_guarded():
    rule = {"id": "RX", "title_zh": "t", "kind": "forbid_pattern", "severity": "error", "pattern": "^file:",
            "fields": ["common.a", "common.b"]}
    schema = {"type": "object", **rule_to_json_schema(rule)}
    v = jsonschema.Draft202012Validator(schema)
    assert v.is_valid({"common": {"a": "https://x", "b": ["doi:1", "urn:2"]}})
    assert v.is_valid({"common": {"a": 5, "b": {"k": "ok"}}})
    assert not v.is_valid({"common": {"a": "file:///tmp/x"}})
    assert not v.is_valid({"common": {"b": ["ok", "file:/x"]}})
    assert not v.is_valid({"common": {"b": {"k": "file:/x"}}})


def test_omit_missing_policy(root):
    base = read_jsonl(root / "examples/records/tool_spec.jsonl")[0]
    for bad in (None, "", [], {}):
        rec = copy.deepcopy(base)
        rec["skills"]["software_version"] = bad
        assert not validate_record(rec, root=root).valid, repr(bad)
    rec = copy.deepcopy(base)
    rec["transform"] = {}
    assert not validate_record(rec, root=root).valid


def test_validate_record_uses_declared_version(root):
    rec = read_jsonl(root / "examples/records/tool_spec.jsonl")[0]
    assert validate_record(rec, root=root).valid
    old = copy.deepcopy(rec)
    old["common"]["schema_version"] = "3.0.0"
    del old["common"]["schema_name"]  # 3.1.0 additions are unknown to 3.0.0
    for name in ("tool_input_formats", "tool_output_formats"):
        del old["skills"][name]
    assert validate_record(old, root=root).valid
    mismatch = validate_record(rec, version="3.0.0", root=root)
    assert "SCHEMA_VERSION_MISMATCH" in {i.code for i in mismatch.errors}


def test_warning_vocabulary_does_not_reject(root):
    rec = read_jsonl(root / "examples/records/tool_spec.jsonl")[0]
    rec["common"]["extraction_method"] = "crowdsourcing"  # extraction_method: closed but warning-level
    res = validate_record(rec, root=root)
    assert res.valid
    assert "VOCAB_UNKNOWN_CODE" in {i.code for i in res.warnings}


def test_dataset_rules(root):
    rc = resolve_schema("latest", root)
    rec = read_jsonl(root / "examples/records/tool_spec.jsonl")[0]
    issues = rc.validator().validate_dataset([rec, json.loads(json.dumps(rec))])
    assert any(i.rule_id == "R025" and i.severity == "error" for _, i in issues)
