"""Complete evidence chains: from a claim to the results and the experiments behind it.

A quote alone says that a sentence exists; it does not show that the paper did an experiment.  The records
already link claim -> evidence (observations / analysis results) and result -> method (experiment).  This module
walks those links, so a front end can show the chain instead of one quote, and can say which link is missing.

The walk is deterministic and only follows fields declared in the record contract.  It never infers a link that
the extraction did not record; an incomplete chain is reported as incomplete.
"""
from __future__ import annotations

from typing import Any

from .util import get_path

# link field -> (human label, whether it is evidence of the claim or a step behind it)
EVIDENCE_LINKS = (
    ("agent.evidence_record_ids", "数据/结果"),
    ("agent.validated_by_record_ids", "验证实验"),
    ("skills.method_record_ids", "实验/方法"),
)
STEP_LINKS = (
    ("agent.tests_record_ids", "检验假设"),
    ("agent.prerequisite_record_ids", "前置步骤"),
)
MAX_DEPTH = 3

KIND_LABEL = {
    "claim": "结论", "observation": "观测结果", "phenotype_observation": "表型观测",
    "environment_observation": "环境观测", "genotype_observation": "基因型观测",
    "analysis_result": "分析结果", "method": "实验/方法", "asset_manifest": "资产",
    "tool_spec": "工具",
}
ROLE_WITHOUT_CHAIN = {"background", "research_question", "objective", "hypothesis"}


def _items(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _summary(record: dict, depth: int, link_role: str = "", link_label: str = "") -> dict:
    common = record.get("common") or {}
    agent = record.get("agent") or {}
    skills = record.get("skills") or {}
    transform = record.get("transform") or {}
    kind = str(common.get("record_kind") or "")
    text = (agent.get("finding_text") or agent.get("actual_observation") or agent.get("experiment_objective")
            or agent.get("knowledge_gap") or "")
    method = skills.get("method_name") or ""
    if not text and method:
        software = " ".join(x for x in (skills.get("software_name"), skills.get("software_version")) if x)
        text = method + (f"（{software}）" if software else "")
    if not text:
        text = common.get("source_quote") or ""
    stats = {}
    for key in ("lod_score", "pve_percent", "p_value", "confidence_interval", "effect_estimate",
                "effect_unit", "effect_direction", "sample_size", "environment_count",
                "relation_evidence_type", "claim_strength", "validation_status"):
        value = agent.get(key) if key in agent else transform.get(key)
        if value not in (None, "", [], {}):
            stats[key] = value
    return {
        "record_id": common.get("record_id"),
        "record_kind": kind,
        "kind_label": KIND_LABEL.get(kind, kind or "记录"),
        "role": agent.get("statement_role"),
        "text": text,
        "method_name": method or None,
        "software": " ".join(x for x in (skills.get("software_name"), skills.get("software_version")) if x) or None,
        "materials": agent.get("experimental_materials") or None,
        "treatment": agent.get("treatment_groups") or None,
        "indicators": agent.get("observation_indicators") or None,
        "quote": common.get("source_quote"),
        "page": common.get("source_page"),
        "section": common.get("source_section"),
        "table_figure": common.get("source_table_figure"),
        "part": common.get("source_part"),
        "review_status": common.get("review_status"),
        "stats": stats or None,
        "depth": depth,
        "link_role": link_role,
        "link_label": link_label,
        "children": [],
    }


def _collect(record: dict, records: dict[str, dict], depth: int, seen: tuple[str, ...],
             link_role: str, link_label: str) -> dict:
    node = _summary(record, depth, link_role, link_label)
    if depth >= MAX_DEPTH:
        return node
    rid = (record.get("common") or {}).get("record_id")
    for path, label in EVIDENCE_LINKS + STEP_LINKS:
        for child_id in _items(get_path(record, path, None)):
            child = records.get(str(child_id))
            if not child or child_id in seen:
                continue
            if path in ("agent.evidence_record_ids", "agent.validated_by_record_ids"):
                role = "evidence"
            elif path == "skills.method_record_ids":
                role = "method"
            else:
                role = "step"
            node["children"].append(_collect(child, records, depth + 1, seen + (str(child_id),), role, label))
    return node


def _flatten(node: dict) -> list[dict]:
    out = [node]
    for child in node.get("children") or []:
        out.extend(_flatten(child))
    return out


def build_chain(records: list[dict] | dict[str, dict], anchor_id: str) -> dict:
    """The chain of one record.  ``complete`` needs both a data/result link and an experiment/method link."""
    by_id = records if isinstance(records, dict) else {
        str((r.get("common") or {}).get("record_id")): r for r in records
        if (r.get("common") or {}).get("record_id")
    }
    anchor_record = by_id.get(str(anchor_id))
    if not anchor_record:
        return {"anchor": None, "complete": False, "applicable": False,
                "missing": ["记录不存在"], "nodes": []}
    anchor = _collect(anchor_record, by_id, 0, (str(anchor_id),), "", "")
    nodes = _flatten(anchor)
    data = [n for n in nodes if n["depth"] == 1 and n["link_role"] == "evidence"]
    methods = [n for n in nodes if n["link_role"] == "method"]
    role = (anchor_record.get("agent") or {}).get("statement_role")
    applicable = role not in ROLE_WITHOUT_CHAIN
    missing = []
    if applicable:
        if not data:
            missing.append("未链接到数据/结果记录")
        if not methods:
            missing.append("未链接到实验/方法记录")
    return {
        "anchor": anchor,
        "nodes": nodes,
        "data_count": len(data),
        "method_count": len(methods),
        "complete": bool(data and methods),
        "applicable": applicable,
        "missing": missing,
    }


def chains_for(records: list[dict] | dict[str, dict], anchor_ids: list[str]) -> dict[str, dict]:
    return {str(rid): build_chain(records, str(rid)) for rid in anchor_ids}
