"""Cross-field rule engine for catalog ``rules``.

Each rule is evaluated by the validator. Error-level rules whose logic is expressible in JSON Schema
are additionally translated into ``allOf`` clauses of the published record schema, so consumers
using only JSON Schema get the same structural verdict (tested in tests/test_validation.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable

from .relations import span_matches
from .util import MISSING, get_path, iter_fields, iter_strings, split_path

RECORD_RULE_KINDS = {"required_when", "require_any_when", "paired", "mutually_exclusive", "lte",
                     "equals_any_field", "forbid_pattern", "grain_matches_kind", "offsets_match_text"}
DATASET_RULE_KINDS = {"unique_within_dataset", "single_value_per_group", "references_resolve"}


@dataclass
class Issue:
    code: str
    severity: str  # "error" | "warning"
    path: str
    message: str
    rule_id: str | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"code": self.code, "severity": self.severity, "path": self.path, "message": self.message}
        if self.rule_id:
            d["rule_id"] = self.rule_id
        if self.detail:
            d["detail"] = self.detail
        return d


def present(record: dict, path: str) -> bool:
    return get_path(record, path) is not MISSING


def eval_condition(cond: dict, record: dict) -> bool:
    if "all" in cond:
        return all(eval_condition(c, record) for c in cond["all"])
    if "any" in cond:
        return any(eval_condition(c, record) for c in cond["any"])
    if "present" in cond:
        return present(record, cond["present"])
    if "any_present" in cond:
        return any(present(record, p) for p in cond["any_present"])
    if "field" in cond:
        value = get_path(record, cond["field"])
        if value is MISSING:
            return False
        if "equals" in cond:
            return value == cond["equals"]
        if "in" in cond:
            return value in cond["in"]
        if "matches" in cond:
            return any(_compiled(cond["matches"]).search(s) for s in iter_strings(value))
    raise ValueError(f"unsupported condition: {cond}")


@lru_cache(maxsize=256)
def _compiled(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def check_record_rule(rule: dict, record: dict, record_kinds: dict) -> list[Issue]:
    kind, rid, sev = rule["kind"], rule["id"], rule["severity"]
    code = f"RULE_{rid}"
    title = rule["title_zh"]
    out: list[Issue] = []

    def issue(path: str, msg: str, **detail: Any) -> None:
        out.append(Issue(code, sev, path, f"{title}：{msg}", rid, detail))

    if kind == "required_when":
        if eval_condition(rule["when"], record):
            for p in rule["require"]:
                if not present(record, p):
                    issue(p, f"缺少 {p}")
    elif kind == "require_any_when":
        if eval_condition(rule["when"], record) and not any(present(record, p) for p in rule["require_any"]):
            issue(rule["require_any"][0], "至少需要其一：" + ", ".join(rule["require_any"]))
    elif kind == "paired":
        got = [p for p in rule["fields"] if present(record, p)]
        if 0 < len(got) < len(rule["fields"]):
            missing = [p for p in rule["fields"] if p not in got]
            issue(missing[0], f"{', '.join(got)} 已填写但缺少 {', '.join(missing)}")
    elif kind == "mutually_exclusive":
        got = [p for p in rule["fields"] if present(record, p)]
        if len(got) > 1:
            issue(got[1], "不得同时填写 " + ", ".join(got))
    elif kind == "lte":
        a, b = (get_path(record, p) for p in rule["fields"])
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) \
                and not isinstance(b, bool) and a > b:
            issue(rule["fields"][0], f"{rule['fields'][0]}={a} 大于 {rule['fields'][1]}={b}")
    elif kind == "equals_any_field":
        value = get_path(record, rule["field"])
        refs = [get_path(record, p) for p in rule["candidates"]]
        refs = [r for r in refs if r is not MISSING]
        if value is not MISSING and refs and value not in refs:
            issue(rule["field"], f"值 {value!r} 不等于 {', '.join(rule['candidates'])} 中任何一个")
    elif kind == "forbid_pattern":
        rx = _compiled(rule["pattern"])
        targets: Iterable[tuple[str, Any]]
        if rule["fields"] == ["*"]:
            targets = list(iter_fields(record))
        else:
            targets = [(p, get_path(record, p)) for p in rule["fields"]]
        for p, value in targets:
            if value is MISSING:
                continue
            for s in iter_strings(value):
                if rx.search(s):
                    issue(p, "值匹配禁止模式")
                    break
    elif kind == "grain_matches_kind":
        grain_path, kind_path = rule["fields"]
        grain, rkind = get_path(record, grain_path), get_path(record, kind_path)
        if grain is not MISSING and rkind is not MISSING and rkind in record_kinds:
            expected = record_kinds[rkind].get("grain")
            if expected and grain != expected:
                issue(grain_path, f"{rkind} 的粒度应为 {expected}，实际为 {grain}")
    elif kind == "offsets_match_text":
        text = get_path(record, rule["field"], None)

        def check(path: str, label: str, mention: Any, start: Any, end: Any) -> None:
            if start is MISSING and end is MISSING:
                return
            if start is MISSING or end is MISSING:
                issue(path, f"{label} 的起止偏移须成对出现")
            elif not span_matches(text, mention, start, end):
                issue(path, f"{label} 的偏移 {start}-{end} 处不是 {mention!r}", start=start, end=end)
        for p in rule.get("fields") or []:
            for n, item in enumerate(get_path(record, p, None) or []):
                if isinstance(item, dict):
                    check(p, f"{p}[{n}]", item.get("mention"), item.get("start", MISSING), item.get("end", MISSING))
        for span in rule.get("spans") or []:
            check(span["start"], span["mention"], get_path(record, span["mention"], None),
                  get_path(record, span["start"]), get_path(record, span["end"]))
    return out


def check_dataset_rule(rule: dict, records: list[dict]) -> list[tuple[int, Issue]]:
    out: list[tuple[int, Issue]] = []
    code, sev, title = f"RULE_{rule['id']}", rule["severity"], rule["title_zh"]
    if rule["kind"] == "unique_within_dataset":
        seen: dict[tuple, int] = {}
        for i, rec in enumerate(records):
            key = tuple(repr(get_path(rec, p, None)) for p in rule["fields"])
            if all(get_path(rec, p) is MISSING for p in rule["fields"]):
                continue
            if key in seen:
                out.append((i, Issue(code, sev, rule["fields"][0],
                                     f"{title}：与第 {seen[key] + 1} 行重复", rule["id"])))
            else:
                seen[key] = i
    elif rule["kind"] == "single_value_per_group":
        groups: dict[Any, tuple[Any, int]] = {}
        for i, rec in enumerate(records):
            g, v = get_path(rec, rule["group_by"]), get_path(rec, rule["field"])
            if g is MISSING or v is MISSING:
                continue
            if g in groups and groups[g][0] != v:
                out.append((i, Issue(code, sev, rule["field"],
                                     f"{title}：组 {g!r} 已在第 {groups[g][1] + 1} 行取值 {groups[g][0]!r}",
                                     rule["id"])))
            else:
                groups.setdefault(g, (v, i))
    elif rule["kind"] == "references_resolve":
        known = {v for rec in records for v in iter_strings(get_path(rec, rule["target"], None) or [])}
        for i, rec in enumerate(records):
            for p in rule["fields"]:
                value = get_path(rec, p)
                if value is MISSING:
                    continue
                dangling = [v for v in iter_strings(value) if v not in known]
                if dangling:
                    out.append((i, Issue(code, sev, p, f"{title}：{', '.join(dangling)} 不在本数据集的 "
                                                       f"{rule['target']} 中", rule["id"], {"unresolved": dangling})))
    return out


# ---------------------------------------------------------------- JSON Schema translation

def _present_schema(path: str) -> dict:
    g, n = split_path(path)
    return {"required": [g], "properties": {g: {"required": [n]}}}


def _cond_schema(cond: dict) -> dict:
    if "all" in cond:
        return {"allOf": [_cond_schema(c) for c in cond["all"]]}
    if "any" in cond:
        return {"anyOf": [_cond_schema(c) for c in cond["any"]]}
    if "present" in cond:
        return _present_schema(cond["present"])
    if "any_present" in cond:
        return {"anyOf": [_present_schema(p) for p in cond["any_present"]]}
    g, n = split_path(cond["field"])
    if "matches" in cond:  # only warning rules use `matches` (bdc check): Python regex flags are not ECMA-262
        raise ValueError(f"condition {cond} is not expressible in JSON Schema")
    value_schema = {"const": cond["equals"]} if "equals" in cond else {"enum": cond["in"]}
    return {"required": [g], "properties": {g: {"required": [n], "properties": {n: value_schema}}}}


def _require_schema(paths: list[str]) -> dict:
    by_group: dict[str, list[str]] = {}
    for p in paths:
        g, n = split_path(p)
        by_group.setdefault(g, []).append(n)
    parts = [{"required": [g], "properties": {g: {"required": names}}} for g, names in by_group.items()]
    return parts[0] if len(parts) == 1 else {"allOf": parts}


def rule_to_json_schema(rule: dict) -> dict | None:
    """Translate an error-level rule to JSON Schema, or return None when not expressible."""
    if rule["severity"] != "error":
        return None
    kind = rule["kind"]
    comment = f"{rule['id']} {rule['title_zh']}"
    if kind == "required_when":
        return {"$comment": comment, "if": _cond_schema(rule["when"]), "then": _require_schema(rule["require"])}
    if kind == "require_any_when":
        return {"$comment": comment, "if": _cond_schema(rule["when"]),
                "then": {"anyOf": [_present_schema(p) for p in rule["require_any"]]}}
    if kind == "paired":
        clauses = []
        for p in rule["fields"]:
            others = [q for q in rule["fields"] if q != p]
            clauses.append({"if": _present_schema(p), "then": _require_schema(others)})
        return {"$comment": comment, "allOf": clauses}
    if kind == "mutually_exclusive":
        fs = rule["fields"]
        pairs = [(a, b) for i, a in enumerate(fs) for b in fs[i + 1:]]
        return {"$comment": comment,
                "allOf": [{"not": {"allOf": [_present_schema(a), _present_schema(b)]}} for a, b in pairs]}
    if kind == "forbid_pattern" and rule["fields"] != ["*"]:
        # Type-guarded: `pattern` is vacuously true for non-strings, so an unguarded `not` would reject arrays.
        deny = {"not": {"type": "string", "pattern": rule["pattern"]}}
        by_group: dict[str, dict] = {}
        for p in rule["fields"]:
            g, n = split_path(p)
            by_group.setdefault(g, {})[n] = {**deny, "items": deny, "additionalProperties": deny}
        return {"$comment": comment,
                "properties": {g: {"properties": props} for g, props in by_group.items()}}
    return None
