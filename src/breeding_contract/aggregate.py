"""Cross-paper relation aggregation: cluster, deduplicate, expose conflicts and a deterministic confidence.

This is deliberately conservative:

* clustering uses the normalized entity nodes and the predicate code (or the verbatim predicate when no code
  exists), so the same relation reported by three papers is one row with three evidence chains;
* conflicts are only reported when the records state opposite directions; missing context is a note, not a
  conflict;
* confidence is a rule over evidence chains and packages, with the reasons written next to it.  It is not a
  model judgement and it never deletes an evidence item.

The output is a derived view; the atomic records remain the source of truth.
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict

AGGREGATE_FORMAT = 1
INVERSE_PREDICATES = {
    frozenset(("locus_increases_trait", "locus_decreases_trait")),
    frozenset(("gene_suppresses_gene", "gene_suppressed_by_gene")),
}
DIRECTION_VALUES = {"increase": "increase", "increased": "increase", "up": "increase", "上调": "increase",
                    "decrease": "decrease", "decreased": "decrease", "down": "decrease", "下调": "decrease"}


def _key(edge: dict) -> tuple[str, str, str]:
    return (str(edge.get("subject")), str(edge.get("predicate_code") or edge.get("predicate")),
            str(edge.get("object")))


def _direction(edge: dict, evidence: dict) -> str | None:
    polarity = str(evidence.get("relation_polarity") or "")
    return DIRECTION_VALUES.get(polarity) or DIRECTION_VALUES.get(str((evidence.get("stats") or {}).get("effect_direction") or ""))


def aggregate_relations(papers: list[dict]) -> dict:
    """Cluster the triad edges of several papers into relation rows, conflicts and confidence."""
    clusters: dict[tuple, dict] = {}
    for paper in papers:
        for edge in paper.get("edges") or []:
            key = _key(edge)
            cluster = clusters.setdefault(key, {
                "relation_id": "rel_" + hashlib.sha256("|".join(key).encode()).hexdigest()[:16],
                "key": "|".join(key),
                "subject": edge.get("subject"), "subject_label": edge.get("subject_label"),
                "subject_type": edge.get("subject_type"), "subject_layer": edge.get("subject_layer"),
                "object": edge.get("object"), "object_label": edge.get("object_label"),
                "object_type": edge.get("object_type"), "object_layer": edge.get("object_layer"),
                "predicate": edge.get("predicate"), "predicate_code": edge.get("predicate_code"),
                "pair": edge.get("pair"), "relation_nature": edge.get("relation_nature"),
                "evidence": [], "paper_ids": [], "directions": set(),
            })
            for ev in edge.get("evidence") or []:
                item = {**ev, "paper_id": paper.get("id"), "paper_title": paper.get("title"),
                        "paper_year": paper.get("year"), "paper_doi": paper.get("doi"),
                        "package_status": (paper.get("package") or {}).get("status")}
                cluster["evidence"].append(item)
                if paper.get("id") not in cluster["paper_ids"]:
                    cluster["paper_ids"].append(paper.get("id"))
                direction = _direction(edge, ev)
                if direction:
                    cluster["directions"].add(direction)

    relations = []
    conflicts = []
    by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for cluster in clusters.values():
        by_pair[(cluster["subject"], cluster["object"])].append(cluster)
    for pair, group in by_pair.items():
        for i, first in enumerate(group):
            for second in group[i + 1:]:
                a, b = first.get("predicate_code"), second.get("predicate_code")
                inverse = bool(a and b and frozenset((a, b)) in INVERSE_PREDICATES)
                opposite = bool(first["directions"] and second["directions"]
                                and first["directions"] != second["directions"])
                if inverse or opposite:
                    cid = "con_" + hashlib.sha256((first["relation_id"] + second["relation_id"]).encode()).hexdigest()[:16]
                    conflict = {
                        "conflict_id": cid, "type": "direction",
                        "message": f"{first['subject_label']} 与 {first['object_label']} 的效应方向相反",
                        "relation_ids": [first["relation_id"], second["relation_id"]],
                        "paper_ids": sorted(set(first["paper_ids"] + second["paper_ids"])),
                        "evidence_ids": [e.get("statement_id") for e in first["evidence"] + second["evidence"]
                                         if e.get("statement_id")],
                    }
                    conflicts.append(conflict)
                    first.setdefault("conflict_ids", []).append(cid)
                    second.setdefault("conflict_ids", []).append(cid)

    for cluster in clusters.values():
        evidence = cluster["evidence"]
        chains = [e.get("chain") for e in evidence if isinstance(e.get("chain"), dict)]
        complete_chains = [c for c in chains if c.get("complete")]
        package_bad = [e.get("paper_title") for e in evidence
                       if e.get("package_status") in ("partial", "unverified", "not_submitted")]
        conflict_ids = cluster.get("conflict_ids") or []
        basis = []
        if conflict_ids:
            basis.append("存在未消解的方向冲突")
        if len(cluster["paper_ids"]) >= 2:
            basis.append(f"{len(cluster['paper_ids'])} 篇独立论文")
        else:
            basis.append("仅 1 篇论文")
        if complete_chains and len(complete_chains) == len(chains):
            basis.append("每条证据链都包含结果和实验/方法")
        elif chains:
            basis.append(f"{len(chains) - len(complete_chains)} 条证据链缺少结果或实验/方法")
        else:
            basis.append("没有可检查的证据链")
        if package_bad:
            basis.append("部分证据来自文章包不完整的论文")
        if conflict_ids or len(complete_chains) != len(chains) or package_bad:
            confidence = "C"
        elif len(cluster["paper_ids"]) >= 2:
            confidence = "A"
        else:
            confidence = "B"
        cluster.update({
            "evidence_count": len(evidence),
            "paper_count": len(cluster["paper_ids"]),
            "confidence": confidence,
            "confidence_basis": basis,
            "conflict_ids": conflict_ids,
            "directions": sorted(cluster["directions"]),
        })
        evidence.sort(key=lambda e: (e.get("paper_year") or 0, e.get("paper_title") or "",
                                     e.get("page") or 0), reverse=True)
        relations.append(cluster)

    relations.sort(key=lambda r: (-r["evidence_count"], r["subject_label"] or "", r["predicate"] or "",
                                  r["object_label"] or ""))
    counts = Counter(r["confidence"] for r in relations)
    return {
        "aggregate_format": AGGREGATE_FORMAT,
        "relations": relations,
        "conflicts": conflicts,
        "counts": {
            "papers": len(papers),
            "relations": len(relations),
            "evidence": sum(r["evidence_count"] for r in relations),
            "conflicts": len(conflicts),
            "confidence": dict(counts),
        },
    }
