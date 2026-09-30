"""Structural repair of backend output before record assembly.

Repairs change *shape and encoding only* — never content: flatten nesting, resolve bare field names, drop empty
values, move evidence keys into `evidence`, coerce JSON types where the conversion is lossless, and map
vocabulary labels/aliases/case variants to their codes. Every repair is logged. Anything that would need
judgement (unknown keys, fields outside the profile, unparseable numbers) is dropped or left for the validator,
never guessed.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

EMPTY = (None, "", [], {})
_REF = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def non_finite(value: Any) -> bool:
    """NaN/Infinity anywhere in a JSON value (Python's json accepts them; JSON and every validator do not)."""
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, list):
        return any(non_finite(v) for v in value)
    if isinstance(value, dict):
        return any(non_finite(v) for v in value.values())
    return False
_NUM = re.compile(r"^[-+]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?(?:[eE][-+]?\d+)?$")
_INT = re.compile(r"^[-+]?(?:\d+|\d{1,3}(?:,\d{3})+)$")


@dataclass
class RepairLog:
    entries: list[dict] = field(default_factory=list)

    def add(self, where: str, action: str, key: str | None = None, **detail: Any) -> None:
        e = {"where": where, "action": action}
        if key is not None:
            e["key"] = key
        e.update({k: v for k, v in detail.items() if v is not None})
        self.entries.append(e)


