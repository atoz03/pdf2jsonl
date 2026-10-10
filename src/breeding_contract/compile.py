"""Compile editable sources into a self-contained contract document and resolved profiles.

The compiled contract (``contract.json`` in a release) is what every consumer loads:
fields with their vocabularies, rules, types, record kinds and ambiguity register.
"""
from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from .sources import Sources
from .util import ContractError, split_path

PROFILE_MERGE_KEYS = ("roles", "system_fields", "generated_fields", "document_defaults", "evidence_policy",
                      "required_fields")
ROLE_PRIORITY = ("system", "linked", "normalized", "generated", "document", "provenance")
FIELD_ANNOTATIONS = ("key_role", "serves", "argument_role", "workflow_edge")
EVIDENCE_ROLES = ("page", "section", "quote", "table_figure", "row_key", "column_key")


def compile_contract(src: Sources) -> dict:
    cat = src.catalog
    fields = []
    for f in cat["fields"]:
        group, name = split_path(f["path"])
        entry = {"path": f["path"], "group": group, "name": name}
        entry.update({k: v for k, v in f.items() if k != "path"})
        fields.append(entry)
    record_kinds = {}
    rk = src.vocabularies.get("record_kind")
    if rk:
        for v in rk["values"]:
            record_kinds[v["code"]] = {k: v.get(k) for k in ("label_zh", "grain", "description_zh")}
    vocabularies = {name: {k: v for k, v in doc.items() if k != "vocabulary_format"}
                    for name, doc in src.vocabularies.items()}
    return {
        "contract_format": 1,
        "name": cat["contract"]["name"],
        "title_zh": cat["contract"]["title_zh"],
        "version": src.version,
        "record_layout": cat["contract"]["record_layout"],
        "missing_value_policy": cat["contract"]["missing_value_policy"],
        "baseline_zh": cat["contract"].get("baseline_zh"),
        "codes": cat["codes"],
        "groups": cat["groups"],
        "types": cat["types"],
        "record_kinds": record_kinds,
        "fields": fields,
        "rules": cat["rules"],
        "vocabularies": vocabularies,
        "ambiguities": cat["ambiguities"],
        "source_digest": src.digest(),
    }


def field_index(contract: dict) -> dict[str, dict]:
    return {f["path"]: f for f in contract["fields"]}


def _merge_profile(parent: dict, child: dict) -> dict:
    out = copy.deepcopy(parent)
    for key, value in child.items():
        if key in PROFILE_MERGE_KEYS and isinstance(value, dict) and isinstance(out.get(key), dict):
            merged = out[key]
            for k2, v2 in value.items():
                if isinstance(v2, dict) and isinstance(merged.get(k2), dict):
                    merged[k2] = {**merged[k2], **v2}
                else:
                    merged[k2] = copy.deepcopy(v2)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _flatten_extends(name: str, raw_profiles: dict[str, dict], seen: tuple = ()) -> tuple[dict, list[str]]:
    if name not in raw_profiles:
        raise ContractError(f"unknown profile {name!r}")
    if name in seen:
        raise ContractError(f"profile inheritance cycle: {' -> '.join(seen + (name,))}")
    raw = raw_profiles[name]
    parent_name = raw.get("extends")
    if not parent_name:
        return copy.deepcopy(raw), [name]
    parent, chain = _flatten_extends(parent_name, raw_profiles, seen + (name,))
    merged = _merge_profile(parent, {k: v for k, v in raw.items() if k != "extends"})
    return merged, chain + [name]


def _fill_rules(p: dict) -> list[str]:
    names = set()
    for spec in (p.get("system_fields") or {}).values():
        names.add(spec["rule"])
    for spec in (p.get("generated_fields") or {}).values():
        names.add(spec["rule"])
    for n in p.get("normalizers") or []:
        names.add(n["rule"])
    for sr in p.get("system_records") or []:
        names.add(sr["rule"])
        for spec in sr["fields"].values():
            names.add(spec["rule"])
    return sorted(names)


