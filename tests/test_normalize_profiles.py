"""Deterministic normalization and profile resolution."""
from __future__ import annotations

import pytest

from breeding_contract import load_profile, resolve_schema
from breeding_contract.normalize import normalize_value, parse_raw_value
from breeding_contract.util import load_yaml


@pytest.fixture(scope="module")
def units(root):
    return load_yaml(root / "vocabularies/units.yaml")


@pytest.mark.parametrize("raw,unit,expect", [
    ("118.4", "cm", {"value": 118.4, "unit": "cm"}),
    ("1184", "mm", {"value": 118.4, "unit": "cm"}),
    ("1.2", "m", {"value": 120, "unit": "cm"}),
    ("12-15", "cm", {"min": 12, "max": 15, "unit": "cm"}),
    ("1,250", "g", {"value": 1250, "unit": "g"}),
    ("3", None, {"value": 3}),
])
def test_normalize_converts(units, raw, unit, expect):
    out, reason = normalize_value(raw, unit, units)
    assert reason is None and out == expect


@pytest.mark.parametrize("raw,unit,reason", [
    (None, "cm", "no_raw_value"),
    ("about 12", "cm", "unparsed_value"),
    ("12 ± 3", "cm", "unparsed_value"),
    ("15-12", "cm", "unparsed_value"),  # reversed ranges are never silently reordered
    ("12", "furlong", "unknown_unit"),
])
def test_normalize_refuses_guesses(units, raw, unit, reason):
    out, why = normalize_value(raw, unit, units)
    assert out == {} and why == reason


def test_parse_raw_value_keeps_raw_untouched():
    raw = "  12.5 "
    parse_raw_value(raw)
    assert raw == "  12.5 "


def test_pdf_extraction_exposes_only_direct_fields(root):
    prof = load_profile("pdf_extraction", "latest", root)
    extract = [f for f in prof["fields"] if f["role"] == "extract"]
    assert extract and all(f["availability"] == "D" for f in extract)
    # G fields may only be pipeline-generated; F (future source) fields never appear in an extraction profile
    assert all(f["role"] in ("generated", "system") for f in prof["fields"] if f["availability"] == "G")
    assert not any(f["availability"] == "F" for f in prof["fields"])
    assert not any(f["availability"] == "I" for f in extract)
    roles = prof["roles"]["provenance"]
    assert {"page", "quote", "document_id"} <= set(roles)
    assert not any(f["path"].startswith("omics.") for f in prof["fields"])


def test_omics_profile_extends_pdf_extraction(root):
    prof = load_profile("pdf_extraction_omics", "latest", root)
    base = load_profile("pdf_extraction", "latest", root)
    assert prof["extends_chain"][-1] == "pdf_extraction_omics" and "pdf_extraction" in prof["extends_chain"]
    paths = {f["path"] for f in prof["fields"]}
    assert {f["path"] for f in base["fields"]} <= paths
    assert any(p.startswith("omics.") for p in paths)


def test_profile_schema_restricts_fields(root):
    rc = resolve_schema("latest", root)
    compact = rc.profile("compact")
    assert len(compact["fields"]) == 158  # 157 v3 compact fields + common.schema_name (3.1.0)
    schema = rc.profile_schema("compact")
    assert set(schema["properties"]) <= set(rc.contract["groups"])


def test_every_profile_fill_rule_is_implemented(root):
    from pdf2jsonl_skill.fill_rules import IMPLEMENTED_RULES
    rc = resolve_schema("latest", root)
    for name in rc.profile_names():
        missing = set(rc.profile(name).get("fill_rules") or []) - set(IMPLEMENTED_RULES)
        assert not missing, (name, missing)
