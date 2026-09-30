"""Render the extraction brief for a model from the *resolved* profile of the requested contract version.

The prompt template (prompts/extraction_brief.md) contains workflow instructions only; every field, record
kind, vocabulary and rule shown to the model is injected here from the repository release.
"""
from __future__ import annotations

import re

from .contract_link import skill_dir

PLACEHOLDERS = frozenset({
    "contract_name", "schema_version", "release_status", "profile_name", "profile_title", "profile_description",
    "record_kinds_table", "document_fields_table", "evidence_roles_table", "extract_fields_table", "field_count",
    "vocabularies_block", "rules_block", "system_fields_list", "candidate_schema_file", "pages_file",
    "candidates_file", "argument_block", "record_links_block",
})
ARGUMENT_ORDER = ("claim", "data", "warrant", "backing", "qualifier", "rebuttal")

ROLE_HELP = {
    "page": "physical PDF page number, starting at 1 (the page marker in the pages file)",
    "quote": "minimal verbatim quote copied from that page (no paraphrase, no ellipsis)",
    "section": "section heading the quote belongs to, as printed",
    "table_figure": "table/figure label when the value comes from a table or figure, e.g. `Table 2`",
    "row_key": "row label of the table cell, verbatim",
    "column_key": "column label of the table cell, verbatim",
}


def _cell(s) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def _vocab_hint(profile: dict, f: dict) -> str:
    vname = f.get("vocabulary")
    if not vname:
        return ""
    voc = profile["vocabularies"].get(vname, {})
    codes = [v["code"] for v in voc.get("values", [])]
    mode = {"error": "must be one of", "warning": "should be one of", "open": "e.g."}.get(voc.get("enforcement"), "")
    shown = ", ".join(f"`{c}`" for c in codes[:12]) + (" …" if len(codes) > 12 else "")
    return f"{mode} {shown}"


def fields_table(profile: dict, role: str) -> str:
    rows = ["| field | type | definition | where to look | values |", "|---|---|---|---|---|"]
    for f in profile["fields"]:
        if f["role"] != role:
            continue
        rows.append(f"| `{f['path']}` | {f['type']} | {_cell(f['definition_zh'])} | {_cell(f.get('data_source_zh'))} |"
                    f" {_cell(_vocab_hint(profile, f))} |")
    return "\n".join(rows)


def record_kinds_table(profile: dict) -> str:
    rows = ["| record_kind | meaning |", "|---|---|"]
    for k in profile.get("model_record_kinds") or []:
        info = profile["record_kinds"].get(k, {})
        rows.append(f"| `{k}` | {_cell(info.get('label_zh'))} — {_cell(info.get('description_zh'))} |")
    return "\n".join(rows)


def evidence_table(profile: dict) -> str:
    prov = (profile.get("roles") or {}).get("provenance") or {}
    rows = ["| evidence key | stored as | meaning |", "|---|---|---|"]
    for role in ("page", "quote", "section", "table_figure", "row_key", "column_key"):
        if role in prov:
            rows.append(f"| `{role}` | `{prov[role]}` | {ROLE_HELP[role]} |")
    return "\n".join(rows)


def vocab_block(profile: dict) -> str:
    extract_vocabs = {f["vocabulary"] for f in profile["fields"]
                      if f.get("vocabulary") and f["role"] in ("extract", "document")}
    parts = []
    for name in sorted(extract_vocabs):
        voc = profile["vocabularies"][name]
        vals = "; ".join(f"`{v['code']}`" + (f" ({v['label_zh']})" if v.get("label_zh") else "")
                         for v in voc["values"])
        parts.append(f"- **{name}** ({voc.get('enforcement')}): {vals}")
    return "\n".join(parts) or "(none)"


def rules_block(contract: dict, profile: dict) -> str:
    from breeding_contract.schema_gen import rule_paths
    in_profile = {f["path"] for f in profile["fields"]}
    lines = []
    for r in contract["rules"]:
        applies = r.get("fields") == ["*"] or bool(set(rule_paths(r)) & in_profile)
        if applies:
            lines.append(f"- `{r['id']}` [{r['severity']}] {r['title_zh']}")
    return "\n".join(lines)