def resolve_profile(contract: dict, raw_profiles: dict[str, dict], name: str) -> dict:
    p, chain = _flatten_extends(name, raw_profiles)
    idx = field_index(contract)
    sel = p["selection"]

    def need(path: str, where: str) -> dict:
        if path not in idx:
            raise ContractError(f"profile {name}: {where} references unknown field {path}")
        return idx[path]

    selected: list[str] = []
    if sel["base"] == "all_active":
        avail = set(sel.get("include_availability") or "DNIGF")
        groups = set(sel.get("include_groups") or contract["groups"].keys())
        selected = [f["path"] for f in contract["fields"]
                    if f["status"] == "active" and f["availability"] in avail and f["group"] in groups]
    else:
        for path in sel.get("fields") or []:
            need(path, "selection.fields")
            selected.append(path)
    for path in sel.get("include_fields") or []:
        need(path, "selection.include_fields")
        if path not in selected:
            selected.append(path)
    excluded = set(sel.get("exclude_fields") or [])
    for path in excluded:
        need(path, "selection.exclude_fields")
    selected = [x for x in selected if x not in excluded]

    roles_of: dict[str, set] = {}

    def tag(path: str, role: str, where: str) -> None:
        need(path, where)
        roles_of.setdefault(path, set()).add(role)

    for path in p.get("system_fields") or {}:
        tag(path, "system", "system_fields")
    for n in p.get("normalizers") or []:
        for path in n["outputs"].values():
            tag(path, "normalized", "normalizers.outputs")
        for path in n["inputs"].values():
            need(path, "normalizers.inputs")
    for path in p.get("generated_fields") or {}:
        tag(path, "generated", "generated_fields")
    for sr in p.get("system_records") or []:
        for path in sr["fields"]:
            tag(path, "system", "system_records.fields")
    for path in p.get("document_fields") or []:
        tag(path, "document", "document_fields")
    for link, spec in (p.get("record_links") or {}).items():
        tag(spec["field"], "linked", f"record_links.{link}")
        if idx[spec["field"]]["type"] != "array_string":
            raise ContractError(f"profile {name}: record_links.{link} -> {spec['field']} must be array_string")
        for k in spec.get("target_kinds") or []:
            if contract["record_kinds"] and k not in contract["record_kinds"]:
                raise ContractError(f"profile {name}: record_links.{link}: unknown record kind {k}")
    prov = (p.get("roles") or {}).get("provenance") or {}
    for role, path in prov.items():
        if role in EVIDENCE_ROLES:
            tag(path, "provenance", f"roles.provenance.{role}")
        else:
            need(path, f"roles.provenance.{role}")
    for path in (p.get("required_fields") or {}).get("always") or []:
        need(path, "required_fields.always")
    for path in (p.get("evidence_policy") or {}).get("value_presence_exempt") or []:
        need(path, "evidence_policy.value_presence_exempt")

    extra = [f["path"] for f in contract["fields"]
             if f["path"] not in selected and (f["path"] in roles_of or
                                                f["path"] in ((p.get("required_fields") or {}).get("always") or []))]
    final = selected + extra
    is_extraction = bool(p.get("model_record_kinds"))

    for role, path in {**prov, **((p.get("roles") or {}).get("semantic") or {})}.items():
        if path not in final:
            raise ContractError(f"profile {name}: role {role} -> {path} is not part of the profile field set")
    for n in p.get("normalizers") or []:
        for path in n["inputs"].values():
            if path not in final:
                raise ContractError(f"profile {name}: normalizer input {path} is not part of the profile")

    out_fields = []
    for path in final:
        f = idx[path]
        if is_extraction:
            role = next((r for r in ROLE_PRIORITY if r in roles_of.get(path, set())), "extract")
        else:
            role = "field"
        entry = {"path": path, "group": f["group"], "name": f["name"], "role": role, "type": f["type"],
                 "availability": f["availability"], "required": f["required"], "definition_zh": f["definition_zh"],
                 "data_source_zh": f.get("data_source_zh"), "maturity": f["maturity"], "since": f["since"]}
        for opt in ("vocabulary", "constraints", "status") + FIELD_ANNOTATIONS:
            if opt in f:
                entry[opt] = f[opt]
        out_fields.append(entry)

    vocab_names = sorted({f["vocabulary"] for f in out_fields if "vocabulary" in f})
    vocabularies = {}
    for vn in vocab_names:
        voc = contract["vocabularies"][vn]
        vocabularies[vn] = {"enforcement": voc.get("enforcement"), "closure": voc.get("closure"),
                            "code_status": voc.get("code_status"), "title_zh": voc.get("title_zh"),
                            "values": [{k: val[k] for k in ("code", "label_zh", "aliases") if k in val}
                                       for val in voc.get("values", [])]}
    kinds = list(p.get("model_record_kinds") or [])
    system_kinds = [sr["record_kind"] for sr in p.get("system_records") or []]
    for k in kinds + system_kinds:
        if contract["record_kinds"] and k not in contract["record_kinds"]:
            raise ContractError(f"profile {name}: unknown record kind {k}")
    record_kinds = {k: contract["record_kinds"].get(k, {}) for k in kinds + [s for s in system_kinds if s not in kinds]}

    resolved = {
        "profile_format": 1,
        "name": name,
        "extends_chain": chain,
        "title_zh": p["title_zh"],
        "description_zh": p["description_zh"],
        "contract": {"name": contract["name"], "version": contract["version"]},
        "is_extraction": is_extraction,
        "selection": sel,
        "fields": out_fields,
        "vocabularies": vocabularies,
        "record_kinds": record_kinds,
        "counts": {
            "total": len(out_fields),
            "by_role": dict(sorted(Counter(f["role"] for f in out_fields).items())),
            "by_availability": dict(sorted(Counter(f["availability"] for f in out_fields).items())),
            "by_group": dict(Counter(f["group"] for f in out_fields)),
        },
    }
    for key in ("document_fields", "document_defaults", "roles", "system_fields", "normalizers",
                "generated_fields", "system_records", "model_record_kinds", "record_links", "evidence_policy",
                "required_fields",
                "ambiguities", "source"):
        if key in p:
            resolved[key] = p[key]
    resolved["fill_rules"] = _fill_rules(p)
    return resolved


def resolve_all_profiles(contract: dict, raw_profiles: dict[str, dict]) -> dict[str, dict]:
    return {name: resolve_profile(contract, raw_profiles, name) for name in sorted(raw_profiles)}


def profile_field_set(profile: dict) -> list[str]:
    return [f["path"] for f in profile["fields"]]


def fields_by_role(profile: dict, *roles: str) -> list[dict]:
    return [f for f in profile["fields"] if f["role"] in roles]


def summarize(value: Any, limit: int = 80) -> str:
    s = str(value)
    return s if len(s) <= limit else s[: limit - 1] + "…"
