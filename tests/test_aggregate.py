"""Cross-paper aggregation: one relation per cluster, evidence kept, conflicts and confidence visible."""
from __future__ import annotations

from breeding_contract.aggregate import aggregate_relations


def evidence(sid, paper, chain_complete=True, polarity=None, direction=None):
    return {
        "statement_id": sid, "paper_id": paper, "paper_title": paper, "paper_year": 2026,
        "rel_id": sid, "relation_polarity": polarity,
        "stats": {"effect_direction": direction} if direction else {},
        "chain": {"complete": chain_complete, "missing": [] if chain_complete else ["未链接到实验/方法记录"]},
    }


def edge(subject, predicate_code, obj, paper, evidence_items, nature="associational"):
    return {
        "id": f"edge:{paper}:{subject}:{predicate_code}", "subject": subject, "subject_label": subject.split(":", 1)[-1],
        "subject_type": "gene", "subject_layer": "gene", "object": obj, "object_label": obj.split(":", 1)[-1],
        "object_type": "trait", "object_layer": "trait", "pair": "表型—基因",
        "predicate": predicate_code, "predicate_code": predicate_code, "relation_nature": nature,
        "evidence": evidence_items, "paper_ids": [paper], "evidence_count": len(evidence_items),
    }


def paper(pid, edges, package="complete"):
    return {"id": pid, "title": pid, "doi": "10.1/" + pid, "year": 2026,
            "package": {"status": package}, "edges": edges}


def test_one_relation_across_two_papers_is_A_with_two_evidence_items():
    result = aggregate_relations([
        paper("p1", [edge("gene:g1", "gene_associated_with_trait", "trait:yield", "p1", [evidence("s1", "p1")])]),
        paper("p2", [edge("gene:g1", "gene_associated_with_trait", "trait:yield", "p2", [evidence("s2", "p2")])]),
    ])
    assert result["counts"]["relations"] == 1
    assert result["counts"]["papers"] == 2
    relation = result["relations"][0]
    assert relation["paper_count"] == 2
    assert relation["evidence_count"] == 2
    assert relation["confidence"] == "A"
    assert result["conflicts"] == []


def test_single_paper_is_B():
    result = aggregate_relations([
        paper("p1", [edge("gene:g1", "gene_associated_with_trait", "trait:yield", "p1", [evidence("s1", "p1")])]),
    ])
    assert result["relations"][0]["confidence"] == "B"


def test_incomplete_chain_is_C():
    result = aggregate_relations([
        paper("p1", [edge("gene:g1", "gene_associated_with_trait", "trait:yield", "p1",
                          [evidence("s1", "p1", chain_complete=False)])]),
    ])
    assert result["relations"][0]["confidence"] == "C"
    assert any("证据链" in x for x in result["relations"][0]["confidence_basis"])


def test_opposite_direction_is_a_conflict_and_C():
    result = aggregate_relations([
        paper("p1", [edge("gene:g1", "locus_increases_trait", "trait:yield", "p1", [evidence("s1", "p1", direction="increase")])]),
        paper("p2", [edge("gene:g1", "locus_decreases_trait", "trait:yield", "p2", [evidence("s2", "p2", direction="decrease")])]),
    ])
    assert len(result["conflicts"]) == 1
    assert result["counts"]["conflicts"] == 1
    assert {r["confidence"] for r in result["relations"]} == {"C"}
    assert all(r["conflict_ids"] for r in result["relations"])


def test_partial_package_is_C():
    result = aggregate_relations([
        paper("p1", [edge("gene:g1", "gene_associated_with_trait", "trait:yield", "p1", [evidence("s1", "p1")])],
              package="partial"),
    ])
    assert result["relations"][0]["confidence"] == "C"
    assert any("文章包" in x for x in result["relations"][0]["confidence_basis"])
