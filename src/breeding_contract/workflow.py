"""The research workflow of a paper as a view over its atomic records (AMB-039).

    background -> research question / objective -> hypothesis -> design -> step (method) -> observation / result
               -> conclusion

Nothing here is extracted a second time. A node is a record; its stage is the role the paper gives the
statement (the field bound to vocabulary ``statement_role``) or, without one, the record kind. An edge is a
record link whose field carries a ``workflow_edge`` annotation in the catalog:

    evidence      conclusion / hypothesis  -> the results it rests on
    method        result / observation     -> the step that produced it
    tests         step / result            -> the hypothesis, question or objective it was run to test
    addresses     hypothesis / conclusion  -> the question, objective, hypothesis or background it answers
    prerequisite  step                     -> the step, observation or result whose output it uses

Records joined by prerequisite edges are put in dependency order; a prerequisite that several records use is a
branch point. The audit lists structural gaps (a hypothesis nothing tests, a dependency cycle …). Like the
evidence-chain audit it reports what is present and connected, never whether an experiment is sound: flags are
review hints.
"""
from __future__ import annotations

from .util import get_path, iter_fields

WORKFLOW_FORMAT = 1
ROLE_VOCABULARY = "statement_role"
CONDITION_PATH = "agent.step_condition"
STAGE_ORDER = ("background", "research_question", "objective", "hypothesis", "design", "step", "observation",
               "result", "conclusion", "statement")
KIND_STAGE = {"method": "step", "analysis_result": "result", "claim": "statement"}

FLAG_HELP = {
    "HYPOTHESIS_UNTESTED": "a hypothesis that no step, observation or result is linked to as its test",
    "QUESTION_UNADDRESSED": "a research question or objective that no hypothesis, test or conclusion points to",
    "CONCLUSION_WITHOUT_EVIDENCE": "a conclusion that links no observation or result as its grounds",
    "RESULT_WITHOUT_METHOD": "a result with no link to the step that produced it or that it builds on",
    "STEP_WITHOUT_OUTPUT": "a step that no result cites as its method and no later step depends on",
    "DEPENDENCY_CYCLE": "steps whose prerequisite links form a cycle",
    "UNRESOLVED_LINK": "a workflow link points to a record that is not in this set",
}


def _edge_fields(contract: dict) -> dict[str, str]:
    return {f["path"]: f["workflow_edge"] for f in contract["fields"] if f.get("workflow_edge")}


def _label(rec: dict, text_paths: list[str], name_paths: list[str]):
    for p in text_paths + name_paths:
        v = get_path(rec, p, None)
        if isinstance(v, str) and v:
            return v
    return get_path(rec, "common.source_quote", None)


