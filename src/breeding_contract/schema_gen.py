"""Generate JSON Schema (draft 2020-12) documents from the compiled contract.

* record schema      — every field of the contract version (``record.schema.json``)
* profile schema     — record schema restricted to one profile's field set + profile requirements
* candidate schema   — what an extraction backend/model may emit for an extraction profile
"""
from __future__ import annotations

import copy

from .compile import field_index
from .rules import rule_to_json_schema
from .util import split_path

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def item_types(contract: dict) -> list[str]:
    """Types whose values are arrays of structured items (array_evidence, array_step, ...)."""
    return [name for name, t in contract["types"].items() if "item" in t]


def _id(contract: dict, kind: str) -> str:
    return f"urn:breeding-data-contract:{contract['name']}:{contract['version']}:{kind}"


def _vocab_codes(contract: dict, name: str) -> list[str]:
    return [v["code"] for v in contract["vocabularies"][name].get("values", [])]


def field_schema(contract: dict, f: dict, *, annotate: bool = True) -> dict:
    t = contract["types"][f["type"]]
    if "json_schema" in t:
        s = copy.deepcopy(t["json_schema"])
    else:
        s = {"type": "array", "minItems": 1, "items": {"$ref": f"#/$defs/{f['type']}_item"}}
    c = f.get("constraints") or {}
    for key in ("minimum", "maximum", "pattern"):
        if key in c:
            target = s["items"] if s.get("type") == "array" and "items" in s and "$ref" not in s["items"] else s
            target[key] = c[key]
    vname = f.get("vocabulary")
    if vname:
        voc = contract["vocabularies"][vname]
        if voc.get("enforcement") == "error":
            codes = _vocab_codes(contract, vname)
            if f["type"] == "string":
                s["enum"] = codes
            elif f["type"] == "array_string":
                s["items"]["enum"] = codes
            elif f["type"] == "object_string" and voc.get("applies_to") == "values":
                s["additionalProperties"]["enum"] = codes
    if annotate:
        s["description"] = f["definition_zh"]
        s["x-availability"] = f["availability"]
        s["x-required"] = f["required"]
        s["x-since"] = f["since"]
        s["x-maturity"] = f["maturity"]
        if vname:
            s["x-vocabulary"] = vname
        if f.get("status") == "deprecated":
            s["deprecated"] = True
    return s


def item_defs(contract: dict) -> dict:
    idx = field_index(contract)
    defs = {}
    for tname in item_types(contract):
        t = contract["types"][tname]
        item = t["item"]
        props = copy.deepcopy(item.get("properties") or {})
        for path in item.get("from_fields") or []:
            _, leaf = split_path(path)
            props[leaf] = field_schema(contract, idx[path], annotate=False)
        d = {"type": "object", "additionalProperties": False, "properties": props}
        if item.get("required"):
            d["required"] = item["required"]
        if item.get("any_of_required"):
            d["anyOf"] = [{"required": r} for r in item["any_of_required"]]
        if t.get("maturity") == "provisional":
            d["x-maturity"] = "provisional"
        defs[f"{tname}_item"] = d
    return defs


def record_schema(contract: dict, *, fields: list[str] | None = None, extra_required: list[str] | None = None,
                  record_kinds: list[str] | None = None, include_rules: bool = True, kind: str = "record",
                  title: str | None = None) -> dict:
    idx = field_index(contract)
    allowed = fields if fields is not None else [f["path"] for f in contract["fields"]]
    allowed_set = set(allowed)
    groups: dict[str, dict] = {}
    for f in contract["fields"]:
        if f["path"] not in allowed_set:
            continue
        g = groups.setdefault(f["group"], {"type": "object", "minProperties": 1, "additionalProperties": False,
                                           "properties": {}, "required": []})
        s = field_schema(contract, f)
        if f["path"] == "common.schema_version":
            s["const"] = contract["version"]
        if f["path"] == "common.schema_name":
            s["const"] = contract["name"]
        if f["path"] == "common.record_kind" and record_kinds is not None:
            s["enum"] = list(record_kinds)
        g["properties"][f["name"]] = s
        if f["required"] == "Y":
            g["required"].append(f["name"])
    for path in extra_required or []:
        gname, name = split_path(path)
        if path in allowed_set and name not in groups[gname]["required"]:
            groups[gname]["required"].append(name)
    for gname, g in groups.items():
        g["description"] = contract["groups"][gname]["purpose_zh"]
        if not g["required"]:
            del g["required"]
    schema = {
        "$schema": SCHEMA_DIALECT,
        "$id": _id(contract, kind),
        "title": title or f"{contract['name']} {contract['version']} record",
        "description": (f"{contract['title_zh']}（{contract['name']} {contract['version']}）。由 "
                        "field_catalog/field_catalog.yaml 生成，请勿手工编辑。未报告字段应省略（不写 null/空串）。"),
        "type": "object",
        "required": ["common"],
        "additionalProperties": False,
        "properties": {g: groups[g] for g in contract["groups"] if g in groups},
        "x-contract": {"name": contract["name"], "version": contract["version"],
                       "source_digest": contract["source_digest"]},
    }
    defs = item_defs(contract)
    used = {f"{idx[p]['type']}_item" for p in allowed if idx[p]["type"] in item_types(contract)}
    if used:
        schema["$defs"] = {k: v for k, v in defs.items() if k in used}
    if include_rules:
        clauses = []
        validator_only = []
        for rule in contract["rules"]:
            if rule["kind"] in ("unique_within_dataset", "single_value_per_group"):
                validator_only.append(rule["id"])
                continue
            if not all(p in allowed_set for p in rule_paths(rule)):
                continue
            js = rule_to_json_schema(rule)
            if js is None:
                validator_only.append(rule["id"])
            else:
                clauses.append(js)
        if clauses:
            schema["allOf"] = clauses
        schema["x-validator-only-rules"] = validator_only
    return schema


