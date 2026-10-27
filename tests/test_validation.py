"""Record validation: invalid cases, JSON Schema/validator agreement, omit-missing policy, version routing."""
from __future__ import annotations

import copy
import json

import jsonschema

from breeding_contract import resolve_schema, validate_record
from breeding_contract.check import load_invalid_case
from breeding_contract.rules import rule_to_json_schema
from breeding_contract.util import load_yaml, set_path

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


def test_a_deprecated_vocabulary_code_names_its_replacement(root):
    """qtl_overlaps_qtl is kept so old records resolve, but a record that uses it is told what to use (AMB-043)."""
    from breeding_contract.relations import predicate_code

    rc = resolve_schema("latest", root)
    rec = copy.deepcopy(read_jsonl(root / "examples/output/synthetic_rice_qtl.jsonl")[0])
    rec.setdefault("transform", {})["predicate_label"] = "qtl_overlaps_qtl"
    res = rc.validator().validate(rec)
    assert res.valid
    dep = [i for i in res.warnings if i.code == "VOCAB_CODE_DEPRECATED"]
    assert dep and dep[0].detail["replaced_by"] == "locus_overlaps_locus"
    # the pipeline never produces a deprecated code: it carries no cue any more
    voc = rc.contract["vocabularies"]["predicate_label"]
    assert predicate_code(voc, "overlapped with", ["qtl"], ["qtl"]) == "locus_overlaps_locus"


def test_new_grounding_rules(root):
    """3.8.0: three warnings that tie a field to what the paper actually reports (R038–R040)."""
    rc = resolve_schema("latest", root)
    v = rc.validator()
    base = copy.deepcopy(read_jsonl(root / "examples/output/synthetic_rice_qtl.jsonl")[0])
    set_path(base, "transform.claim_strength", "causal_statistical_only")

    def codes(rec):
        return {i.code for i in v.validate(rec).warnings}

    # R038: a causal claim whose only evidence is statistical should name a validation method
    assert "RULE_R038" in codes(base)
    with_method = copy.deepcopy(base)
    set_path(with_method, "agent.validation_methods", ["complementation in transgenic rice"])
    assert "RULE_R038" not in codes(with_method)
    # R039: functional_validated without a validation record
    status = copy.deepcopy(base)
    set_path(status, "agent.candidate_gene_status", "functional_validated")
    assert "RULE_R039" in codes(status)
    set_path(status, "agent.validated_by_record_ids", ["rec_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"])
    assert "RULE_R039" not in codes(status)
    # R040: a review paraphrase should keep the original-study lead
    review = copy.deepcopy(base)
    set_path(review, "transform.evidence_origin", "review_report")
    assert "RULE_R040" in codes(review)
    set_path(review, "agent.reported_citation_text", "Zhang et al. (2019) Nature Genetics 51: 1044")
    assert "RULE_R040" not in codes(review)



    rc = resolve_schema("latest", root)
    rec = read_jsonl(root / "examples/records/tool_spec.jsonl")[0]
    issues = rc.validator().validate_dataset([rec, json.loads(json.dumps(rec))])
    assert any(i.rule_id == "R025" and i.severity == "error" for _, i in issues)
