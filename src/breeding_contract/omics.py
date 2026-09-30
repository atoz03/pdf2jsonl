"""Migrate instances of the omics 2.0.0 candidate template (grouped JSON, null = missing) to atomic records.

Driven by mappings/omics_to_current.yaml: ``mapped``/``merged`` leaves are copied to their target field
(scalars are wrapped into one-element arrays for array fields); ``partial`` leaves are copied only when the
value satisfies the target field's own schema; ``transformed`` leaves with non-trivial transformations and
``unmapped`` leaves go to the residue file. Nulls are omitted (OMX-008). Input: a JSON object, a JSON array of
objects, or JSONL — one template instance per record.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

from . import GENERATOR_VERSION
from .api import resolve_schema
from .ids import stable_record_id
from .mappings import entry_targets, match_entry
from .paths import repo_root
from .schema_gen import field_schema
from .util import (ContractError, canonical_json, dumps_json, dumps_jsonl, get_path, load_yaml, parse_semver, set_path,
                   sha256_file, utc_now)

EMPTY = (None, "", [], {})
SKIP_GROUPS = {"schema_info", "controlled_vocabularies"}
# transformed leaves whose transformation is a plain copy — others (relation_claim, compose, structure) go to residue
SIMPLE_TRANSFORMS = {"wrap_array", "single_value_measurement"}


def _read_instances(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return [x for x in json.loads(text) if isinstance(x, dict)]
    if text.startswith("{") and "\n{" not in text:
        return [json.loads(text)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class OmicsMigrator:
    def __init__(self, rc, mapping: dict, record_kind: str | None, dataset_id: str | None, run_id: str):
        self.rc = rc
        self.contract = rc.contract
        self.fields = {f["path"]: f for f in self.contract["fields"]}
        self.mapping = mapping
        self.record_kind = record_kind
        self.dataset_id = dataset_id
        self.run_id = run_id
        self.validator = rc.validator()
        self._field_validators: dict[str, jsonschema.Draft202012Validator] = {}

    def _fits(self, path: str, value: Any) -> bool:
        if path not in self._field_validators:
            self._field_validators[path] = jsonschema.Draft202012Validator(
                field_schema(self.contract, self.fields[path], annotate=False))
        return self._field_validators[path].is_valid(value)

    def _coerce(self, path: str, value: Any) -> Any:
        t = self.fields[path]["type"]
        if t == "array_string" and isinstance(value, (str, int, float)) and not isinstance(value, bool):
            return [str(value)]
        if t == "string" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return value

    def migrate(self, inst: dict) -> tuple[dict | None, list[dict], list[dict]]:
        rec: dict = {}
        residue: list[dict] = []
        conflicts: list[dict] = []
        for group, members in inst.items():
            if group in SKIP_GROUPS or not isinstance(members, dict):
                continue
            for leaf, value in members.items():
                if value in EMPTY:
                    continue
                src = f"{group}.{leaf}"
                entry = match_entry(self.mapping["entries"], src)
                status = entry["status"] if entry else "not_in_template"
                targets = entry_targets(entry) if entry else []
                ok = False
                if status in ("mapped", "merged", "partial") or \
                        (status == "transformed" and entry.get("transform") in SIMPLE_TRANSFORMS):
                    if len(targets) == 1 and targets[0] in self.fields:
                        path = targets[0]
                        v = self._coerce(path, value)
                        if self._fits(path, v):
                            existing = get_path(rec, path, None)
                            if existing is None:
                                set_path(rec, path, v)
                                ok = True
                            elif existing == v:
                                ok = True
                            elif isinstance(existing, list) and isinstance(v, list):
                                set_path(rec, path, existing + [x for x in v if x not in existing])
                                ok = True
                            else:
                                conflicts.append({"source": src, "target": path, "value": value, "existing": existing})
                if not ok:
                    residue.append({"path": src, "value": value, "mapping": (
                        {k: entry[k] for k in ("status", "target", "targets", "note_zh", "issues") if k in entry}
                        if entry else {"status": status})})
        kind = get_path(rec, "common.record_kind", None)
        if kind not in (self.contract.get("record_kinds") or {}):
            if kind is not None:
                residue.append({"path": "basic_identity.record_type", "value": kind,
                                "mapping": {"status": "partial", "note_zh": "不是 record_kind 词表代码（OMX-002）"}})
            kind = self.record_kind
        if not kind:
            return None, residue, conflicts
        set_path(rec, "common.record_kind", kind)
        source_id = get_path(rec, "common.source_id", None)
        doi = get_path(rec, "common.source_doi", None)
        if source_id is None and isinstance(doi, str):
            source_id = "doi:" + doi.lower()
            set_path(rec, "common.source_id", source_id)
        if isinstance(doi, str) and get_path(rec, "common.source_uri", None) is None:
            set_path(rec, "common.source_uri", "https://doi.org/" + doi)
        original_id = get_path(rec, "common.record_id", None)
        if original_id is not None:
            set_path(rec, "common.source_record_id", str(original_id))
        # Without an instance ID the record is identified by its content, never by its position in the file.
        anchor = f"omics:{original_id}" if original_id is not None else \
            "omics:sha256=" + hashlib.sha256(canonical_json(inst).encode("utf-8")).hexdigest()[:16]
        set_path(rec, "common.record_id", stable_record_id(str(source_id), kind, anchor,
                                                           get_path(rec, "common.source_quote", None)))
        grain = (self.contract["record_kinds"].get(kind) or {}).get("grain")
        system = {"common.schema_name": self.rc.name, "common.schema_version": self.rc.version,
                  "common.record_grain": grain, "common.record_version": 1, "common.extraction_run_id": self.run_id,
                  "common.qc_rule_set_version": f"{self.rc.name}@{self.rc.version}+omics-migration@{GENERATOR_VERSION}",
                  "common.dataset_id": self.dataset_id}
        for p, v in system.items():
            if v not in EMPTY:
                set_path(rec, p, v)
        if get_path(rec, "common.source_locator", None) is None:
            set_path(rec, "common.source_locator", "document")
        if get_path(rec, "common.review_status", None) is None:
            set_path(rec, "common.review_status", "pending_review")
        codes = sorted(set(get_path(rec, "common.qc_failure_codes", []) or []) | {"OMICS_MIGRATED"} |
                       ({"OMICS_FIELD_CONFLICT"} if conflicts else set()))
        set_path(rec, "common.qc_failure_codes", codes)
        return rec, residue, conflicts


def migrate_omics_file(path: Path | str, out_dir: Path | str, version: str = "latest", record_kind: str | None = None,
                       dataset_id: str | None = None, root: Path | str | None = None) -> dict:
    root = repo_root(root)
    path, out_dir = Path(path), Path(out_dir)
    rc = resolve_schema(version, root)
    if parse_semver(rc.version.split("-")[0]) < (3, 1, 0):
        raise ContractError(f"omics migration targets contract >= 3.1.0 (got {rc.version})")
    mapping = load_yaml(root / "mappings/omics_to_current.yaml")
    started = utc_now()
    run_id = "mig_" + started.strftime("%Y%m%dT%H%M%SZ") + "_" + sha256_file(path)[:8]
    mig = OmicsMigrator(rc, mapping, record_kind, dataset_id, run_id)
    records, rejected, residue = [], [], []
    for n, inst in enumerate(_read_instances(path), 1):
        rec, res, conflicts = mig.migrate(inst)
        residue += [{**r, "instance": n} for r in res]
        if rec is None:
            rejected.append({"error_format": 1, "stage": "migration", "code": "RECORD_KIND_UNKNOWN", "instance": n,
                             "message": "无法确定 record_kind：模板 record_type 不是词表代码，且未提供 --record-kind"})
            continue
        result = mig.validator.validate(rec)
        if result.valid:
            records.append((n, rec))
        else:
            rejected.append({"error_format": 1, "stage": "migration", "code": "RECORD_INVALID", "instance": n,
                             "message": "迁移记录未通过契约校验", "issues": [i.to_dict() for i in result.errors],
                             "conflicts": conflicts, "record": rec})
    bad: dict[int, list] = {}
    for idx, issue in mig.validator.validate_dataset([r for _, r in records]):
        if issue.severity == "error":
            bad.setdefault(idx, []).append(issue)
    for idx in sorted(bad, reverse=True):
        n, rec = records.pop(idx)
        rejected.append({"error_format": 1, "stage": "dataset", "code": "DATASET_RULE", "instance": n,
                         "message": bad[idx][0].message, "issues": [i.to_dict() for i in bad[idx]], "record": rec})
    rejected.sort(key=lambda e: e.get("instance", 0))
    records = [r for _, r in records]
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    outs = {"records": out_dir / f"{stem}.migrated.jsonl", "errors": out_dir / f"{stem}.migrated.errors.jsonl",
            "residue": out_dir / f"{stem}.residue.json", "report": out_dir / f"{stem}.migration.json"}
    outs["records"].write_text(dumps_jsonl(records), encoding="utf-8")
    outs["errors"].write_text(dumps_jsonl(rejected), encoding="utf-8")
    outs["residue"].write_text(dumps_json({"residue_format": 1, "source": path.name, "unconsumed": residue}),
                               encoding="utf-8")
    counts = {"records": len(records), "rejected": len(rejected), "residue_leaves": len(residue)}
    report = {"migration_format": 1, "run_id": run_id, "created_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "source": {"file_name": path.name, "sha256": sha256_file(path), "template_version": "2.0.0"},
              "contract": rc.identity(),
              "mapping": {"id": mapping["id"], "sha256": sha256_file(root / "mappings/omics_to_current.yaml")},
              "options": {"record_kind": record_kind, "dataset_id": dataset_id}, "counts": counts,
              "outputs": {k: {"file": p.name, "sha256": sha256_file(p)} for k, p in outs.items() if k != "report"},
              "tooling": {"breeding_contract": GENERATOR_VERSION}}
    outs["report"].write_text(dumps_json(report), encoding="utf-8")
    return {"outputs": {k: str(v) for k, v in outs.items()}, **counts}
