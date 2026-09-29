"""Semantic-version discipline between two compiled contracts (docs/versioning.md).

``required_bump(old, new)`` classifies the change set. ``bdc check`` compares consecutive releases and the working
tree against the latest release, and fails when the declared VERSION bump is smaller than required.

* major — a record valid under ``old`` may become invalid or change meaning: field removed, type changed,
  requirement tightened to Y, error-enforced vocabulary code removed or enforcement raised to error,
  constraint added/tightened, an error rule added or a warning rule raised to error over fields that existed.
* minor — additive: fields, vocabulary codes, vocabularies, record kinds, profiles, warning rules, error rules
  over new fields only, provisional → verified.
* patch — anything else that changes the compiled contract (wording, source references, ambiguity notes).
"""
from __future__ import annotations

from .schema_gen import rule_paths

LEVELS = ("none", "patch", "minor", "major")


def _vocab_codes(v: dict) -> set[str]:
    return {x["code"] for x in v.get("values", [])}


def required_bump(old: dict, new: dict, old_profiles: dict | None = None,
                  new_profiles: dict | None = None) -> tuple[str, list[tuple[str, str]]]:
    reasons: list[tuple[str, str]] = []
    add = lambda level, msg: reasons.append((level, msg))  # noqa: E731
    fo = {f["path"]: f for f in old["fields"]}
    fn = {f["path"]: f for f in new["fields"]}
    for p, f in fo.items():
        g = fn.get(p)
        if g is None:
            add("major", f"field {p} removed")
            continue
        if f["type"] != g["type"]:
            add("major", f"{p}: type {f['type']} -> {g['type']}")
        if g["required"] == "Y" and f["required"] != "Y":
            add("major", f"{p}: required {f['required']} -> Y")
        if f["availability"] != g["availability"]:
            add("major", f"{p}: availability {f['availability']} -> {g['availability']}")
        if (f.get("constraints") or {}) != (g.get("constraints") or {}):
            add("major", f"{p}: constraints changed")
        if f.get("vocabulary") != g.get("vocabulary") and g.get("vocabulary"):
            enforcement = new["vocabularies"][g["vocabulary"]].get("enforcement")
            add("major" if enforcement == "error" else "minor", f"{p}: bound to vocabulary {g['vocabulary']}")
        if f.get("maturity") != g.get("maturity"):
            add("minor", f"{p}: maturity {f.get('maturity')} -> {g.get('maturity')}")
        if f.get("status") != g.get("status"):
            add("minor", f"{p}: status {f.get('status')} -> {g.get('status')}")
        if f["definition_zh"] != g["definition_zh"]:
            add("patch", f"{p}: definition wording changed (confirm the meaning is unchanged)")
    for p in fn:
        if p not in fo:
            add("minor", f"field {p} added")
    for name, v in old["vocabularies"].items():
        w = new["vocabularies"].get(name)
        if w is None:
            add("major", f"vocabulary {name} removed")
            continue
        removed = _vocab_codes(v) - _vocab_codes(w)
        if removed and w.get("enforcement") == "error":
            add("major", f"vocabulary {name}: codes removed {sorted(removed)}")
        elif removed:
            add("minor", f"vocabulary {name}: codes removed {sorted(removed)} (not enforced)")
        if w.get("enforcement") == "error" and v.get("enforcement") != "error":
            add("major", f"vocabulary {name}: enforcement raised to error")
        if _vocab_codes(w) - _vocab_codes(v):
            add("minor", f"vocabulary {name}: codes added")
    for name in new["vocabularies"]:
        if name not in old["vocabularies"]:
            add("minor", f"vocabulary {name} added")
    ro = {r["id"]: r for r in old["rules"]}
    for r in new["rules"]:
        prev = ro.get(r["id"])
        if r["severity"] == "error" and (prev is None or prev["severity"] != "error"):
            touches_old = any(p in fo for p in rule_paths(r) if p != "*") or rule_paths(r) == ["*"]
            add("major" if touches_old else "minor", f"rule {r['id']} is an error rule over "
                f"{'existing' if touches_old else 'new'} fields")
        elif prev is None:
            add("minor", f"rule {r['id']} added (warning)")
        elif {k: v for k, v in prev.items() if k not in ("source_zh", "title_zh", "ambiguities")} != \
                {k: v for k, v in r.items() if k not in ("source_zh", "title_zh", "ambiguities")}:
            add("major" if r["severity"] == "error" else "minor", f"rule {r['id']} changed")
    for rid in ro:
        if rid not in {r["id"] for r in new["rules"]}:
            add("minor", f"rule {rid} removed")
    for k in set(old.get("record_kinds") or {}) - set(new.get("record_kinds") or {}):
        add("major", f"record kind {k} removed")
    if old_profiles is not None and new_profiles is not None:
        for name in old_profiles:
            if name not in new_profiles:
                add("major", f"profile {name} removed")
        for name in new_profiles:
            if name not in old_profiles:
                add("minor", f"profile {name} added")
    if not reasons and old.get("source_digest") != new.get("source_digest"):
        add("patch", "contract sources changed (wording, references or notes)")
    level = max((lvl for lvl, _ in reasons), key=LEVELS.index, default="none")
    return level, reasons


def declared_bump(old_version: str, new_version: str) -> str:
    a = tuple(int(x) for x in old_version.split("-")[0].split("."))
    b = tuple(int(x) for x in new_version.split("-")[0].split("."))
    if b[0] != a[0]:
        return "major"
    if b[1] != a[1]:
        return "minor"
    return "patch" if b[2] != a[2] else "none"