def workflow_view(records: list[dict], contract: dict) -> dict | None:
    """Nodes, edges, step order and structural flags; None when the contract declares no workflow edges
    (versions before 3.5.0)."""
    edge_of = _edge_fields(contract)
    if not edge_of:
        return None
    fields = {f["path"]: f for f in contract["fields"]}
    role_path = next((p for p, f in fields.items() if f.get("vocabulary") == ROLE_VOCABULARY), None)
    text_paths = [p for p, f in fields.items() if f.get("key_role") == "assertion"
                  and f.get("argument_role") in (None, "claim") and f["type"] == "string"]
    name_paths = [p for p, f in fields.items() if f.get("key_role") == "method_spec" and f["type"] == "string"]
    kinds = contract.get("record_kinds") or {}

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for rec in records:
        rid, kind = get_path(rec, "common.record_id", None), get_path(rec, "common.record_kind", None)
        role = get_path(rec, role_path, None) if role_path else None
        stage = role or KIND_STAGE.get(kind) or \
            ("observation" if kind == "observation" or (kinds.get(kind) or {}).get("grain") == "observation_unit"
             else None)
        links = [(edge_of[p], p, t) for p, v in iter_fields(rec) if p in edge_of for t in v]
        if stage is None and not links:
            continue  # assets and tool specifications are not part of a paper's workflow
        node = {"id": rid, "stage": stage or "statement", "record_kind": kind,
                "label": _label(rec, text_paths, name_paths),
                "source_id": get_path(rec, "common.source_id", None),
                "source_part": get_path(rec, "common.source_part", None),
                "source_page": get_path(rec, "common.source_page", None),
                "condition": get_path(rec, CONDITION_PATH, None)}
        nodes[rid] = {k: v for k, v in node.items() if v is not None}
        edges += [{"s": rid, "type": etype, "o": target, "field": path} for etype, path, target in links]

    flags: dict[str, list[str]] = {}

    def flag(rid: str, code: str) -> None:
        if code not in flags.setdefault(rid, []):
            flags[rid].append(code)
    incoming: dict[str, dict[str, list[str]]] = {}
    outgoing: dict[str, dict[str, list[str]]] = {}
    for e in edges:
        if e["o"] not in nodes:
            e["unresolved"] = True
            flag(e["s"], "UNRESOLVED_LINK")
            continue
        incoming.setdefault(e["o"], {}).setdefault(e["type"], []).append(e["s"])
        outgoing.setdefault(e["s"], {}).setdefault(e["type"], []).append(e["o"])

    def has(table: dict, rid: str, *types: str) -> bool:
        return any(table.get(rid, {}).get(t) for t in types)
    for rid, n in nodes.items():
        stage = n["stage"]
        if stage == "hypothesis" and not has(incoming, rid, "tests"):
            flag(rid, "HYPOTHESIS_UNTESTED")
        if stage in ("research_question", "objective") and not has(incoming, rid, "addresses", "tests"):
            flag(rid, "QUESTION_UNADDRESSED")
        if stage == "conclusion" and not has(outgoing, rid, "evidence"):
            flag(rid, "CONCLUSION_WITHOUT_EVIDENCE")
        if stage == "result" and not has(outgoing, rid, "method", "prerequisite"):
            flag(rid, "RESULT_WITHOUT_METHOD")
        if stage == "step" and not has(incoming, rid, "method", "prerequisite"):
            flag(rid, "STEP_WITHOUT_OUTPUT")

    # Order steps by their prerequisites (Kahn); what cannot be ordered lies on a cycle.
    deps = {rid: [t for t in outgoing.get(rid, {}).get("prerequisite", [])] for rid in nodes}
    in_dag = {rid for rid in nodes if deps[rid] or has(incoming, rid, "prerequisite")}
    position = {rid: i for i, rid in enumerate(nodes)}
    remaining = {rid: set(deps[rid]) for rid in in_dag}
    order: list[str] = []
    while remaining:
        ready = sorted((r for r, d in remaining.items() if not d), key=position.get)
        if not ready:
            for rid in remaining:
                flag(rid, "DEPENDENCY_CYCLE")
            break
        for r in ready:
            order.append(r)
            del remaining[r]
        for d in remaining.values():
            d.difference_update(ready)
    branch_points = sorted((rid for rid in nodes if len(set(incoming.get(rid, {}).get("prerequisite", []))) > 1),
                           key=position.get)

    for rid, codes in flags.items():
        nodes[rid]["flags"] = codes
    traces = []
    for rid, n in nodes.items():
        if n["stage"] != "hypothesis":
            continue
        t = {"hypothesis": rid, "label": n.get("label"),
             "addresses": outgoing.get(rid, {}).get("addresses", []),
             "tested_by": incoming.get(rid, {}).get("tests", []),
             "evidence": outgoing.get(rid, {}).get("evidence", []),
             "addressed_by": incoming.get(rid, {}).get("addresses", [])}
        traces.append({k: v for k, v in t.items() if v not in (None, [])})
    stage_counts: dict[str, int] = {}
    for n in nodes.values():
        stage_counts[n["stage"]] = stage_counts.get(n["stage"], 0) + 1
    edge_counts: dict[str, int] = {}
    for e in edges:
        edge_counts[e["type"]] = edge_counts.get(e["type"], 0) + 1
    flag_counts: dict[str, int] = {}
    for codes in flags.values():
        for c in codes:
            flag_counts[c] = flag_counts.get(c, 0) + 1
    return {
        "workflow_format": WORKFLOW_FORMAT,
        "basis": "nodes are records, edges are record links with a catalog workflow_edge (AMB-039); "
                 "structure and connectivity only, not experimental soundness",
        "stages": {s: stage_counts[s] for s in STAGE_ORDER if s in stage_counts} |
                  {s: c for s, c in sorted(stage_counts.items()) if s not in STAGE_ORDER},
        "edges_by_type": dict(sorted(edge_counts.items())),
        "flags": dict(sorted(flag_counts.items())),
        "flag_help": {k: FLAG_HELP[k] for k in sorted(flag_counts)},
        "step_order": order,
        "branch_points": branch_points,
        "hypotheses": traces,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def workflow_audit(records: list[dict], contract: dict) -> dict | None:
    """The summary of ``workflow_view`` for a validation report: counts, flags and the flagged records."""
    view = workflow_view(records, contract)
    if view is None:
        return None
    return {"audit_format": 1, "basis": view["basis"], "stages": view["stages"],
            "edges_by_type": view["edges_by_type"],
            "links": {"total": len(view["edges"]), "unresolved": sum(1 for e in view["edges"] if e.get("unresolved"))},
            "flags": view["flags"], "flag_help": view["flag_help"],
            "hypotheses": len(view["hypotheses"]), "steps_ordered": len(view["step_order"]),
            "records": [{"record_id": n["id"], "stage": n["stage"], "flags": n["flags"]}
                        for n in view["nodes"] if n.get("flags")]}
