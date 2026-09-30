"""PDF -> atomic JSONL records under an explicitly resolved contract version.

    resolve contract+profile -> parse layout -> backend candidates -> structural repair -> evidence verification
    -> record assembly (document, provenance, extracted, normalized, generated, system fields)
    -> validation -> review fields -> re-validation -> system records -> dataset rules -> outputs

Outputs (stem = input file name without extension):
    <stem>.jsonl              accepted records (valid; warnings => review_status needs review)
    <stem>.errors.jsonl       rejected candidates/records with reasons (never silently dropped)
    <stem>.validation.json    validation report
    <stem>.manifest.json      resolved schema version, profile, input hash, pipeline/backend/environment
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

from . import PIPELINE_VERSION, SUPPORTED_CONTRACT, SUPPORTED_MAJORS
from .contract_link import ensure_contract_importable, sha256_file

ensure_contract_importable()
from breeding_contract import GENERATOR_VERSION, resolve_schema  # noqa: E402
from breeding_contract.argument import argument_audit  # noqa: E402
from breeding_contract.ids import normalize_text  # noqa: E402
from breeding_contract.rules import Issue  # noqa: E402
from breeding_contract.util import (MISSING, ContractError, del_path, dumps_json, dumps_jsonl, get_path,  # noqa: E402
                                    set_path, utc_now)

from .backends import load_backend  # noqa: E402
from .brief import candidates_skeleton, render_brief  # noqa: E402
from .evidence import EvidenceIndex  # noqa: E402
from .fill_rules import IMPLEMENTED_RULES, REGISTRY, RecordContext, RunContext  # noqa: E402
from .pdf_parse import ParsedDocument, parse_document  # noqa: E402
from .repair import repair_output  # noqa: E402

EMPTY = (None, "", [], {})
EVIDENCE_ROLES = ("page", "section", "quote", "table_figure", "row_key", "column_key")
ID_ANCHOR_ROLES = ("page", "table_figure", "row_key", "column_key")  # the section is not part of record identity


class PipelineError(Exception):
    """Contract/usage problem: nothing is written."""


@dataclass
class RunOptions:
    profile: str = "pdf_extraction"
    schema_version: str = "latest"
    backend: str = "candidates"
    candidates_file: str | None = None
    out_dir: str | None = None
    text_layer: str | None = None
    dataset_id: str | None = None
    dataset_version: str | None = None
    source_asset_id: str | None = None
    asset_uri: str | None = None
    run_id: str | None = None
    allow_unreleased: bool = False
    bundle: bool = False

    def cli_values(self) -> dict:
        return {k: v for k, v in asdict(self).items()
                if k in ("dataset_id", "dataset_version", "source_asset_id", "asset_uri") and v not in (None, "")}


@dataclass
class RunResult:
    outputs: dict[str, Path]
    counts: dict
    manifest: dict
    records: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------- resolution
def resolve_contract(version: str, profile_name: str, allow_unreleased: bool = False):
    try:
        rc = resolve_schema(version)
    except ContractError as e:
        raise PipelineError(str(e)) from e
    if rc.name != SUPPORTED_CONTRACT:
        raise PipelineError(f"contract {rc.name!r} is not supported by pdf2jsonl (expects {SUPPORTED_CONTRACT})")
    major = int(rc.version.split(".")[0])
    if major not in SUPPORTED_MAJORS:
        raise PipelineError(f"contract {rc.version} has major version {major}; this pipeline supports "
                            f"{', '.join(map(str, SUPPORTED_MAJORS))}. Update the Skill runtime.")
    if rc.status != "released" and not allow_unreleased:
        raise PipelineError(f"contract {rc.version} is unreleased; production output requires a released version "
                            "(use --allow-unreleased for development runs only)")
    try:
        profile = rc.profile(profile_name)
    except ContractError as e:
        raise PipelineError(str(e)) from e
    if not profile.get("is_extraction"):
        raise PipelineError(f"profile {profile_name!r} is not an extraction profile")
    missing = sorted(set(profile["fill_rules"]) - IMPLEMENTED_RULES)
    if missing:
        raise PipelineError(f"profile {profile_name} ({rc.version}) needs fill rules not implemented by "
                            f"pdf2jsonl {PIPELINE_VERSION}: {', '.join(missing)}")
    return rc, profile


def output_stem(path: Path) -> str:
    name = path.name
    for ext in (".pages.jsonl", ".pdf", ".txt"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return path.stem


def _iso(t: _dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _environment() -> dict:
    pkgs = {}
    for name in ("jsonschema", "PyYAML", "pypdf"):
        try:
            pkgs[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    return {"python": platform.python_version(), "platform": platform.platform(terse=True), "packages": pkgs}


# ---------------------------------------------------------------------------------------------- assembly
class Assembler:
    def __init__(self, run: RunContext, index: EvidenceIndex):
        self.run = run
        self.index = index
        p = run.profile
        self.profile = p
        self.fields = {f["path"]: f for f in p["fields"]}
        self.order = [f["path"] for f in p["fields"]]
        self.group_order = list(run.rc.contract["groups"])
        self.prov = (p.get("roles") or {}).get("provenance") or {}
        self.policy = p.get("evidence_policy") or {}
        self.exempt = set(self.policy.get("value_presence_exempt") or [])
        sys_fields = list((p.get("system_fields") or {}).items())
        self.phase1 = sorted([(k, s) for k, s in sys_fields if REGISTRY[s["rule"]].phase == 1],
                             key=lambda kv: REGISTRY[kv[1]["rule"]].order)
        self.phase2 = [(k, s) for k, s in sys_fields if REGISTRY[s["rule"]].phase == 2]
        self.validator = run.rc.validator(p["name"])
        self.document_issues: list[Issue] = []

    # -- helpers
    @staticmethod
    def _apply(ctx: RecordContext, path: str, spec: dict) -> None:
        v = REGISTRY[spec["rule"]].fn(ctx, spec.get("params") or {})
        if v is MISSING or v in EMPTY:
            del_path(ctx.record, path)
        else:
            set_path(ctx.record, path, v)

    def _ordered(self, record: dict) -> dict:
        out: dict = {}
        for path in self.order:
            v = get_path(record, path)
            if v is not MISSING:
                set_path(out, path, v)
        extra = {g: {k: v for k, v in grp.items() if get_path(out, f"{g}.{k}") is MISSING}
                 for g, grp in record.items() if isinstance(grp, dict)}
        for g, grp in extra.items():  # out-of-profile keys (should not happen) are kept so validation reports them
            for k, v in grp.items():
                set_path(out, f"{g}.{k}", v)
        return {g: out[g] for g in self.group_order if g in out} | {g: v for g, v in out.items()
                                                                     if g not in self.group_order}

    def _present(self, value: Any, pages: list[int]) -> str | None:
        """None if literally present on one of ``pages``; else the warning code."""
        items = value if isinstance(value, list) else [value]
        for v in items:
            if isinstance(v, bool) or not isinstance(v, (str, int, float)):
                continue
            if any(self.index.value_present(v, p) for p in pages):
                continue
            return "VALUE_NOT_ON_EVIDENCE_PAGE" if self.index.value_present(v) else "VALUE_NOT_IN_SOURCE"
        return None

    # -- document level
    def check_document(self, document: dict, explicit: set[str]) -> None:
        level = self.policy.get("value_presence_check", "off")
        if level == "off":
            return
        for path, value in document.items():
            f = self.fields.get(path, {})
            if path not in explicit or path in self.exempt or f.get("vocabulary"):
                continue
            items = value if isinstance(value, list) else [value]
            missing = [v for v in items if isinstance(v, (str, int, float)) and not isinstance(v, bool)
                       and not self.index.value_present(v)]
            if missing:
                self.document_issues.append(Issue("DOCUMENT_VALUE_NOT_IN_SOURCE", level, path,
                                                  f"文档级字段 {path} 的取值在原文中找不到", detail={"value": value}))

    # -- evidence
    def verify_evidence(self, cand: dict) -> tuple[dict, tuple[int, int] | None, list[Issue], dict | None]:
        """-> (evidence, span, warnings, rejection)"""
        ev = dict(cand.get("evidence") or {})
        warnings: list[Issue] = []
        page, quote = ev.get("page"), ev.get("quote")
        page_path = self.prov.get("page", "evidence.page")

        def reject(code: str, msg: str, **detail):
            return ev, None, warnings, {"code": code, "message": msg, **({"detail": detail} if detail else {})}
        if self.policy.get("required_for_model_records", True) and (page in EMPTY or quote in EMPTY):
            return reject("EVIDENCE_MISSING", "候选记录缺少 evidence.page 或 evidence.quote")
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= self.run.doc.page_count:
            return reject("EVIDENCE_PAGE_INVALID", f"页码 {page!r} 不是 1..{self.run.doc.page_count} 的物理页码")
        max_chars = self.policy.get("max_quote_chars")
        if max_chars and len(quote) > max_chars:
            return reject("EVIDENCE_QUOTE_TOO_LONG", f"引文超过 {max_chars} 字符（须为最小原文证据）")
        span = None
        if self.policy.get("verify_quote", True):
            radius = int(self.policy.get("page_search_radius", 0))
            m = self.index.locate(quote, page, radius)
            if m is None:
                return reject("EVIDENCE_QUOTE_NOT_FOUND", f"引文在第 {page} 页（±{radius}）中找不到",
                              stated_page=page, radius=radius)
            if m.page_corrected:
                warnings.append(Issue("EVIDENCE_PAGE_CORRECTED", "warning", page_path,
                                      f"引文实际位于第 {m.page} 页（候选声明第 {page} 页）",
                                      detail={"stated_page": page, "found_page": m.page}))
                ev["page"] = m.page
            span = (m.start, m.end)
            if "section" not in ev:
                sec = self.index.section_at(m.page, m.start)
                if sec:
                    ev["section"] = sec
            for role, code in (("table_figure", "EVIDENCE_TABLE_NOT_ON_PAGE"), ("row_key", "EVIDENCE_CELL_KEY_NOT_ON_PAGE"),
                               ("column_key", "EVIDENCE_CELL_KEY_NOT_ON_PAGE")):
                if ev.get(role) and not any(self.index.page_mentions(p, str(ev[role]))
                                            for p in (m.page - 1, m.page, m.page + 1)
                                            if 1 <= p <= self.run.doc.page_count):
                    warnings.append(Issue(code, "warning", self.prov.get(role, role),
                                          f"{role}={ev[role]!r} 未出现在证据页附近"))
        return ev, span, warnings, None

    def value_warnings(self, cand: dict, page: int) -> list[Issue]:
        level = self.policy.get("value_presence_check", "off")
        if level == "off":
            return []
        radius = int(self.policy.get("page_search_radius", 0))
        pages = [p for p in range(page - radius, page + radius + 1) if 1 <= p <= self.run.doc.page_count]
        out = []
        for path, value in cand["fields"].items():
            if path in self.exempt or self.fields.get(path, {}).get("vocabulary"):
                continue
            code = self._present(value, pages)
            if code:
                out.append(Issue(code, level, path, f"{path} 的取值未在证据页（±{radius}）逐字出现",
                                 detail={"value": value}))
        return out

    # -- records
    def build(self, kind: str, *, candidate: dict | None, evidence: dict, span, ordinal: int,
              pre_issues: list[Issue], extra_fields: list[tuple[str, dict]] = (),
              links: dict[str, list[str]] | None = None) -> tuple[dict, RecordContext]:
        ctx = RecordContext(self.run, kind, {}, candidate=candidate, evidence=evidence, span=span, ordinal=ordinal)
        doc_values = {**self.run.document, **((candidate or {}).get("document_overrides") or {})}
        for path, v in doc_values.items():
            set_path(ctx.record, path, v)
        for role, v in evidence.items():
            if role in self.prov:
                set_path(ctx.record, self.prov[role], v)
        for path, v in ((candidate or {}).get("fields") or {}).items():
            set_path(ctx.record, path, v)
        for path, ids in (links or {}).items():
            set_path(ctx.record, path, ids)
        if candidate is not None:
            for n in self.profile.get("normalizers") or []:
                for path, v in REGISTRY[n["rule"]].fn(ctx, n).items():
                    set_path(ctx.record, path, v)
            for path, spec in (self.profile.get("generated_fields") or {}).items():
                self._apply(ctx, path, spec)
        for path, spec in extra_fields:
            self._apply(ctx, path, spec)
        for path, spec in self.phase1:
            self._apply(ctx, path, spec)
        doc_issues = [i for i in self.document_issues if get_path(ctx.record, i.path) is not MISSING]
        self.review(ctx, list(pre_issues) + doc_issues)
        return ctx.record, ctx

    def review(self, ctx: RecordContext, pre: list[Issue]) -> None:
        """Validate and (re)compute the phase-2 review fields, which depend on the warnings. Also used after
        dataset rules add warnings, so review_status / qc_failure_codes always match the reported warnings."""
        ctx.issues = pre + self.validator.validate(ctx.record).issues
        seen_codes = None
        for _ in range(3):  # review fields depend on warnings; re-run until stable
            for path, spec in self.phase2:
                self._apply(ctx, path, spec)
            ctx.issues = pre + self.validator.validate(ctx.record).issues
            codes = sorted({i.code for i in ctx.issues if i.severity == "warning"})
            if codes == seen_codes:
                break
            seen_codes = codes
        ctx.record = self._ordered(ctx.record)
        ctx.pre = pre


# ---------------------------------------------------------------------------------------------- run
def _candidate_problems(cand: dict | None, kinds: set[str]) -> dict | None:
    if cand is None:
        return {"code": "CANDIDATE_MALFORMED", "message": "候选不是 JSON 对象"}
    if not isinstance(cand.get("record_kind"), str) or cand["record_kind"] not in kinds:
        return {"code": "CANDIDATE_RECORD_KIND", "message": f"record_kind {cand.get('record_kind')!r} 不在画像允许的类型中",
                "detail": {"allowed": sorted(kinds)}}
    if not cand.get("fields"):
        return {"code": "CANDIDATE_NO_FIELDS", "message": "候选修复后没有任何可抽取字段"}
    return None


def run(input_path: Path | str, opts: RunOptions) -> RunResult:
    input_path = Path(input_path)
    started = utc_now()
    rc, profile = resolve_contract(opts.schema_version, opts.profile, opts.allow_unreleased)
    backend = load_backend(opts.backend)
    try:
        doc = parse_document(input_path, opts.text_layer)
    except (ValueError, RuntimeError, OSError) as e:
        raise PipelineError(str(e)) from e
    run_key = f"{doc.sha256}|{profile['name']}|{rc.version}|{opts.backend}"
    run_id = opts.run_id or "run_{}_{}".format(started.strftime("%Y%m%dT%H%M%SZ"),
                                               hashlib.sha256(run_key.encode()).hexdigest()[:8])
    options = {"candidates_file": opts.candidates_file, **opts.cli_values()}
    raw = backend.extract(doc, profile, rc, options)
    document, candidates, repairs = repair_output(raw, profile, rc.contract)
    defaults = dict(profile.get("document_defaults") or {})
    run_ctx = RunContext(rc=rc, profile=profile, doc=doc, backend=backend.info(), run_id=run_id,
                         options=opts.cli_values(), document={**defaults, **document})
    index = EvidenceIndex(doc)
    asm = Assembler(run_ctx, index)
    asm.check_document(run_ctx.document, explicit=set(document))

    kinds = set(profile.get("model_record_kinds") or [])
    accepted: list[tuple[dict, RecordContext, int | None]] = []
    rejected: list[dict] = []
    seen: dict = {}
    ordinals: dict[int, int] = {}

    def reject(stage: str, idx: int | None, problem: dict, cand=None, record=None, issues=None):
        e = {"error_format": 1, "stage": stage, "code": problem["code"], "message": problem["message"]}
        if idx is not None:
            e["candidate_index"] = idx
        if problem.get("detail"):
            e["detail"] = problem["detail"]
        if issues:
            e["issues"] = [i.to_dict() for i in issues]
        if cand is not None:
            e["candidate"] = cand
        if record is not None:
            e["record"] = record
        rejected.append(e)

    # system records first (they describe the input itself)
    skipped_system = []
    for sr in profile.get("system_records") or []:
        ctx0 = RecordContext(run_ctx, sr["record_kind"], {})
        if not REGISTRY[sr["rule"]].fn(ctx0, sr.get("params") or {}):
            skipped_system.append({"record_kind": sr["record_kind"], "reason": ctx0.notes.get("skipped", "rule declined")})
            continue
        rec, ctx = asm.build(sr["record_kind"], candidate=None, evidence={}, span=None, ordinal=0, pre_issues=[],
                             extra_fields=list(sr["fields"].items()))
        errs = [i for i in ctx.issues if i.severity == "error"]
        if errs:
            reject("validation", None, {"code": "RECORD_INVALID", "message": f"系统记录 {sr['record_kind']} 未通过校验"},
                   record=rec, issues=errs)
        else:
            accepted.append((rec, ctx, None))

    # pass 1: shape, evidence and duplicates
    verified: list[tuple[int, dict, dict, Any, list[Issue]]] = []
    ref_alias: dict[str, str] = {}
    for i, cand in enumerate(candidates):
        problem = _candidate_problems(cand, kinds)
        if problem:
            reject("candidate", i, problem, cand=cand)
            continue
        ev, span, pre, problem = asm.verify_evidence(cand)
        if problem:
            reject("evidence", i, problem, cand=cand)
            continue
        anchor = tuple(str(ev.get(r)) for r in ID_ANCHOR_ROLES) + (normalize_text(ev.get("quote") or ""),)
        dedupe_key = (cand["record_kind"], json.dumps(cand["fields"], sort_keys=True, ensure_ascii=False)) + anchor
        if dedupe_key in seen:
            first = seen[dedupe_key]
            if cand.get("ref") and first.get("ref") and cand["ref"] != first["ref"]:
                ref_alias[cand["ref"]] = first["ref"]  # links to the duplicate resolve to the kept candidate
            reject("candidate", i, {"code": "CANDIDATE_DUPLICATE", "message": "与前面的候选完全相同，已去重"}, cand=cand)
            continue
        seen[dedupe_key] = cand
        pre += asm.value_warnings(cand, ev["page"])
        verified.append((i, cand, ev, span, pre))

    # Ordinals separate records that share kind + anchor + quote. They follow the canonical field content,
    # not the input order, so re-running with reordered candidates keeps every record_id.
    groups: dict[tuple, list] = {}
    for item in verified:
        i, cand, ev = item[:3]
        key = (cand["record_kind"],) + tuple(str(ev.get(r)) for r in ID_ANCHOR_ROLES) + \
            (normalize_text(ev.get("quote") or ""),)
        groups.setdefault(key, []).append(item)
    for items in groups.values():
        items.sort(key=lambda it: json.dumps(it[1]["fields"], sort_keys=True, ensure_ascii=False))
        for n, (i, *_rest) in enumerate(items):
            ordinals[i] = n

    # pass 2: build records
    built: dict[int, tuple[dict, RecordContext]] = {}
    for i, cand, ev, span, pre in verified:
        built[i] = asm.build(cand["record_kind"], candidate=cand, evidence=ev, span=span, ordinal=ordinals[i],
                             pre_issues=pre)

    # pass 3: resolve candidate references (profile record_links) to record IDs and rebuild the linking records
    record_links = profile.get("record_links") or {}
    targets: dict[str, tuple[str, str]] = {}
    for i, cand, *_ in verified:
        rec, ctx = built[i]
        ref = cand.get("ref")
        if not ref or any(x.severity == "error" for x in ctx.issues):
            continue
        if ref in targets:
            ctx.issues.append(Issue("CANDIDATE_REF_DUPLICATE", "warning", "ref", f"ref {ref!r} 已被前面的候选使用"))
            continue
        targets[ref] = (_record_id(rec, profile), cand["record_kind"])
    for i, cand, ev, span, pre in verified:
        if not cand.get("links"):
            continue
        resolved: dict[str, list[str]] = {}
        link_issues: list[Issue] = []
        for name, refs in cand["links"].items():
            spec = record_links[name]
            ids = []
            for r in refs:
                target = targets.get(ref_alias.get(r, r))
                if r == cand.get("ref"):
                    link_issues.append(Issue("CANDIDATE_LINK_SELF", "warning", spec["field"], f"{name} 引用了候选自身"))
                elif target is None:
                    link_issues.append(Issue("CANDIDATE_LINK_UNRESOLVED", "warning", spec["field"],
                                             f"{name} 引用的候选 {r!r} 不存在或未被接受", detail={"link": name, "ref": r}))
                elif spec.get("target_kinds") and target[1] not in spec["target_kinds"]:
                    link_issues.append(Issue("CANDIDATE_LINK_KIND", "warning", spec["field"],
                                             f"{name} 只能引用 {', '.join(spec['target_kinds'])}，{r!r} 是 {target[1]}",
                                             detail={"link": name, "ref": r}))
                elif target[0] not in ids:
                    ids.append(target[0])
            if ids:
                resolved[spec["field"]] = ids
        built[i] = asm.build(cand["record_kind"], candidate=cand, evidence=ev, span=span, ordinal=ordinals[i],
                             pre_issues=pre + link_issues, links=resolved)
    for i, cand, *_ in verified:
        rec, ctx = built[i]
        errs = [x for x in ctx.issues if x.severity == "error"]
        if errs:
            reject("validation", i, {"code": "RECORD_INVALID", "message": "组装后的记录未通过契约校验"},
                   cand=cand, record=rec, issues=errs)
        else:
            accepted.append((rec, ctx, i))

    # dataset-level rules over the accepted set; warnings feed back into the review fields
    dataset_issues = asm.validator.validate_dataset([r for r, _, _ in accepted])
    bad: dict[int, list[Issue]] = {}
    extra: dict[int, list[Issue]] = {}
    for idx, issue in dataset_issues:
        (bad if issue.severity == "error" else extra).setdefault(idx, []).append(issue)
    for idx, issues in extra.items():
        if idx in bad:
            continue
        rec, ctx, ci = accepted[idx]
        asm.review(ctx, ctx.pre + issues)
        accepted[idx] = (ctx.record, ctx, ci)
    for idx in sorted(bad, reverse=True):
        rec, ctx, ci = accepted.pop(idx)
        reject("dataset", ci, {"code": "DATASET_RULE", "message": "违反数据集级规则"}, record=rec, issues=bad[idx])
    rejected.sort(key=lambda e: (e.get("candidate_index", -1), e["stage"]))

    records = [r for r, _, _ in accepted]
    review_path = next((p for p, s in (profile.get("system_fields") or {}).items()
                        if s["rule"] == "validation_outcome"), None)
    counts = {
        "pages": doc.page_count,
        "candidates": len(candidates),
        "records": len(records),
        "rejected": len(rejected),
        "by_record_kind": {},
        "by_review_status": {},
        "rejected_by_code": {},
    }
    kind_counts: dict = {}
    for _, ctx, _ in accepted:
        kind_counts[ctx.record_kind] = kind_counts.get(ctx.record_kind, 0) + 1
    counts["by_record_kind"] = dict(sorted(kind_counts.items()))
    if review_path:
        rs: dict = {}
        for r in records:
            v = get_path(r, review_path, None)
            rs[str(v)] = rs.get(str(v), 0) + 1
        counts["by_review_status"] = dict(sorted(rs.items()))
    for e in rejected:
        counts["rejected_by_code"][e["code"]] = counts["rejected_by_code"].get(e["code"], 0) + 1
    counts["rejected_by_code"] = dict(sorted(counts["rejected_by_code"].items()))

    # ------------------------------------------------------------------ outputs
    out_dir = Path(opts.out_dir) if opts.out_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = output_stem(input_path)
    paths = {k: out_dir / f"{stem}{suffix}" for k, suffix in
             (("records", ".jsonl"), ("errors", ".errors.jsonl"), ("validation", ".validation.json"),
              ("manifest", ".manifest.json"))}
    paths["records"].write_text(dumps_jsonl(records), encoding="utf-8")
    paths["errors"].write_text(dumps_jsonl(rejected), encoding="utf-8")
    identity = rc.identity()
    report = {
        "report_format": 1,
        "run_id": run_id,
        "contract": identity,
        "profile": profile["name"],
        "input": {"file_name": input_path.name, "sha256": doc.sha256},
        "valid": True,
        "counts": counts,
        "document": {"values": run_ctx.document, "issues": [i.to_dict() for i in asm.document_issues]},
        "records": [{"line": n + 1, "record_id": _record_id(r, profile), "record_kind": ctx.record_kind,
                     "candidate_index": ci,
                     "warnings": [x.to_dict() for x in ctx.issues if x.severity == "warning"],
                     **({"notes": ctx.notes} if ctx.notes else {})}
                    for n, (r, ctx, ci) in enumerate(accepted)],
        "rejected": [{k: e[k] for k in ("stage", "code", "message", "candidate_index") if k in e} for e in rejected],
        "repairs": repairs,
        "system_records_skipped": skipped_system,
        "argument_structure": argument_audit(records, rc.contract),
    }
    paths["validation"].write_text(dumps_json(report), encoding="utf-8")

    bundle_path = None
    if opts.bundle:
        from breeding_contract.bundle import bundle_records
        bundle_path = out_dir / f"{stem}.bundle.json"
        bundle_path.write_text(dumps_json(bundle_records(records, rc)), encoding="utf-8")
        paths["bundle"] = bundle_path

    manifest = {
        "manifest_format": 1,
        "run_id": run_id,
        "created_at": _iso(started),
        "contract": identity,
        "profile": {"name": profile["name"], "extends_chain": profile["extends_chain"],
                    "fill_rules": profile["fill_rules"], "field_count": profile["counts"]["total"]},
        "input": {"file_name": input_path.name, "sha256": doc.sha256, "size_bytes": doc.size_bytes,
                  "media_type": doc.media_type, "page_count": doc.page_count, "parser": doc.parser},
        "pipeline": {"name": "pdf2jsonl", "version": PIPELINE_VERSION, "contract_tooling": GENERATOR_VERSION},
        "backend": backend.info(),
        "options": opts.cli_values(),
        "environment": _environment(),
        "counts": {k: counts[k] for k in ("pages", "candidates", "records", "rejected")},
        "outputs": {k: {"file": p.name, "sha256": sha256_file(p)} for k, p in paths.items() if k != "manifest"},
    }
    if opts.candidates_file:
        manifest["input"]["candidates_sha256"] = sha256_file(Path(opts.candidates_file))
    paths["manifest"].write_text(dumps_json(manifest), encoding="utf-8")
    return RunResult(outputs=paths, counts=counts, manifest=manifest, records=records)


def _record_id(record: dict, profile: dict):
    path = next((p for p, s in (profile.get("system_fields") or {}).items() if s["rule"] == "stable_record_id"), None)
    return get_path(record, path, None) if path else None


# ---------------------------------------------------------------------------------------------- agent mode
def pages_text(doc: ParsedDocument) -> str:
    return "".join(f"=== page {p.number} ===\n{p.text.rstrip()}\n\n" for p in doc.pages)


def prepare(input_path: Path | str, opts: RunOptions, work_dir: Path | str | None = None) -> Path:
    """Write the agent work directory: brief.md, pages.txt, candidate.schema.json, request.json."""
    input_path = Path(input_path)
    rc, profile = resolve_contract(opts.schema_version, opts.profile, opts.allow_unreleased)
    try:
        doc = parse_document(input_path, opts.text_layer)
    except (ValueError, RuntimeError, OSError) as e:
        raise PipelineError(str(e)) from e
    work = Path(work_dir) if work_dir else default_work_dir(input_path, opts)
    work.mkdir(parents=True, exist_ok=True)
    (work / "pages.txt").write_text(pages_text(doc), encoding="utf-8")
    (work / "candidate.schema.json").write_text(dumps_json(rc.candidate_schema(profile["name"])), encoding="utf-8")
    (work / "brief.md").write_text(render_brief(rc, profile, "pages.txt", "candidates.json", "candidate.schema.json"),
                                   encoding="utf-8")
    (work / "candidates.template.json").write_text(dumps_json(candidates_skeleton(profile)), encoding="utf-8")
    request = {
        "request_format": 1,
        "created_at": _iso(utc_now()),
        "input": {"path": str(input_path.resolve()), "sha256": doc.sha256,
                  **({"text_layer": str(Path(opts.text_layer).resolve())} if opts.text_layer else {})},
        "contract": rc.identity(),
        "profile": profile["name"],
        "options": {**opts.cli_values(), **({"out_dir": str(Path(opts.out_dir).resolve())} if opts.out_dir else {})},
        "pipeline": {"name": "pdf2jsonl", "version": PIPELINE_VERSION},
    }
    (work / "request.json").write_text(dumps_json(request), encoding="utf-8")
    return work


def default_work_dir(input_path: Path, opts: RunOptions) -> Path:
    out_dir = Path(opts.out_dir) if opts.out_dir else input_path.parent
    return out_dir / f"{output_stem(input_path)}.work"


def finalize(work_dir: Path | str, overrides: RunOptions | None = None, requested_version: str | None = None) -> RunResult:
    """Validate the agent's candidates.json and write outputs under the version pinned at prepare time."""
    work = Path(work_dir)
    req_file, cand_file = work / "request.json", work / "candidates.json"
    if not req_file.is_file():
        raise PipelineError(f"{work}: no request.json (run `pdf2jsonl prepare` first)")
    if not cand_file.is_file():
        raise PipelineError(f"{work}: candidates.json not written yet")
    req = json.loads(req_file.read_text(encoding="utf-8"))
    pinned = req["contract"]
    input_path = Path(req["input"]["path"])
    if not input_path.is_file() or sha256_file(input_path) != req["input"]["sha256"]:
        raise PipelineError(f"input {input_path} is missing or changed since prepare")
    released = pinned["release_status"] == "released"
    version = pinned["schema_version"] if released else "dev"
    # The version is pinned at prepare time: a release (or a working-tree edit) in between must not silently
    # change the contract the candidates were written against.
    for label, v in (("pinned version", version), ("requested version", requested_version)):
        if v is None:
            continue
        rc_now, _ = resolve_contract(v, req["profile"], allow_unreleased=not released)
        if rc_now.version != pinned["schema_version"]:
            raise PipelineError(f"work dir was prepared for {pinned['schema_version']} but the {label} "
                                f"({v}) now resolves to {rc_now.version}; run prepare again")
    o = overrides or RunOptions()
    opts = RunOptions(profile=req["profile"], schema_version=version, backend="candidates",
                      candidates_file=str(cand_file), out_dir=o.out_dir or req["options"].get("out_dir"),
                      text_layer=req["input"].get("text_layer"),
                      dataset_id=o.dataset_id or req["options"].get("dataset_id"),
                      dataset_version=o.dataset_version or req["options"].get("dataset_version"),
                      source_asset_id=o.source_asset_id or req["options"].get("source_asset_id"),
                      asset_uri=o.asset_uri or req["options"].get("asset_uri"),
                      run_id=o.run_id, allow_unreleased=not released, bundle=o.bundle)
    return run(input_path, opts)
