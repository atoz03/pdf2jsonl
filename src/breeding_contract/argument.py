"""Evidence-chain audit of a set of records, after TRACE (Kim & Yang, ICML 2026, arXiv:2605.29656).

TRACE labels every step of a reasoning trace with Toulmin elements (claim, data, warrant, backing, qualifier,
rebuttal) and Flavell's metacognitive elements (monitoring, evaluation), then checks which element
combinations and transitions form sound argument structure. Records are already structured, so here the
elements come from the catalog: fields carry an ``argument_role`` (AMB-033). The audit reports, for every record
that asserts something, the elements it states itself, the elements reachable through its links (the chain),
whether those links resolve, and structural flags.

It produces no score. TRACE itself notes that fluent structure can rest on wrong premises; the audit therefore
says what is *present and connected*, never whether a conclusion is true. Flags are review hints, not errors.
"""
from __future__ import annotations

from .rules import check_record_rule, eval_condition
from .util import MISSING, get_path, iter_fields

ELEMENTS = ("claim", "data", "warrant", "backing", "qualifier", "rebuttal", "monitoring", "evaluation")
CHAIN_DEPTH = 3

FLAG_HELP = {
    "NO_DATA": "asserts something but neither states nor links any data (quote, observation, statistic)",
    "NO_WARRANT": "no warrant in the chain: no statistical test, evidence type or linked method",
    "QUALIFIER_NOT_CAPTURED": "the quote hedges the statement but the qualifier text was not captured",
    "HEDGED_STATEMENT_USED_AS_DATA": "a hedged statement is used as data for another statement (uncertainty compounds)",
    "UNRESOLVED_LINK": "a link points to a record that is not in this set",
}


def _roles(contract: dict) -> tuple[dict[str, str], list[str]]:
    roles = {f["path"]: f["argument_role"] for f in contract["fields"] if f.get("argument_role")}
    links = [f["path"] for f in contract["fields"]
             if f.get("key_role") == "record_link" and f.get("type") == "array_string"
             and f.get("argument_role") in ("data", "warrant")]
    return roles, links


def argument_audit(records: list[dict], contract: dict, id_path: str = "common.record_id",
                   kind_path: str = "common.record_kind") -> dict:
    roles, link_fields = _roles(contract)
    qualifier_rules = [r for r in contract["rules"] if r["kind"] == "required_when"
                       and r.get("require") and all(roles.get(p) == "qualifier" for p in r["require"])]
    # A hedge is what the qualifier rule (R032) looks for: the verbatim hedge field, or a hedging quote. Scope
    # qualifiers such as applicable_population restrict a claim without weakening it, so they do not count.
    hedge_fields = {p for r in qualifier_rules for p in r["require"]}

    def hedged(rec: dict) -> bool:
        return any(get_path(rec, p) is not MISSING for p in hedge_fields) or \
            any(r.get("when") and eval_condition(r["when"], rec) for r in qualifier_rules)

    by_id = {get_path(r, id_path, None): r for r in records}
    own: dict[str, set[str]] = {}
    links: dict[str, dict[str, list[str]]] = {}
    for rec in records:
        rid = get_path(rec, id_path, None)
        own[rid] = {roles[p] for p, _ in iter_fields(rec) if p in roles}
        links[rid] = {p: list(v) for p in link_fields if (v := get_path(rec, p)) is not MISSING}

    def chain(rid: str) -> set[str]:
        seen, frontier, out = {rid}, [rid], set(own.get(rid, ()))
        for _ in range(CHAIN_DEPTH):
            nxt = []
            for r in frontier:
                for p, ids in links.get(r, {}).items():
                    for t in ids:
                        if t in by_id and t not in seen:
                            seen.add(t)
                            nxt.append(t)
                            # a linked record contributes what it grounds: its data/warrant/backing, and it is
                            # itself data (or a warrant, for method links) for the linking statement
                            out |= own[t] & {"data", "warrant", "backing"}
                            out.add(roles[p])
            frontier = nxt
        return out

    used_as_data: dict[str, list[str]] = {}
    for rid, ls in links.items():
        for p, ids in ls.items():
            if roles.get(p) == "data":
                for t in ids:
                    used_as_data.setdefault(t, []).append(rid)

    rows = []
    coverage = {e: {"own": 0, "chain": 0} for e in ELEMENTS}
    flag_counts: dict[str, int] = {}
    n_links = n_unresolved = 0
    for rec in records:
        rid = get_path(rec, id_path, None)
        mine = own[rid]
        if "claim" not in mine and not any(p in links[rid] for p in link_fields):
            continue  # records that assert nothing (pure observations, assets) are grounds, not arguments
        ch = chain(rid)
        flags = []
        unresolved = [t for ids in links[rid].values() for t in ids if t not in by_id]
        n_links += sum(len(ids) for ids in links[rid].values())
        n_unresolved += len(unresolved)
        if "data" not in ch:
            flags.append("NO_DATA")
        if "warrant" not in ch:
            flags.append("NO_WARRANT")
        kinds = contract.get("record_kinds") or {}
        if any(check_record_rule(r, rec, kinds) for r in qualifier_rules):
            flags.append("QUALIFIER_NOT_CAPTURED")
        hedged_targets = [t for p, ids in links[rid].items() if roles.get(p) == "data"
                          for t in ids if t in by_id and "claim" in own[t] and hedged(by_id[t])]
        if hedged_targets:
            flags.append("HEDGED_STATEMENT_USED_AS_DATA")
        if unresolved:
            flags.append("UNRESOLVED_LINK")
        for e in ELEMENTS:
            coverage[e]["own"] += e in mine
            coverage[e]["chain"] += e in ch
        for f in flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1
        row = {"record_id": rid, "record_kind": get_path(rec, kind_path, None),
               "elements": [e for e in ELEMENTS if e in mine], "chain_elements": [e for e in ELEMENTS if e in ch]}
        if links[rid]:
            row["links"] = links[rid]
        if used_as_data.get(rid):
            row["supports"] = sorted(used_as_data[rid])
        if flags:
            row["flags"] = flags
        rows.append(row)
    return {
        "audit_format": 1,
        "basis": "TRACE (arXiv:2605.29656): Toulmin + Flavell elements via catalog argument_role (AMB-033); "
                 "reports structure and connectivity, not correctness",
        "statements": len(rows),
        "coverage": coverage,
        "links": {"total": n_links, "unresolved": n_unresolved},
        "flags": dict(sorted(flag_counts.items())),
        "flag_help": {k: FLAG_HELP[k] for k in sorted(flag_counts)},
        "records": rows,
    }
