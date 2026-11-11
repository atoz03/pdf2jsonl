"""Cross-paper aggregation of 4.0.0 association events.

The 3.x ``aggregate_relations`` works on derived triad edges.  This module works one level lower: it clusters
``association`` records by trait + locus, keeps every study/population/environment context, and computes a
conservative A/B/C confidence.  It is deliberately not a model judgement and never drops evidence.

Rules:

* the same trait + locus reported by two papers is one relation with two papers and all evidence;
* a second population or environment is context, not a conflict;
* a conflict exists only when the papers explicitly state opposite effect directions;
* any missing context, missing field evidence, or unresolved conflict makes the relation C.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter


AGGREGATE_FORMAT = 1
DIRECTION_WORDS = {
    "increase": "increase", "increased": "increase", "up": "increase", "上调": "increase", "增加": "increase",
    "decrease": "decrease", "decreased": "decrease", "down": "decrease", "下调": "decrease", "降低": "decrease",
}


def _text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    return re.sub(r"\s+", " ", value).strip()


def _trait_key(a: dict) -> str:
    c = a.get("common") or {}
    return _text(c.get("trait_id") or "|".join(sorted(c.get("trait_names") or [])))


def _key(a: dict) -> tuple[str, str, str]:
    c = a.get("common") or {}
    return (_trait_key(a), _text(c.get("locus_id") or ""), _text(c.get("locus_type") or ""))


def _paper(a: dict) -> dict:
    c = a.get("common") or {}
    return {
        "id": c.get("source_id") or c.get("source_doi") or c.get("source_title"),
        "title": c.get("source_title"),
        "doi": c.get("source_doi"),
        "year": c.get("source_year"),
    }


def _direction(a: dict) -> str | None:
    c = a.get("common") or {}
    agent = a.get("agent") or {}
    raw = _text(str(agent.get("effect_direction") or c.get("effect_direction") or ""))
    return DIRECTION_WORDS.get(raw)


def _evidence(a: dict) -> list[dict]:
    c = a.get("common") or {}
    return [{**e, "association_id": c.get("record_id"), "paper_id": _paper(a)["id"]}
            for e in c.get("field_evidence") or []]


def aggregate_associations(records: list[dict]) -> dict:
    """Cluster association records across papers and return relations, contexts, conflicts and confidence."""
    associations = [r for r in records if (r.get("common") or {}).get("record_kind") == "association"]
    clusters: dict[tuple, dict] = {}
    for rec in associations:
        c = rec["common"]
        key = _key(rec)
        cluster = clusters.setdefault(key, {
            "relation_id": "assoc_" + hashlib.sha256("|".join(key).encode()).hexdigest()[:16],
            "key": "|".join(key),
            "trait_id": c.get("trait_id"),
            "trait_names": sorted(c.get("trait_names") or []),
            "locus_id": c.get("locus_id"),
            "locus_type": c.get("locus_type"),
            "papers": [], "contexts": [], "evidence": [], "directions": set(),
        })
        paper = _paper(rec)
        if paper not in cluster["papers"]:
            cluster["papers"].append(paper)
        direction = _direction(rec)
        if direction:
            cluster["directions"].add(direction)
        evidence = _evidence(rec)
        cluster["evidence"].extend(evidence)
        cluster["contexts"].append({
            "association_id": c.get("record_id"),
            "paper": paper,
            "association_kind": c.get("association_kind"),
            "study_id": c.get("study_id"),
            "population_id": c.get("population_id"),
            "population_name": c.get("population_name"),
            "population_type": c.get("population_type"),
            "material_id": c.get("material_id"),
            "germplasm_names": c.get("germplasm_names") or [],
            "environment_id": c.get("environment_id"),
            "alternate_allele": c.get("alternate_allele"),
            "validation_status": (rec.get("transform") or {}).get("validation_status"),
            "review_status": c.get("review_status"),
            "effect_direction": direction,
            "missing_fields": c.get("missing_fields") or {},
            "evidence_count": len(evidence),
        })

    relations, conflicts = [], []
    for cluster in clusters.values():
        directions = sorted(cluster["directions"])
        evidence = cluster["evidence"]
        contexts = cluster["contexts"]
        conflict_ids = []
        if "increase" in directions and "decrease" in directions:
            cid = "acon_" + hashlib.sha256(cluster["relation_id"].encode()).hexdigest()[:16]
            conflicts.append({
                "conflict_id": cid, "type": "direction",
                "message": f"{cluster['trait_names']} / {cluster['locus_id']} 的效应方向相反",
                "relation_id": cluster["relation_id"],
                "paper_ids": [p.get("id") for p in cluster["papers"]],
                "association_ids": [x["association_id"] for x in contexts],
                "directions": directions,
            })
            conflict_ids.append(cid)

        missing = [x["association_id"] for x in contexts
                   if not x.get("study_id") or not x.get("population_id") or not x.get("environment_id")
                   or not x.get("evidence_count")]
        incomplete = [x["association_id"] for x in contexts if not x.get("evidence_count")]
        basis = []
        if conflict_ids:
            basis.append("存在未消解的方向冲突")
        if len(cluster["papers"]) >= 2:
            basis.append(f"{len(cluster['papers'])} 篇独立论文")
        else:
            basis.append("仅 1 篇论文")
        if missing:
            basis.append(f"{len(missing)} 个上下文缺少研究/群体/环境或字段证据")
        if incomplete:
            basis.append(f"{len(incomplete)} 个关联没有字段级证据")
        if not cluster["papers"]:
            basis.append("没有论文上下文")
        if conflict_ids or missing:
            confidence = "C"
        elif len(cluster["papers"]) >= 2:
            confidence = "A"
        else:
            confidence = "B"
        relations.append({
            **cluster,
            "directions": directions,
            "paper_count": len(cluster["papers"]),
            "association_count": len(contexts),
            "evidence_count": len(evidence),
            "confidence": confidence,
            "confidence_basis": basis,
            "conflict_ids": conflict_ids,
            "missing_context_ids": missing,
        })

    relations.sort(key=lambda r: (-r["paper_count"], -r["evidence_count"], r["trait_names"], r["locus_id"]))
    counts = Counter(r["confidence"] for r in relations)
    return {
        "aggregate_format": AGGREGATE_FORMAT,
        "scope": "association",
        "relations": relations,
        "conflicts": conflicts,
        "counts": {
            "papers": len({p.get("id") for r in relations for p in r["papers"]}),
            "relations": len(relations),
            "associations": len(associations),
            "evidence": sum(r["evidence_count"] for r in relations),
            "conflicts": len(conflicts),
            "confidence": dict(counts),
        },
    }
