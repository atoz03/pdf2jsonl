"""The catalog must carry the verified v3 definitions verbatim (sources/fields_v3 is the evidence)."""
from __future__ import annotations

import re

import pytest

from breeding_contract.util import load_yaml

ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|(.*)\|\s*$")


def md_rows(path):
    rows = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        m = ROW.match(line)
        if m:
            cells = [c.strip() for c in m.group(2).split("|")]
            rows[m.group(1)] = (n, cells)
    return rows


@pytest.fixture(scope="module")
def catalog(root):
    return load_yaml(root / "field_catalog/field_catalog.yaml")


@pytest.fixture(scope="module")
def full_rows(root):
    return md_rows(root / "sources/fields_v3/breeding_fields_259_final.md")


def test_v3_field_set_is_exactly_the_259(catalog, full_rows):
    v3 = [f for f in catalog["fields"] if "fields_v3" in (f.get("origin") or [])]
    assert len(full_rows) == 259
    assert {f["path"] for f in v3} == set(full_rows)
    assert all(f["maturity"] == "verified" and f["since"] == "3.0.0" for f in v3)
    # every non-v3 field is a 3.1.0+ addition and marked provisional (never "verified")
    for f in catalog["fields"]:
        if "fields_v3" not in (f.get("origin") or []):
            assert f["maturity"] == "provisional", f["path"]
            assert f["since"] != "3.0.0", f["path"]


def test_v3_definitions_verbatim(catalog, full_rows):
    for f in catalog["fields"]:
        if "fields_v3" not in (f.get("origin") or []):
            continue
        line, (ftype, avail, req, data_source, downstream, definition) = full_rows[f["path"]]
        assert f["source_ref"] == f"sources/fields_v3/breeding_fields_259_final.md#L{line}", f["path"]
        assert (f["type"], f["availability"], f["required"]) == (ftype, avail, req), f["path"]
        assert f["definition_zh"] == definition, f["path"]
        assert f["data_source_zh"] == data_source, f["path"]
        assert f["downstream_zh"] == downstream, f["path"]


def test_compact_profile_matches_compact_table(root):
    compact = md_rows(root / "sources/fields_v3/breeding_fields_compact_final.md")
    prof = load_yaml(root / "profiles/compact.yaml")
    assert len(compact) == 157
    assert set(prof["selection"]["fields"]) == set(compact)
    # compact rows repeat the full definitions; they must not contradict the catalog
    full = md_rows(root / "sources/fields_v3/breeding_fields_259_final.md")
    for path, (_, cells) in compact.items():
        assert cells[:3] == full[path][1][:3], path


def test_availability_and_required_codes(catalog):
    assert {f["availability"] for f in catalog["fields"]} <= set("DNIGF")
    assert {f["required"] for f in catalog["fields"]} <= set("YCN")


def test_sources_are_byte_identical_to_the_manifest(root):
    """sources/ are immutable inputs: every hash listed in sources/SOURCES.md must still match."""
    import hashlib
    text = (root / "sources/SOURCES.md").read_text(encoding="utf-8")
    listed = re.findall(r"^\| `([^`]+)` \|.*?`([0-9a-f]{64})` \|$", text, re.M)
    assert len(listed) >= 12
    for rel, digest in listed:
        path = root / "sources" / rel
        if not path.exists() and rel.startswith("archives/"):
            continue  # archives are optional in slim checkouts
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, rel
