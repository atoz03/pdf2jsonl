"""The regression the feedback asks for, as a gate: the same papers through the old and the new contract, with the
main text alone and with the supplements, and every acceptance criterion checked.

The matrix lives in ``scripts/acceptance_matrix.py`` so the report (``scripts/acceptance_report.py``) and this test
assert the same facts; the report is generated, not hand-written.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="module")
def cells(root, tmp_path_factory):
    sys.path.insert(0, str(root / "scripts"))
    from acceptance_matrix import build_matrix

    return build_matrix(root, tmp_path_factory.mktemp("acceptance"))


def test_every_acceptance_criterion_passes(cells):
    sys.path.insert(0, str(cells[0].validation.__class__.__module__ and ""))  # noqa: F841 - keep import side effects
    from acceptance_matrix import criteria

    verdicts = criteria(cells)
    failed = [v for v in verdicts if not v["ok"]]
    assert not failed, "\n".join(f"{v['name']}: {v['detail']}" for v in failed)
    assert len(verdicts) >= 27


def test_the_matrix_covers_both_versions_and_both_inputs(cells):
    seen = {(c.version, c.supplement) for c in cells if c.paper == "heat"}
    assert seen == {("3.6.0", False), ("3.6.0", True), ("3.8.0", False), ("3.8.0", True)}
    # and the three focus fixtures ran under both versions
    for paper in ("gmoleo1", "qtl_overlap", "review"):
        assert {c.version for c in cells if c.paper == paper} == {"3.6.0", "3.8.0"}


def test_the_old_version_lacks_what_the_new_one_writes(cells):
    old = next(c for c in cells if c.paper == "gmoleo1" and c.version == "3.6.0")
    new = next(c for c in cells if c.paper == "gmoleo1" and c.version == "3.8.0")
    fields = ("relation_resolution", "claim_strength", "validation_status")
    assert not any((r.get("transform") or {}).get(f) for r in old.records for f in fields)
    assert any((r.get("transform") or {}).get(f) for r in new.records for f in fields)


def test_the_review_run_marks_every_record_as_a_paraphrase(cells):
    review = next(c for c in cells if c.paper == "review" and c.version == "3.8.0")
    origins = [((r.get("transform") or {}).get("evidence_origin")) for r in review.records]
    assert origins and set(origins) == {"review_report"}
