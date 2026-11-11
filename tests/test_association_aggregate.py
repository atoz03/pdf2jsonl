"""Cross-paper aggregation of 4.0.0 association events."""
from __future__ import annotations

import copy

from breeding_contract.association_aggregate import aggregate_associations


def assoc(paper: str, *, direction: str = "increase", locus: str = "urn:gene:RBL1",
          trait: str = "urn:trait:lesion", population: str | None = None,
          evidence: bool = True, study: bool = True) -> dict:
    common = {
        "record_id": f"rec_{paper}_{population or 'p1'}",
        "record_kind": "association",
        "source_id": f"doi:{paper}", "source_doi": paper,
        "source_title": f"Paper {paper}", "source_year": 2025,
        "study_id": f"study:{paper}" if study else None,
        "population_id": population or f"pop:{paper}",
        "population_name": population or "panel",
        "environment_id": "env:greenhouse",
        "trait_id": trait, "trait_names": ["disease resistance"],
        "locus_id": locus, "locus_type": "gene",
        "association_kind": "linkage_mapping",
        "field_evidence": ([{"field": "common.locus_id", "locator": "page=1;section=Results",
                             "quote": "RBL1", "page": 1}] if evidence else []),
    }
    if not study:
        common.pop("study_id")
    return {"common": common, "agent": {"effect_direction": direction}}


def test_same_trait_and_locus_is_one_relation_with_two_papers():
    agg = aggregate_associations([assoc("10.1/a"), assoc("10.1/b", population="pop:b")])
    assert agg["counts"] == {"papers": 2, "relations": 1, "associations": 2, "evidence": 2,
                             "conflicts": 0, "confidence": {"A": 1}}
    relation = agg["relations"][0]
    assert relation["paper_count"] == 2 and relation["association_count"] == 2
    assert relation["confidence"] == "A"
    assert {c["population_name"] for c in relation["contexts"]} == {"panel", "pop:b"}


def test_opposite_direction_is_a_conflict_and_never_deleted():
    agg = aggregate_associations([assoc("10.1/a"), assoc("10.1/b", direction="decrease")])
    assert agg["counts"]["conflicts"] == 1
    assert agg["counts"]["confidence"] == {"C": 1}
    relation = agg["relations"][0]
    assert relation["confidence"] == "C"
    assert relation["directions"] == ["decrease", "increase"]
    assert relation["evidence_count"] == 2
    assert agg["conflicts"][0]["relation_id"] == relation["relation_id"]


def test_single_paper_is_b_and_different_locus_is_separate():
    agg = aggregate_associations([assoc("10.1/a"), assoc("10.2/b", locus="urn:gene:OTHER")])
    assert agg["counts"]["relations"] == 2
    assert agg["counts"]["confidence"] == {"B": 2}


def test_missing_context_or_evidence_is_c():
    agg = aggregate_associations([assoc("10.1/a", study=False), assoc("10.2/b", evidence=False)])
    assert agg["counts"]["confidence"] == {"C": 1}
    relation = agg["relations"][0]
    assert relation["missing_context_ids"]
    assert relation["confidence_basis"]
    assert relation["evidence_count"] == 1


def test_rbl1_multi_paper_demo_reaches_a_b_c(root, tmp_path):
    from breeding_contract.rbl1_case import build_case
    from scripts.make_rbl1_aggregate_demo import build as build_multi

    build_case(None, root / "examples/rbl1/primers.csv", tmp_path / "case")
    agg = build_multi(tmp_path / "case", tmp_path / "multi")
    assert agg["counts"] == {"papers": 5, "relations": 3, "associations": 7, "evidence": 22,
                             "conflicts": 1, "confidence": {"A": 1, "B": 1, "C": 1}}
    assert agg["conflicts"] and agg["conflicts"][0]["type"] == "direction"
    by_trait = {tuple(r["trait_names"]): r for r in agg["relations"]}
    assert by_trait[("disease resistance", "lesion mimic")]["confidence"] == "C"
    assert by_trait[("multipathogen resistance", "yield")]["confidence"] == "A"
    assert by_trait[("plant height",)]["confidence"] == "B"
