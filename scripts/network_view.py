"""Simplified phenotype–gene–population view over existing records.

The extraction contract is not changed here.  This module reads the latest run of each paper and builds:

* a per-paper view: only the phenotype–gene–population relations of that paper, each with a complete evidence
  chain (claim -> data/result -> experiment/method) and the paper's article package;
* a cross-paper network: the same relations clustered and deduplicated, with conflicts and confidence;
* a count of everything left out, so "not shown" never means "not extracted".

Evidence chains are built by ``breeding_contract.evidence_chain``; the package by
``breeding_contract.article_package``; the aggregation by ``breeding_contract.aggregate``.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from breeding_contract.aggregate import aggregate_relations
from breeding_contract.article_package import build_package
from breeding_contract.evidence_chain import build_chain
from breeding_contract.util import get_path

LAYERS = ("trait", "gene", "population")
LAYER_LABEL = {"trait": "表型", "gene": "基因层", "population": "种群"}
LAYER_ORDER = {name: i for i, name in enumerate(LAYERS)}

# QTL and QTN are different entity types in the records (and stay different in the detailed dashboard), but
# the research view puts all three on the gene layer.
ENTITY_LAYER = {"gene": "gene", "qtl": "gene", "qtn": "gene", "trait": "trait", "population": "population"}
ENTITY_LABEL = {"gene": "基因", "qtl": "QTL", "qtn": "QTN", "trait": "表型", "population": "种群"}

ENTITY_FIELDS = (
    ("trait", "common.trait_names"),
    ("gene", "common.gene_names"),
    ("qtl", "common.qtl_names"),
    ("qtn", "common.qtn_names"),
    ("population", "common.population_name"),
    ("germplasm", "common.germplasm_names"),
    ("variety", "common.variety_names"),
    ("marker", "common.marker_names"),
)

PAIR_LABEL = {
    frozenset(("trait", "gene")): "表型—基因",
    frozenset(("gene", "population")): "基因—种群",
    frozenset(("trait", "population")): "表型—种群",
}

NATURE_LABEL = {"causal": "因果", "associational": "相关", "structural": "结构", "descriptive": "描述",
                "unknown": "未判定"}

STAT_FIELDS = (
    "lod_score", "pve_percent", "p_value", "confidence_interval", "effect_estimate", "effect_unit",
    "effect_direction", "sample_size", "environment_count", "population_type", "chromosome",
    "locus_interval_start_bp", "locus_interval_end_bp", "genome_assembly", "relation_evidence_type",
)


def normalize_label(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def layer_of(entity_type: str | None) -> str | None:
    return ENTITY_LAYER.get(str(entity_type or "").casefold())


def pair_label(layer_a: str, layer_b: str) -> str:
    return PAIR_LABEL.get(frozenset((layer_a, layer_b)),
                          f"{LAYER_LABEL.get(layer_a, layer_a)}—{LAYER_LABEL.get(layer_b, layer_b)}")


def _items(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _json_obj(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def infer_entity_type(record: dict | None, mention: str | None) -> str | None:
    if not record or not mention:
        return None
    wanted = normalize_label(mention)
    for link in _items(get_path(record, "transform.entity_links", None)):
        if isinstance(link, dict) and normalize_label(link.get("mention")) == wanted and link.get("entity_type"):
            return str(link["entity_type"])
    for entity_type, path in ENTITY_FIELDS:
        values = _items(get_path(record, path, None))
        if any(normalize_label(value) == wanted for value in values):
            return entity_type
    return None


def _endpoint(statement: dict, record: dict | None, role: str) -> dict | None:
    mention = statement.get(f"{role}_mention")
    entity_type = statement.get(f"{role}_type") or infer_entity_type(record, mention)
    layer = layer_of(entity_type)
    label = str(mention or statement.get(f"{role}_id") or "").strip()
    if not label or not layer:
        return None
    return {"label": label, "type": str(entity_type), "layer": layer,
            "node": f"{layer}:{normalize_label(label)}"}


def _predicate(statement: dict) -> tuple[str, str, str]:
    """Returns (grouping key, display text, code)."""
    status = str(statement.get("predicate_status") or "")
    code = str(statement.get("predicate") or "")
    if code.startswith("bdc:"):
        code = code[4:]
    mention = str(statement.get("predicate_mention") or "").strip()
    if status in {"ontology", "reviewed", "lexicon"} and code and code != "stated_relation":
        return code, mention or code, code
    key = normalize_label(mention) or normalize_label(code) or "unlabelled"
    return "verbatim:" + key, mention or code or "（未给出谓语）", ""


def _evidence(statement: dict, record: dict | None, paper: dict, run: dict, chain: dict) -> dict:
    common = (record or {}).get("common") or {}
    agent = (record or {}).get("agent") or {}
    transform = (record or {}).get("transform") or {}
    source_parts = run.get("source_parts") or {}
    missing = source_parts.get("missing") or []
    if isinstance(missing, list):
        missing = [m.get("part") if isinstance(m, dict) else str(m) for m in missing]
    stats = {key: agent.get(key) for key in STAT_FIELDS if agent.get(key) not in (None, "", [], {})}
    for key in ("claim_strength", "validation_status", "relation_evidence_type"):
        if transform.get(key) not in (None, "", [], {}):
            stats[key] = transform[key]
    return {
        "statement_id": statement.get("statement_id"),
        "record_id": statement.get("record_id"),
        "paper_id": paper.get("id"),
        "paper_title": paper.get("title"),
        "paper_doi": paper.get("doi"),
        "paper_year": paper.get("year"),
        "pdf_url": paper.get("pdf_url"),
        "page": statement.get("source_page") if statement.get("source_page") is not None else common.get("source_page"),
        "section": common.get("source_section"),
        "table_figure": common.get("source_table_figure"),
        "part": common.get("source_part"),
        "quote": statement.get("source_quote") or common.get("source_quote"),
        "anchors": _json_obj(statement.get("anchors")),
        "predicate_mention": statement.get("predicate_mention"),
        "predicate_code": _predicate(statement)[2],
        "predicate_status": statement.get("predicate_status"),
        "relation_nature": statement.get("relation_nature"),
        "relation_polarity": statement.get("relation_polarity"),
        "assertion_mode": statement.get("relation_assertion_mode"),
        "hedge": statement.get("hedge"),
        "review_status": common.get("review_status"),
        "qc_failure_codes": common.get("qc_failure_codes") or [],
        "stats": stats,
        "population_name": common.get("population_name") or agent.get("applicable_population"),
        "source_complete": source_parts.get("complete"),
        "source_missing": missing,
        "statement_role": agent.get("statement_role"),
        "chain": chain,
    }


def _paper_meta(paper: dict, run: dict, package: dict) -> dict:
    records = run.get("records") or []
    common = (records[0].get("common") if records else {}) or {}
    source_parts = run.get("source_parts") or {}
    return {
        "id": paper.get("id"),
        "title": paper.get("title") or common.get("source_title") or paper.get("filename"),
        "doi": paper.get("doi") or common.get("source_doi"),
        "year": paper.get("year") or common.get("source_year"),
        "crop": paper.get("crop") or common.get("crop_name"),
        "pdf_url": paper.get("pdf_url"),
        "run_id": run.get("run_id"),
        "created_at": run.get("created_at"),
        "records": len(records),
        "pending": (run.get("counts") or {}).get("pending", 0),
        "source_complete": source_parts.get("complete") if isinstance(source_parts, dict) else None,
        "source_missing": [m.get("part") if isinstance(m, dict) else str(m) for m in source_parts.get("missing") or []],
        "supplements": [p.get("part") for p in ((run.get("manifest") or {}).get("input") or {}).get("supplements") or []
                        if isinstance(p, dict)],
        "package": package,
    }


def _supplement_inputs(paper: dict, run: dict) -> list[dict]:
    manifest_parts = {p.get("part"): p for p in (((run.get("manifest") or {}).get("input") or {}).get("supplements") or [])
                      if isinstance(p, dict)}
    out = []
    for part in paper.get("supplements") or []:
        if not isinstance(part, dict):
            continue
        base = manifest_parts.get(part.get("part"), {})
        out.append({**base, **part, "file_name": base.get("file_name") or part.get("filename")})
    for label, base in manifest_parts.items():
        if not any(x.get("part") == label for x in out):
            out.append(dict(base))
    return out


def _paper_view(paper: dict) -> dict | None:
    runs = [r for r in paper.get("runs") or [] if r.get("records")]
    if not runs:
        return None
    run = runs[0]
    records = {}
    for rec in run.get("records") or []:
        rid = (rec.get("common") or {}).get("record_id")
        if rid:
            records[rid] = rec
    input_info = ((run.get("manifest") or {}).get("input") or {})
    package = build_package(run.get("records") or [], input=input_info, source_parts=run.get("source_parts"),
                            pages=paper.get("pages"), supplements=_supplement_inputs(paper, run),
                            source_id=((run.get("records") or [{}])[0].get("common") or {}).get("source_id"),
                            title=paper.get("title"), doi=paper.get("doi"), year=paper.get("year"))
    meta = _paper_meta(paper, run, package)
    edges: dict[tuple, dict] = {}
    hidden: Counter = Counter()
    hidden_samples: list[dict] = []
    statements = ((run.get("derived") or {}).get("tables") or {}).get("statements") or []
    for statement in statements:
        record = records.get(statement.get("record_id"))
        subject = _endpoint(statement, record, "subject")
        obj = _endpoint(statement, record, "object")
        s_label = (subject or {}).get("label") or statement.get("subject_mention") or "（未识别主语）"
        o_label = (obj or {}).get("label") or statement.get("object_mention") or "（未识别宾语）"

        def note(reason: str) -> None:
            hidden[reason] += 1
            if len(hidden_samples) < 6:
                hidden_samples.append({"reason": reason, "subject": s_label,
                                       "predicate": statement.get("predicate_mention") or statement.get("predicate"),
                                       "object": o_label})

        if not subject or not obj:
            note("未识别实体类型")
            continue
        if subject["layer"] == obj["layer"]:
            note(f"{LAYER_LABEL[subject['layer']]}—{LAYER_LABEL[obj['layer']]}")
            continue
        key, predicate_label, predicate_code = _predicate(statement)
        edge_key = (subject["node"], key, obj["node"])
        edge = edges.setdefault(edge_key, {
            "id": "edge:" + hashlib.sha256("|".join(edge_key).encode()).hexdigest()[:16],
            "subject": subject["node"], "object": obj["node"],
            "subject_label": subject["label"], "object_label": obj["label"],
            "subject_type": subject["type"], "object_type": obj["type"],
            "subject_layer": subject["layer"], "object_layer": obj["layer"],
            "pair": pair_label(subject["layer"], obj["layer"]),
            "predicate": predicate_label, "predicate_code": predicate_code,
            "relation_nature": statement.get("relation_nature") or "unknown",
            "evidence": [], "paper_ids": [], "statement_ids": [],
        })
        chain = build_chain(records, str(statement.get("record_id")))
        evidence = _evidence(statement, record, paper, run, chain)
        if evidence["statement_id"] in edge["statement_ids"]:
            continue
        edge["statement_ids"].append(evidence["statement_id"])
        edge["evidence"].append(evidence)
        if paper.get("id") not in edge["paper_ids"]:
            edge["paper_ids"].append(paper.get("id"))
    for edge in edges.values():
        edge["evidence"].sort(key=lambda e: (e.get("paper_year") or 0, e.get("paper_title") or "",
                                             e.get("page") or 0), reverse=True)
        edge["paper_count"] = len(edge["paper_ids"])
        edge["evidence_count"] = len(edge["evidence"])
        edge["nature_label"] = NATURE_LABEL.get(edge["relation_nature"], edge["relation_nature"] or "未判定")
        chains = [e.get("chain") or {} for e in edge["evidence"]]
        edge["chain_complete"] = bool(chains) and all(c.get("complete") for c in chains)
        edge["chain_missing"] = sorted({m for c in chains for m in (c.get("missing") or [])})
    # The review queue contains every pending record of the paper, including records outside the triad:
    # a reviewer still has to see what the view does not show.  `in_scope` says whether it belongs to a
    # displayed relation.
    record_relations: dict[str, list[str]] = {}
    in_scope: set[str] = set()
    for edge in edges.values():
        label = f"{edge['subject_label']} — {edge['predicate']} — {edge['object_label']}"
        for ev in edge["evidence"]:
            ids = {str(ev.get("record_id"))}
            ids.update(str(n.get("record_id")) for n in ((ev.get("chain") or {}).get("nodes") or []))
            for rid in ids:
                in_scope.add(rid)
                bucket = record_relations.setdefault(rid, [])
                if label not in bucket:
                    bucket.append(label)
    review_queue = []
    kind_label = {"claim": "结论", "observation": "观测结果", "phenotype_observation": "表型观测",
                  "environment_observation": "环境观测", "genotype_observation": "基因型观测",
                  "analysis_result": "分析结果", "method": "实验/方法", "tool_spec": "工具"}
    for rid, rec in records.items():
        common = rec.get("common") or {}
        if common.get("review_status") != "pending_review":
            continue
        agent = rec.get("agent") or {}
        skills = rec.get("skills") or {}
        text = (agent.get("finding_text") or agent.get("actual_observation") or agent.get("experiment_objective")
                or agent.get("knowledge_gap") or skills.get("method_name") or common.get("source_quote") or "")
        review_queue.append({
            "record_id": rid,
            "record_kind": common.get("record_kind"),
            "kind_label": kind_label.get(str(common.get("record_kind")), common.get("record_kind") or "记录"),
            "text": text,
            "quote": common.get("source_quote"),
            "section": common.get("source_section"),
            "page": common.get("source_page"),
            "table_figure": common.get("source_table_figure"),
            "part": common.get("source_part"),
            "qc_failure_codes": common.get("qc_failure_codes") or [],
            "in_scope": rid in in_scope,
            "relations": record_relations.get(rid, []),
        })
    review_queue.sort(key=lambda x: (not x["in_scope"], x["page"] or 0, x["record_id"]))
    return {**meta, "edges": sorted(edges.values(), key=lambda e: (
        LAYER_ORDER.get(e["subject_layer"], 9), LAYER_ORDER.get(e["object_layer"], 9),
        -e["evidence_count"], e["subject_label"].casefold(), e["predicate"].casefold(),
        e["object_label"].casefold())), "hidden": dict(hidden.most_common()), "hidden_samples": hidden_samples,
        "review_queue": review_queue}


def _relation_map(aggregate: dict) -> dict[tuple, dict]:
    out = {}
    for relation in aggregate.get("relations") or []:
        key = (relation.get("subject"), relation.get("predicate_code") or relation.get("predicate"),
               relation.get("object"))
        out[key] = relation
    return out


def build_network(data: dict) -> dict:
    """Per-paper views plus the merged three-layer network and its aggregation."""
    paper_views = [v for v in (_paper_view(p) for p in data.get("papers") or []) if v]
    aggregate = aggregate_relations(paper_views)
    relation_map = _relation_map(aggregate)
    for view in paper_views:
        for edge in view.get("edges") or []:
            relation = relation_map.get((edge["subject"], edge["predicate_code"] or edge["predicate"],
                                         edge["object"]))
            if relation:
                edge.update({"relation_id": relation["relation_id"], "confidence": relation["confidence"],
                             "confidence_basis": relation["confidence_basis"],
                             "conflict_ids": relation["conflict_ids"]})
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    hidden: Counter = Counter()
    hidden_samples: list[dict] = []
    for view in paper_views:
        hidden.update(view.get("hidden") or {})
        hidden_samples.extend(view.get("hidden_samples") or [])
        for edge in view.get("edges") or []:
            key = (edge["subject"], edge["predicate_code"] or edge["predicate"], edge["object"])
            target = edges.setdefault(key, {
                "id": edge["id"], "subject": edge["subject"], "object": edge["object"],
                "subject_label": edge["subject_label"], "object_label": edge["object_label"],
                "subject_type": edge["subject_type"], "object_type": edge["object_type"],
                "subject_layer": edge["subject_layer"], "object_layer": edge["object_layer"],
                "pair": edge["pair"], "predicate": edge["predicate"], "predicate_code": edge["predicate_code"],
                "relation_nature": edge["relation_nature"], "evidence": [], "paper_ids": [],
                "statement_ids": [],
            })
            for ev in edge["evidence"]:
                if ev.get("statement_id") in target["statement_ids"]:
                    continue
                target["statement_ids"].append(ev.get("statement_id"))
                target["evidence"].append(ev)
            for pid in edge["paper_ids"]:
                if pid not in target["paper_ids"]:
                    target["paper_ids"].append(pid)
            relation = relation_map.get(key)
            if relation:
                target.update({"relation_id": relation["relation_id"], "confidence": relation["confidence"],
                               "confidence_basis": relation["confidence_basis"],
                               "conflict_ids": relation["conflict_ids"]})
            for end in ("subject", "object"):
                label, layer, etype = edge[f"{end}_label"], edge[f"{end}_layer"], edge[f"{end}_type"]
                node = nodes.setdefault(edge[end], {"id": edge[end], "label": label, "layer": layer,
                                                    "kinds": [], "paper_ids": [], "evidence": 0})
                if etype not in node["kinds"]:
                    node["kinds"].append(etype)
                for pid in edge["paper_ids"]:
                    if pid not in node["paper_ids"]:
                        node["paper_ids"].append(pid)
                node["evidence"] += 1
    for node in nodes.values():
        node["degree"] = sum(1 for edge in edges.values()
                             if edge["subject"] == node["id"] or edge["object"] == node["id"])
        node["kinds"].sort(key=lambda x: (ENTITY_LABEL.get(x, x), x))
        node["kind_label"] = " · ".join(ENTITY_LABEL.get(k, k) for k in node["kinds"])
        node["papers"] = len(node["paper_ids"])
    edge_list = []
    for edge in edges.values():
        edge["evidence"].sort(key=lambda e: (e.get("paper_year") or 0, e.get("paper_title") or "",
                                             e.get("page") or 0), reverse=True)
        edge["paper_count"] = len(edge["paper_ids"])
        edge["evidence_count"] = len(edge["evidence"])
        edge["nature_label"] = NATURE_LABEL.get(edge["relation_nature"], edge["relation_nature"] or "未判定")
        chains = [e.get("chain") or {} for e in edge["evidence"]]
        edge["chain_complete"] = bool(chains) and all(c.get("complete") for c in chains)
        edge["chain_missing"] = sorted({m for c in chains for m in (c.get("missing") or [])})
        edge_list.append(edge)
    edge_list.sort(key=lambda e: (LAYER_ORDER.get(e["subject_layer"], 9), LAYER_ORDER.get(e["object_layer"], 9),
                                  -e["evidence_count"], e["subject_label"].casefold(),
                                  e["predicate"].casefold(), e["object_label"].casefold()))
    node_list = sorted(nodes.values(), key=lambda n: (LAYER_ORDER.get(n["layer"], 9), -n["degree"],
                                                      n["label"].casefold()))
    layer_counts = Counter(n["layer"] for n in node_list)
    return {
        "view_format": 2,
        "generated_at": data.get("generated_at"),
        "contract_version": data.get("version"),
        "summary": {
            "papers": len(paper_views),
            "nodes": len(node_list),
            "edges": len(edge_list),
            "evidence": sum(e["evidence_count"] for e in edge_list),
            "hidden": sum(hidden.values()),
            "hidden_by_reason": dict(hidden.most_common()),
            "layers": {layer: layer_counts.get(layer, 0) for layer in LAYERS},
            "confidence": (aggregate.get("counts") or {}).get("confidence") or {},
            "conflicts": len(aggregate.get("conflicts") or []),
        },
        "hidden_samples": hidden_samples[:12],
        "papers": sorted(paper_views, key=lambda p: (p.get("title") or "").casefold()),
        "nodes": node_list,
        "edges": edge_list,
        "aggregate": aggregate,
    }
