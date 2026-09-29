"""The Skill follows the repository: a catalog change reaches the brief via dev, and latest after a release."""
from __future__ import annotations

import json

from breeding_contract.release import release

from conftest import EXAMPLE_PDF, run_skill
from helpers import PROBE, add_probe_field, bump_version


def brief(repo, *args):
    r = run_skill(repo, "brief", *args)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_brief_is_rendered_from_the_resolved_profile(root):
    text = brief(root)
    resolved = json.loads(run_skill(root, "resolve").stdout)
    assert resolved["schema_version"] in text and "{{" not in text
    assert "common.source_quote" in text and "omics." not in text
    assert "omics.omics_type" in brief(root, "--profile", "pdf_extraction_omics")
    old = brief(root, "--schema-version", "3.0.0")
    assert "common.source_journal" not in old and "common.source_journal" in text


def test_catalog_change_reaches_the_skill(repo_copy, tmp_path):
    add_probe_field(repo_copy, since="3.2.0")
    bump_version(repo_copy, "3.2.0")
    assert PROBE not in brief(repo_copy)  # latest release is unchanged
    refused = run_skill(repo_copy, "brief", "--schema-version", "dev")
    assert refused.returncode == 1 and "unreleased" in refused.stderr
    dev = brief(repo_copy, "--schema-version", "dev", "--allow-unreleased")
    assert PROBE in dev and "3.2.0-dev." in dev
    # a dev run stamps the unreleased version into every record
    run = run_skill(repo_copy, "run", str(EXAMPLE_PDF), "--backend", "mock", "--schema-version", "dev",
                    "--allow-unreleased", "--out-dir", str(tmp_path / "dev"))
    assert run.returncode == 0, run.stderr
    rec = json.loads((tmp_path / "dev/synthetic_rice_qtl.jsonl").read_text().splitlines()[0])
    assert rec["common"]["schema_version"].startswith("3.2.0-dev.")
    # after `bdc release` the default (latest) picks the field up without touching the Skill
    assert release(repo_copy)[1] == "created"
    assert PROBE in brief(repo_copy)
    assert json.loads(run_skill(repo_copy, "resolve").stdout)["schema_version"] == "3.2.0"


def test_skill_refuses_an_unsupported_major(monkeypatch, root):
    import pytest

    from pdf2jsonl_skill import pipeline
    monkeypatch.setattr(pipeline, "SUPPORTED_MAJORS", (4,))
    with pytest.raises(pipeline.PipelineError, match="major"):
        pipeline.resolve_contract("latest", "pdf_extraction", False)
