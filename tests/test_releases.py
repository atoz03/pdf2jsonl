"""Version resolution, release immutability and the dev (unreleased) channel."""
from __future__ import annotations

import json

import pytest

from breeding_contract import ContractError, available_versions, load_field_catalog, load_profile, resolve_schema
from breeding_contract.check import run_checks
from breeding_contract.release import release, verify_release
from breeding_contract.sources import load_sources
from breeding_contract.util import load_json

from helpers import PROBE, add_probe_field, bump_version


def test_latest_resolves_to_index_latest(root):
    index = load_json(root / "releases/index.json")
    rc = resolve_schema("latest", root)
    assert rc.version == index["latest"]
    assert rc.status == "released" and rc.requested == "latest"
    assert rc.identity()["release_sha256"]


@pytest.mark.parametrize("requested", ["3.0.0", "v3.0.0", "3.1.0"])
def test_explicit_versions(root, requested):
    rc = resolve_schema(requested, root)
    assert rc.version == requested.lstrip("v")
    assert rc.record_schema()["x-contract"]["version"] == rc.version


@pytest.mark.parametrize("bad", ["9.9.9", "3.1", "banana", "3.1.0-dev.deadbeef"])
def test_unknown_or_invalid_versions_fail(root, bad):
    with pytest.raises(ContractError):
        resolve_schema(bad, root)


def test_every_release_verifies(root):
    for v in available_versions(root):
        assert verify_release(root, v) == []


def test_dev_equals_release_when_sources_unchanged(root):
    src = load_sources(root)
    rc = resolve_schema("dev", root)
    assert rc.version == src.version and rc.status == "released" and rc.requested == "dev"


def test_public_api_loaders(root):
    cat = load_field_catalog("latest", root)
    prof = load_profile("pdf_extraction", "latest", root)
    assert len(cat["fields"]) == len(resolve_schema("latest", root).fields)
    assert prof["name"] == "pdf_extraction" and prof["is_extraction"]
    old = load_field_catalog("3.0.0", root)
    assert len(old["fields"]) == 259
    assert not any(f["path"].startswith("omics.") for f in old["fields"])


def test_tampered_release_is_rejected(repo_copy):
    target = repo_copy / "releases/3.0.0/record.schema.json"
    data = load_json(target)
    data["title"] += " (tampered)"
    target.write_text(json.dumps(data), encoding="utf-8")
    assert verify_release(repo_copy, "3.0.0")
    with pytest.raises(ContractError, match="integrity"):
        resolve_schema("3.0.0", repo_copy)


def test_editing_released_sources_is_an_error(repo_copy):
    add_probe_field(repo_copy, since="3.1.0")
    msgs = [f.message for f in run_checks(repo_copy) if f.level == "error" and f.check == "freshness"]
    assert any("releases are immutable" in m for m in msgs)
    with pytest.raises(ContractError, match="immutable"):
        release(repo_copy)


def test_new_field_flows_through_dev_then_release(repo_copy):
    add_probe_field(repo_copy, since="3.2.0")
    bump_version(repo_copy, "3.2.0")
    # before release: latest is unchanged, dev carries the field under an unreleased version
    assert PROBE not in {f["path"] for f in resolve_schema("latest", repo_copy).fields}
    dev = resolve_schema("dev", repo_copy)
    assert dev.status == "unreleased" and dev.version.startswith("3.2.0-dev.")
    assert PROBE in {f["path"] for f in dev.fields}
    assert PROBE in {f["path"] for f in dev.profile("pdf_extraction")["fields"]}
    warn = [f for f in run_checks(repo_copy) if f.check == "freshness"]
    assert warn and all(f.level == "warning" for f in warn)
    assert any(f.level == "error" and f.check == "freshness" for f in run_checks(repo_copy, strict=True))
    # release
    assert release(repo_copy) == ("3.2.0", "created")
    assert release(repo_copy) == ("3.2.0", "unchanged")
    rc = resolve_schema("latest", repo_copy)
    assert rc.version == "3.2.0" and PROBE in {f["path"] for f in rc.fields}
    # older releases stay byte-identical and resolvable
    assert PROBE not in {f["path"] for f in resolve_schema("3.1.0", repo_copy).fields}
    assert verify_release(repo_copy, "3.1.0") == []


def test_semver_discipline_between_releases(root):
    from breeding_contract.compat import required_bump
    old, new = resolve_schema("3.0.0", root).contract, resolve_schema("3.1.0", root).contract
    level, reasons = required_bump(old, new)
    assert level == "minor"  # 3.1.0 only adds; the 259 v3 fields are untouched
    assert not [m for lvl, m in reasons if lvl == "major"]


def test_breaking_change_needs_a_major_bump(repo_copy):
    import yaml

    from breeding_contract.util import load_yaml
    cat_path = repo_copy / "field_catalog/field_catalog.yaml"
    cat = load_yaml(cat_path)
    f = next(x for x in cat["fields"] if x["path"] == "common.sample_size")
    f["type"] = "string"
    cat_path.write_text(yaml.safe_dump(cat, allow_unicode=True, sort_keys=False), encoding="utf-8")
    bump_version(repo_copy, "3.2.0")
    errs = [f.message for f in run_checks(repo_copy) if f.check == "semver"]
    assert errs and "require major" in errs[0] and "common.sample_size" in errs[0]
    bump_version(repo_copy, "4.0.0")
    assert not [f for f in run_checks(repo_copy) if f.check == "semver"]