def argument_block(contract: dict, profile: dict) -> str:
    """Fields the model may fill, grouped by their Toulmin element (catalog `argument_role`, AMB-033)."""
    labels = (contract.get("codes") or {}).get("argument_role") or {}
    by_role: dict[str, list[str]] = {}
    for f in profile["fields"]:
        if f.get("argument_role") in ARGUMENT_ORDER and f["role"] in ("extract", "provenance"):
            by_role.setdefault(f["argument_role"], []).append(f["path"])
    lines = []
    for r in ARGUMENT_ORDER:
        if r in by_role:
            spec = labels.get(r, {})
            lines.append(f"- **{spec.get('label_en', r)}** ({spec.get('label_zh', '')}，{spec.get('description_zh', '')}): "
                         + ", ".join(f"`{p}`" for p in by_role[r]))
    linked = [f"`{s['field']}` (via `links.{n}`)" for n, s in (profile.get("record_links") or {}).items()]
    if linked:
        lines.append("- **Links** between candidates, filled by the pipeline: " + ", ".join(linked))
    return "\n".join(lines) or "(this profile exposes no evidence-chain fields)"


def record_links_block(profile: dict) -> str:
    links = profile.get("record_links") or {}
    if not links:
        return "(this profile declares no candidate links; do not output `ref` or `links`)"
    first = next(iter(links))
    lines = ["Give a candidate a short `ref` (letters, digits, `_.:-`) when another candidate points to it, and list the "
             "references under `links`, e.g. "
             f'`{{"ref": "r3", "record_kind": "...", "links": {{"{first}": ["r1", "r2"]}}, ...}}`.', ""]
    for name, spec in links.items():
        targets = ", ".join(f"`{k}`" for k in spec.get("target_kinds") or []) or "any record kind"
        lines.append(f"- `links.{name}` → stored as `{spec['field']}`: {spec['description_zh']} (targets: {targets})")
    lines += ["", "Reference only candidates in this file and only when the paper itself connects them (the result is "
              "reported by that method; the conclusion rests on that observation). The pipeline turns references into "
              "record IDs. A reference to a candidate that is rejected, e.g. because its quote is not found, stays "
              "unresolved and the linking record is flagged for review."]
    return "\n".join(lines)


def system_list(profile: dict) -> str:
    return ", ".join(f"`{f['path']}`" for f in profile["fields"]
                     if f["role"] in ("system", "linked", "normalized", "generated"))


def render_brief(rc, profile: dict, pages_file: str, candidates_file: str, candidate_schema_file: str) -> str:
    template = (skill_dir() / "prompts" / "extraction_brief.md").read_text(encoding="utf-8")
    values = {
        "contract_name": rc.name,
        "schema_version": rc.version,
        "release_status": rc.status,
        "profile_name": profile["name"],
        "profile_title": profile["title_zh"],
        "profile_description": profile["description_zh"],
        "record_kinds_table": record_kinds_table(profile),
        "document_fields_table": fields_table(profile, "document"),
        "evidence_roles_table": evidence_table(profile),
        "extract_fields_table": fields_table(profile, "extract"),
        "field_count": str(sum(f["role"] == "extract" for f in profile["fields"])),
        "vocabularies_block": vocab_block(profile),
        "rules_block": rules_block(rc.contract, profile),
        "system_fields_list": system_list(profile),
        "candidate_schema_file": candidate_schema_file,
        "pages_file": pages_file,
        "candidates_file": candidates_file,
        "argument_block": argument_block(rc.contract, profile),
        "record_links_block": record_links_block(profile),
    }
    assert set(values) == PLACEHOLDERS

    def sub(m: re.Match) -> str:
        return values[m.group(1)]
    return re.sub(r"\{\{\s*([a-z_]+)\s*\}\}", sub, template)


def candidates_skeleton(profile: dict) -> dict:
    """A minimal, empty-valued illustration of the candidates document (keys resolved from the profile)."""
    sem = (profile.get("roles") or {}).get("semantic") or {}
    doc = {f["path"]: f"<{f['type']}>" for f in profile["fields"] if f["role"] == "document"}
    statement = sem.get("statement")
    fields = {statement: "<verbatim-supported single finding>"} if statement else {}
    kinds = profile.get("model_record_kinds") or ["claim"]
    return {"extraction": {"method": "model", "model": "<model id>", "backend": "agent"},
            "document": doc,
            "candidates": [{"record_kind": kinds[0], "fields": fields,
                            "evidence": {"page": 1, "quote": "<verbatim quote>"}}]}