class Repairer:
    def __init__(self, profile: dict, contract: dict):
        self.profile = profile
        self.contract = contract
        self.fields = {f["path"]: f for f in profile["fields"]}
        self.contract_paths = {f["path"] for f in contract["fields"]}
        self.by_name: dict[str, list[str]] = {}
        for f in profile["fields"]:
            if f["role"] in ("extract", "document"):
                self.by_name.setdefault(f["name"], []).append(f["path"])
        prov = (profile.get("roles") or {}).get("provenance") or {}
        self.evidence_role_of = {path: role for role, path in prov.items()
                                 if role in ("page", "section", "quote", "table_figure", "row_key", "column_key")}
        self.evidence_roles = set(self.evidence_role_of.values())
        self.kinds = list(profile.get("model_record_kinds") or [])
        self.links = set(profile.get("record_links") or {})
        self.vocab_maps: dict[str, dict[str, str]] = {}
        for name, voc in profile["vocabularies"].items():
            m: dict[str, str] = {}
            for v in voc["values"]:
                for label in [v["code"], v.get("label_zh")] + list(v.get("aliases") or []):
                    if isinstance(label, str) and label.strip():
                        m.setdefault(label.strip().casefold(), v["code"])
            self.vocab_maps[name] = m

    # ------------------------------------------------------------------ helpers
    def flatten(self, obj: dict) -> dict:
        out = {}
        for k, v in obj.items():
            if isinstance(v, dict) and "." not in k and k in self.contract["groups"]:
                for x, y in v.items():
                    out[f"{k}.{x}"] = y
            else:
                out[k] = v
        return out

    def resolve_key(self, key: str, where: str, log: RepairLog) -> str | None:
        if key in self.contract_paths:
            return key
        if "." not in key:
            paths = self.by_name.get(key, [])
            if len(paths) == 1:
                log.add(where, "resolved_bare_field_name", key, to=paths[0])
                return paths[0]
            if len(paths) > 1:
                log.add(where, "dropped_ambiguous_field_name", key, candidates=paths)
                return None
        log.add(where, "dropped_unknown_field", key)
        return None

    def coerce(self, path: str, value: Any, where: str, log: RepairLog) -> Any:
        f = self.fields.get(path)
        if f is None:
            return value
        t = f["type"]
        new = value
        if t in ("integer", "number") and isinstance(value, str):
            s = value.strip()
            if path.endswith("_percent") and s.endswith("%"):
                s = s[:-1].strip()
            if (_INT if t == "integer" else _NUM).match(s):
                s = s.replace(",", "")
                new = int(s) if t == "integer" else (float(s) if any(c in s for c in ".eE") else int(s))
        elif t == "integer" and isinstance(value, float) and value.is_integer():
            new = int(value)
        elif t == "string" and isinstance(value, (int, float)) and not isinstance(value, bool):
            new = str(value)
        elif t == "array_string" and isinstance(value, str):
            new = [value]
        elif t == "array_string" and isinstance(value, list):
            new = [str(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x for x in value]
            new = [x for x in new if x not in EMPTY]
        elif t == "boolean" and isinstance(value, str) and value.strip().lower() in ("true", "false"):
            new = value.strip().lower() == "true"
        if new != value or type(new) is not type(value):
            log.add(where, "coerced_type", path, **{"from": value, "to": new})
        vname = f.get("vocabulary")
        if vname and vname in self.vocab_maps:
            new = self._vocab(path, vname, new, where, log)
        return new

    def _vocab(self, path: str, vname: str, value: Any, where: str, log: RepairLog) -> Any:
        m = self.vocab_maps[vname]
        codes = set(m.values())

        def one(v):
            if isinstance(v, str) and v not in codes:
                code = m.get(v.strip().casefold())
                if code:
                    log.add(where, "mapped_vocabulary_label", path, **{"from": v, "to": code, "vocabulary": vname})
                    return code
            return v
        if isinstance(value, list):
            return [one(v) for v in value]
        if isinstance(value, dict):
            return {k: one(v) for k, v in value.items()}
        return one(value)

    # ------------------------------------------------------------------ evidence
    def repair_evidence(self, ev: Any, where: str, log: RepairLog) -> dict:
        if not isinstance(ev, dict):
            if ev not in EMPTY:
                log.add(where, "dropped_malformed_evidence")
            return {}
        out = {}
        for k, v in ev.items():
            role = self.evidence_role_of.get(k, k)  # accept full field paths as evidence keys
            if role != k:
                log.add(where, "renamed_evidence_key", k, to=role)
            if role not in self.evidence_roles:
                log.add(where, "dropped_unknown_evidence_key", k)
                continue
            if isinstance(v, str):
                v = v.strip()
            if v in EMPTY:
                continue
            if non_finite(v):
                log.add(where, "dropped_non_finite_number", f"evidence.{role}")
                continue
            if role == "page" and isinstance(v, str) and v.isdigit():
                log.add(where, "coerced_type", "evidence.page", **{"from": v, "to": int(v)})
                v = int(v)
            elif role != "page" and isinstance(v, (int, float)) and not isinstance(v, bool):
                log.add(where, "coerced_type", f"evidence.{role}", **{"from": v, "to": str(v)})
                v = str(v)
            if role != "page" and not isinstance(v, str):
                log.add(where, "dropped_malformed_evidence_value", f"evidence.{role}", type=type(v).__name__)
                continue
            out[role] = v
        return out

    # ------------------------------------------------------------------ entry points
    def repair_document(self, document: Any, log: RepairLog) -> dict:
        if not isinstance(document, dict):
            return {}
        out = {}
        for k, v in self.flatten(document).items():
            path = self.resolve_key(k, "document", log)
            if path is None:
                continue
            if v in EMPTY:
                log.add("document", "dropped_empty_value", path)
                continue
            if non_finite(v):
                log.add("document", "dropped_non_finite_number", path)
                continue
            if self.fields.get(path, {}).get("role") != "document":
                log.add("document", "dropped_non_document_field", path)
                continue
            out[path] = self.coerce(path, v, "document", log)
        return out

    def repair_candidate(self, cand: Any, index: int, log: RepairLog) -> dict | None:
        where = f"candidates[{index}]"
        if not isinstance(cand, dict):
            log.add(where, "dropped_malformed_candidate")
            return None
        kind = cand.get("record_kind")
        if isinstance(kind, str) and kind not in self.kinds:
            fixed = next((k for k in self.kinds if k.casefold() == kind.strip().casefold()), None)
            if fixed:
                log.add(where, "normalized_record_kind", **{"from": kind, "to": fixed})
                kind = fixed
        evidence = self.repair_evidence(cand.get("evidence"), where, log)
        fields: dict = {}
        overrides: dict = {}
        raw_fields = cand.get("fields") if isinstance(cand.get("fields"), dict) else {}
        for k, v in self.flatten(raw_fields).items():
            path = self.resolve_key(k, where, log)
            if path is None:
                continue
            if isinstance(v, str):
                v = v.strip()
            if v in EMPTY:
                log.add(where, "dropped_empty_value", path)
                continue
            if non_finite(v):
                log.add(where, "dropped_non_finite_number", path)
                continue
            if path in self.evidence_role_of:
                role = self.evidence_role_of[path]
                ev = self.repair_evidence({role: v}, where, log)
                if role in ev and role not in evidence:
                    evidence[role] = ev[role]
                    log.add(where, "moved_to_evidence", path, role=role)
                continue
            role = self.fields.get(path, {}).get("role")
            if role == "document":
                overrides[path] = self.coerce(path, v, where, log)
                log.add(where, "document_field_override", path)
                continue
            if role != "extract":
                why = "computed_by_pipeline" if role else "not_in_profile"
                log.add(where, "dropped_field", path, reason=why)
                continue
            fields[path] = self.coerce(path, v, where, log)
        out = {"record_kind": kind, "fields": fields, "evidence": evidence}
        if overrides:
            out["document_overrides"] = overrides
        for opt in ("confidence", "note"):
            if cand.get(opt) not in EMPTY and not non_finite(cand[opt]):
                out[opt] = cand[opt]
        ref, links = self.repair_links(cand, where, log)
        if ref:
            out["ref"] = ref
        if links:
            out["links"] = links
        return out

    def repair_links(self, cand: dict, where: str, log: RepairLog) -> tuple[str | None, dict]:
        """`ref` (candidate-local name) and `links` ({link name: [ref, ...]}) as declared by profile record_links."""
        ref = cand.get("ref")
        if ref is not None:
            ref = str(ref).strip() if isinstance(ref, (str, int)) and not isinstance(ref, bool) else None
            if not ref or not _REF.match(ref):
                log.add(where, "dropped_malformed_ref", **{"value": cand.get("ref")})
                ref = None
        links: dict = {}
        raw = cand.get("links")
        if raw not in EMPTY and not isinstance(raw, dict):
            log.add(where, "dropped_malformed_links")
            raw = {}
        for name, refs in (raw or {}).items():
            if name not in self.links:
                log.add(where, "dropped_unknown_link", name, allowed=sorted(self.links))
                continue
            if isinstance(refs, (str, int)) and not isinstance(refs, bool):
                refs = [refs]
            if not isinstance(refs, list):
                log.add(where, "dropped_malformed_links", name)
                continue
            clean = []
            for r in refs:
                r = str(r).strip() if isinstance(r, (str, int)) and not isinstance(r, bool) else ""
                if r and r not in clean:
                    clean.append(r)
            if clean:
                links[name] = clean
        return ref, links


def repair_output(raw: dict, profile: dict, contract: dict) -> tuple[dict, list[dict | None], list[dict]]:
    """-> (document, candidates (None = dropped), repair log entries)"""
    r = Repairer(profile, contract)
    log = RepairLog()
    raw = raw if isinstance(raw, dict) else {}
    document = r.repair_document(raw.get("document"), log)
    cands = raw.get("candidates") if isinstance(raw.get("candidates"), list) else []
    repaired = [r.repair_candidate(c, i, log) for i, c in enumerate(cands)]
    return document, repaired, log.entries
