"""Record validation against a resolved contract version (and optionally a profile).

Validation = JSON Schema structure (fields, types, constraints, error-level vocabularies)
           + catalog rules (cross-field, error or warning)
           + warning-level vocabularies + deprecation notices
           + dataset rules (uniqueness, leakage groups) for whole files.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

import jsonschema

from .compile import field_index
from .rules import DATASET_RULE_KINDS, Issue, check_dataset_rule, check_record_rule
from .schema_gen import profile_schema, record_schema, strip_rules
from .util import MISSING, get_path, iter_fields

_REQ_RE = re.compile(r"'([^']+)' is a required property")


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"valid": self.valid, "errors": [i.to_dict() for i in self.errors],
                "warnings": [i.to_dict() for i in self.warnings]}


def _json_path(parts: Iterable) -> str:
    out = ""
    for i, p in enumerate(parts):
        if isinstance(p, int):
            out += f"[{p}]"
        else:
            out += ("." if i else "") + str(p)
    return out


class Validator:
    def __init__(self, contract: dict, profile: dict | None = None, schema: dict | None = None):
        self.contract = contract
        self.profile = profile
        self.fields = field_index(contract)
        if schema is None:
            schema = profile_schema(contract, profile) if profile else record_schema(contract)
        self.schema = schema
        self._structural = jsonschema.Draft202012Validator(strip_rules(schema))
        self.record_rules = [r for r in contract["rules"] if r["kind"] not in DATASET_RULE_KINDS]
        self.dataset_rules = [r for r in contract["rules"] if r["kind"] in DATASET_RULE_KINDS]
        self.warn_vocab = {}
        for f in contract["fields"]:
            vname = f.get("vocabulary")
            if vname:
                voc = contract["vocabularies"][vname]
                if voc.get("enforcement") == "warning":
                    self.warn_vocab[f["path"]] = (vname, {v["code"] for v in voc["values"]},
                                                  voc.get("applies_to", "value"))
        self.profile_fields = {f["path"] for f in profile["fields"]} if profile else None

    # -------------------------------------------------------------- structural
    def _schema_issues(self, record: dict) -> list[Issue]:
        issues = []
        for e in self._structural.iter_errors(record):
            base = list(e.absolute_path)
            kw = e.validator
            if kw == "required":
                m = _REQ_RE.search(e.message)
                name = m.group(1) if m else "?"
                path = _json_path(base + [name])
                issues.append(Issue("SCHEMA_REQUIRED", "error", path, f"缺少必填字段 {path}"))
            elif kw == "additionalProperties":
                allowed = set((e.schema or {}).get("properties", {}))
                for key in e.instance:
                    if key in allowed:
                        continue
                    path = _json_path(base + [key])
                    if len(base) == 1 and path in self.fields:
                        issues.append(Issue("PROFILE_FIELD_NOT_ALLOWED", "error", path,
                                            f"字段 {path} 属于契约但不在画像 {self.profile['name']} 中"
                                            if self.profile else f"字段 {path} 不允许出现"))
                    else:
                        issues.append(Issue("SCHEMA_UNKNOWN_FIELD", "error", path, f"契约中不存在字段 {path}"))
            elif kw == "const" and base == ["common", "schema_version"]:
                issues.append(Issue("SCHEMA_VERSION_MISMATCH", "error", "common.schema_version",
                                    f"记录声明版本 {e.instance!r}，校验版本为 {self.contract['version']}"))
            else:
                path = _json_path(base) or "<record>"
                issues.append(Issue(f"SCHEMA_{kw.upper()}", "error", path, e.message[:300]))
        return issues

    # -------------------------------------------------------------- public
    def validate(self, record: dict) -> ValidationResult:
        if not isinstance(record, dict):
            return ValidationResult([Issue("SCHEMA_TYPE", "error", "<record>", "记录必须是 JSON 对象")])
        issues = self._schema_issues(record)
        kinds = self.contract.get("record_kinds") or {}
        for rule in self.record_rules:
            issues.extend(check_record_rule(rule, record, kinds))
        for path, (vname, codes, applies) in self.warn_vocab.items():
            value = get_path(record, path)
            if value is MISSING:
                continue
            values = list(value.values()) if applies == "values" and isinstance(value, dict) else \
                (value if isinstance(value, list) else [value])
            unknown = [v for v in values if isinstance(v, str) and v not in codes]
            if unknown:
                issues.append(Issue("VOCAB_UNKNOWN_CODE", "warning", path,
                                    f"{path} 取值 {unknown} 不在词表 {vname} 中", detail={"vocabulary": vname}))
        for path, _ in iter_fields(record):
            f = self.fields.get(path)
            if f and f.get("status") == "deprecated":
                repl = f.get("replaced_by")
                issues.append(Issue("FIELD_DEPRECATED", "warning", path,
                                    f"{path} 已弃用" + (f"，请改用 {repl}" if repl else "")))
        return ValidationResult(issues)

    def validate_dataset(self, records: list[dict]) -> list[tuple[int, Issue]]:
        out: list[tuple[int, Issue]] = []
        for rule in self.dataset_rules:
            out.extend(check_dataset_rule(rule, records))
        return out
