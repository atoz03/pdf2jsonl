"""The simplified network view: only the three layers, with hidden relations counted, never dropped."""
from __future__ import annotations

import json

from scripts import make_network_dashboard, network_view


def record(rid="rec_1", **common):
    return {"common": {"record_id": rid, "source_page": 1, "source_section": "Results",
                       "source_quote": "qGY3.1 was associated with grain yield.", **common},
            "agent": {"lod_score": 8.4, "pve_percent": 18.6},
            "transform": {"claim_strength": "associational", "validation_status": "candidate"}}


def statement(sid, subject_type, subject, object_type, obj, predicate="was associated with",
              predicate_code="qtl_associated_with_trait", nature="associational", anchors=None):
    return {"statement_id": sid, "record_id": "rec_1", "subject_type": subject_type,
            "subject_mention": subject, "object_type": object_type, "object_mention": obj,
            "predicate": f"bdc:{predicate_code}" if predicate_code else "bdc:stated_relation",
            "predicate_mention": predicate, "predicate_status": "lexicon" if predicate_code else "verbatim",
            "relation_nature": nature, "source_page": 1, "source_quote": "qGY3.1 was associated with grain yield.",
            "anchors": anchors or {"subject": [0, 6], "predicate": [7, 27], "object": [28, 39]}}


def data(statements):
    return {
        "generated_at": "2026-11-09T00:00:00Z", "version": "3.8.0",
        "papers": [{
            "id": "p1", "title": "Paper one", "doi": "10.1/p1", "year": 2024, "crop": "rice",
            "pdf_url": "./p1.pdf",
            "runs": [{
                "run_id": "r1", "created_at": "2026-11-09T00:00:00Z",
                "records": [record(), record("rec_2", population_name="R1")],
                "derived": {"tables": {"statements": statements}},
                "source_parts": {"complete": True, "missing": []},
                "counts": {"pending": 1},
                "manifest": {"input": {"supplements": []}},
            }],
        }],
    }


def test_only_the_three_layers_are_kept_and_qtl_is_gene_layer():
    view = network_view.build_network(data([
        statement("s1", "qtl", "qGY3.1", "trait", "grain yield"),
        statement("s2", "gene", "G1", "gene", "G2", predicate="interacted with", predicate_code="", nature=None),
        statement("s3", "trait", "grain yield", "population", "R1", predicate="was measured in", predicate_code=""),
    ]))
    assert view["summary"]["edges"] == 2
    assert view["summary"]["hidden"] == 1
    assert view["summary"]["hidden_by_reason"] == {"基因层—基因层": 1}
    assert view["summary"]["layers"] == {"trait": 1, "gene": 1, "population": 1}
    edge = next(e for e in view["edges"] if e["pair"] == "表型—基因")
    assert edge["subject_layer"] == "gene"
    assert edge["subject_type"] == "qtl"
    assert edge["predicate_code"] == "qtl_associated_with_trait"
    assert edge["evidence_count"] == 1
    assert edge["evidence"][0]["section"] == "Results"
    assert edge["evidence"][0]["stats"]["lod_score"] == 8.4

    unencoded = next(e for e in view["edges"] if e["pair"] == "表型—种群")
    assert unencoded["predicate_code"] == ""
    assert unencoded["predicate"] == "was measured in"


def test_untyped_ends_are_counted_not_guessed():
    view = network_view.build_network(data([
        statement("s1", None, "The allele from Parent1", "trait", "grain yield"),
    ]))
    assert view["summary"]["edges"] == 0
    assert view["summary"]["hidden_by_reason"] == {"未识别实体类型": 1}


def test_infer_type_uses_record_fields_and_entity_markers():
    rec = record(population_name="R1")
    assert network_view.infer_entity_type(rec, "R1") == "population"
    rec2 = {"common": {"record_id": "x", "trait_names": ["grain yield"]},
            "transform": {"entity_links": [{"mention": "GY", "entity_type": "gene"}]}}
    assert network_view.infer_entity_type(rec2, "GY") == "gene"
    assert network_view.infer_entity_type(rec2, "unknown") is None


def test_network_label_is_case_and_space_insensitive():
    assert network_view.normalize_label("  Grain   Yield ") == "grain yield"
    assert network_view.layer_of("QTL") == "gene"
    assert network_view.layer_of("qtn") == "gene"
    assert network_view.layer_of("trait") == "trait"
    assert network_view.layer_of("method") is None


def test_paper_view_contains_package_and_evidence_chain():
    view = network_view.build_network(data([
        statement("s1", "qtl", "qGY3.1", "trait", "grain yield"),
    ]))
    paper = view["papers"][0]
    assert paper["package"]["package_format"] == 1
    assert paper["package"]["status"] in {"complete", "partial", "unverified", "not_submitted"}
    edge = paper["edges"][0]
    chain = edge["evidence"][0]["chain"]
    assert chain["anchor"]["record_id"] == "rec_1"
    assert "complete" in chain
    assert view["aggregate"]["relations"]


def test_render_embeds_escaped_json_and_page_markers():
    view = network_view.build_network(data([]))
    html = make_network_dashboard.render(view)
    assert 'id="network-data"' in html
    assert "表型—基因—种群" in html
    assert "关系清单" in html
    payload = html.split('<script id="network-data" type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(payload)["view_format"] == 2
    assert "</script>" not in payload


def test_render_escapes_script_close():
    view = network_view.build_network(data([]))
    view["papers"][0]["title"] = "</script><script>alert(1)</script>"
    html = make_network_dashboard.render(view)
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script" in html
