"""The curated real-paper rice stress panel (page-1 associations) builds and aggregates."""
from __future__ import annotations

from breeding_contract.api import resolve_schema
from scripts.build_rice_stress_panel import build


def test_panel_builds_without_pdfs_and_keeps_context(root, tmp_path):
    agg = build(root / "examples/rice_stress_panel/panel.csv", None, tmp_path, None)
    assert agg["counts"] == {"papers": 13, "relations": 13, "associations": 13, "evidence": 39,
                             "conflicts": 0, "confidence": {"B": 13}}
    records = [line for line in (tmp_path / "panel_records.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    assert len(records) == 13
    validator = resolve_schema("4.0.0").validator("association_extraction")
    assert all(validator.validate(__import__("json").loads(line)).valid for line in records)
    # Shared traits remain separate loci but are visible as a paper-trait graph through the aggregate contexts.
    traits = {tuple(r["trait_names"]) for r in agg["relations"]}
    assert ("blast resistance",) in traits
    assert ("bacterial blight resistance",) in traits
    assert ("chilling tolerance",) in traits


def test_dashboard_uses_panel_for_graph_and_aggregate(root, tmp_path):
    from breeding_contract.rbl1_case import build_case
    from scripts.make_rbl1_dashboard import build as build_dashboard

    build_case(None, root / "examples/rbl1/primers.csv", tmp_path / "case")
    build(root / "examples/rice_stress_panel/panel.csv", None, tmp_path / "panel", tmp_path / "case")
    out, payload = build_dashboard(tmp_path / "case", tmp_path / "dashboard.html",
                                   tmp_path / "panel" / "records.jsonl")
    text = out.read_text(encoding="utf-8")
    assert payload["aggregate"]["counts"]["papers"] == 14
    assert "paper-graph" in text and "多文聚合" in text and "论文—性状关系图" in text
    assert "lesion mimic" in text and "bacterial blight resistance" in text