def rule_paths(rule: dict) -> list[str]:
    paths = list(rule.get("require") or []) + list(rule.get("require_any") or [])
    paths += [p for p in rule.get("fields") or [] if p != "*"]
    for key in ("field", "group_by", "target"):
        if rule.get(key):
            paths.append(rule[key])
    paths += list(rule.get("candidates") or [])
    for span in rule.get("spans") or []:
        paths += [span["mention"], span["start"], span["end"]]

    def walk(c: dict) -> None:
        for sub in c.get("all", []) + c.get("any", []):
            walk(sub)
        if "present" in c:
            paths.append(c["present"])
        paths.extend(c.get("any_present", []))
        if "field" in c:
            paths.append(c["field"])
    if rule.get("when"):
        walk(rule["when"])
    return paths


def profile_schema(contract: dict, profile: dict) -> dict:
    kinds = None
    if profile.get("is_extraction"):
        kinds = list(profile.get("model_record_kinds") or [])
        kinds += [sr["record_kind"] for sr in profile.get("system_records") or [] if sr["record_kind"] not in kinds]
    return record_schema(contract, fields=[f["path"] for f in profile["fields"]],
                         extra_required=(profile.get("required_fields") or {}).get("always"),
                         record_kinds=kinds, kind=f"profile:{profile['name']}",
                         title=f"{contract['name']} {contract['version']} record — profile {profile['name']}")


def candidate_schema(contract: dict, profile: dict) -> dict:
    """Schema of the candidates document an extraction backend returns (flat dotted field keys)."""
    idx = field_index(contract)
    by_role: dict[str, list[dict]] = {}
    for f in profile["fields"]:
        by_role.setdefault(f["role"], []).append(f)
    doc_props = {f["path"]: field_schema(contract, idx[f["path"]]) for f in by_role.get("document", [])}
    extract_props = {f["path"]: field_schema(contract, idx[f["path"]]) for f in by_role.get("extract", [])}
    prov = (profile.get("roles") or {}).get("provenance") or {}
    ev_props = {}
    for role in ("page", "section", "quote", "table_figure", "row_key", "column_key"):
        if role in prov:
            ev_props[role] = field_schema(contract, idx[prov[role]])
    if "part" in prov:  # multi-file sources (AMB-041): a label of the run, not a vocabulary code
        ev_props["part"] = {"type": "string", "pattern": "^[a-z][a-z0-9_]*$",
                            "description": "which file of the source the page belongs to, as named in the page "
                                           "markers (e.g. `supplement`); omit for the main text"}
    max_quote = (profile.get("evidence_policy") or {}).get("max_quote_chars")
    if max_quote and "quote" in ev_props:
        ev_props["quote"]["maxLength"] = max_quote
    ev_required = [r for r in ("page", "quote") if r in ev_props]
    cand_props = {
        "record_kind": {"enum": list(profile.get("model_record_kinds") or [])},
        "fields": {"type": "object", "minProperties": 1, "additionalProperties": False, "properties": extract_props},
        "evidence": {"type": "object", "additionalProperties": False, "properties": ev_props,
                     "required": ev_required},
        "note": {"type": "string", "description": "free-text note for reviewers; never copied into records"},
    }
    links = profile.get("record_links") or {}
    if links:
        cand_props["ref"] = {"type": "string", "pattern": "^[A-Za-z0-9_.:-]{1,64}$",
                             "description": "candidate-local name that other candidates can reference in `links`"}
        cand_props["links"] = {
            "type": "object", "additionalProperties": False, "minProperties": 1,
            "description": "references to other candidates by `ref`; resolved to record IDs by the pipeline",
            "properties": {name: {"type": "array", "minItems": 1, "uniqueItems": True,
                                  "items": {"type": "string", "pattern": "^[A-Za-z0-9_.:-]{1,64}$"},
                                  "description": spec["description_zh"] +
                                  (f"（目标类型：{', '.join(spec['target_kinds'])}）" if spec.get("target_kinds") else "")}
                           for name, spec in links.items()}}
    if any(spec["rule"] == "backend_confidence" for spec in (profile.get("generated_fields") or {}).values()):
        cand_props["confidence"] = {"type": "number", "minimum": 0, "maximum": 1,
                                    "description": "backend-reported confidence; omit if the backend has none"}
    required_doc = [p for p in doc_props
                    if idx[p]["required"] == "Y" and p not in (profile.get("document_defaults") or {})]
    return {
        "$schema": SCHEMA_DIALECT,
        "$id": _id(contract, f"candidates:{profile['name']}"),
        "title": f"Extraction candidates — {contract['name']} {contract['version']} / {profile['name']}",
        "description": ("Output format for extraction backends. Keys of `document` and `fields` are dotted "
                        "field paths from the resolved profile. Evidence is mandatory and must be verbatim."),
        "type": "object",
        "required": ["document", "candidates"],
        "additionalProperties": False,
        "properties": {
            "extraction": {"type": "object", "additionalProperties": False,
                           "properties": {"method": {"type": "string"}, "model": {"type": "string"},
                                          "backend": {"type": "string"}, "notes": {"type": "string"}}},
            "document": {"type": "object", "additionalProperties": False, "properties": doc_props,
                         "required": required_doc},
            "candidates": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                      "required": ["record_kind", "fields", "evidence"],
                                                      "properties": cand_props}},
        },
        "$defs": {k: v for k, v in item_defs(contract).items()},
    }


def strip_rules(schema: dict) -> dict:
    s = dict(schema)
    s.pop("allOf", None)
    return s
