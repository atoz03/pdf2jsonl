"""Named fill rules referenced by extraction profiles (system_fields, normalizers, generated_fields, system_records).

A profile says *which* field is produced by *which* rule; this module says *how*. Rules never read field
paths from code: they receive the resolved profile (roles) and the record under construction.
`bdc check` fails if a released profile names a rule that is not registered here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import PIPELINE_VERSION
from .contract_link import ensure_contract_importable

ensure_contract_importable()
from breeding_contract.ids import build_locator, build_span, stable_record_id  # noqa: E402
from breeding_contract.normalize import normalize_value  # noqa: E402
from breeding_contract.relations import (end_types, entity_markers, find_span, negated, predicate_code,  # noqa: E402
                                          relation_context)
from breeding_contract.util import MISSING, get_path  # noqa: E402

REGISTRY: dict[str, "RuleSpec"] = {}


@dataclass
class RuleSpec:
    name: str
    fn: Callable
    phase: int = 1        # 1 = while building, 2 = after validation
    order: int = 50       # evaluation order inside phase 1 (ids last)
    kind: str = "field"   # field | normalizer | record


def rule(name: str, phase: int = 1, order: int = 50, kind: str = "field"):
    def deco(fn):
        REGISTRY[name] = RuleSpec(name, fn, phase, order, kind)
        return fn
    return deco


@dataclass
class RunContext:
    rc: Any                      # breeding_contract.ResolvedContract
    profile: dict
    doc: Any                     # ParsedDocument
    backend: dict                # {"name", "extraction_method", "model"}
    run_id: str
    options: dict
    document: dict = field(default_factory=dict)   # resolved document-level field values {path: value}

    def role(self, family: str, name: str) -> str | None:
        return ((self.profile.get("roles") or {}).get(family) or {}).get(name)

    @property
    def units(self) -> dict:
        return self.rc.contract["vocabularies"]["units"]


@dataclass
class RecordContext:
    run: RunContext
    record_kind: str
    record: dict
    candidate: dict | None = None
    evidence: dict = field(default_factory=dict)   # page, section, quote, table_figure, row_key, column_key
    span: tuple[int, int] | None = None
    ordinal: int = 0
    issues: list = field(default_factory=list)     # Issue objects (validator + pipeline warnings)
    notes: dict = field(default_factory=dict)
    pre: list = field(default_factory=list)        # pipeline issues that are not re-derived by validation

    def value(self, path: str | None) -> Any:
        if not path:
            return MISSING
        v = get_path(self.record, path)
        return self.run.document.get(path, MISSING) if v is MISSING else v


# ------------------------------------------------------------------ identity & versioning
@rule("resolved_schema_version")
def _schema_version(ctx: RecordContext, params: dict):
    return ctx.run.rc.version


@rule("resolved_schema_name")
def _schema_name(ctx: RecordContext, params: dict):
    return ctx.run.rc.name


@rule("profile_name")
def _profile_name(ctx: RecordContext, params: dict):
    return ctx.run.profile["name"]


@rule("candidate_record_kind")
def _record_kind(ctx: RecordContext, params: dict):
    return ctx.record_kind


@rule("grain_from_record_kind")
def _grain(ctx: RecordContext, params: dict):
    grain = (ctx.run.rc.contract.get("record_kinds") or {}).get(ctx.record_kind, {}).get("grain")
    if not grain:
        ctx.notes.setdefault("missing", {})["grain"] = "ambiguous_in_contract"
        return MISSING
    return grain


@rule("constant")
def _constant(ctx: RecordContext, params: dict):
    return params["value"]


@rule("cli_option")
def _cli_option(ctx: RecordContext, params: dict):
    v = ctx.run.options.get(params["option"])
    return MISSING if v in (None, "") else v


@rule("run_id")
def _run_id(ctx: RecordContext, params: dict):
    return ctx.run.run_id


@rule("backend_extraction_method")
def _extraction_method(ctx: RecordContext, params: dict):
    return ctx.run.backend.get("extraction_method") or MISSING


@rule("qc_rule_set_version")
def _qc_version(ctx: RecordContext, params: dict):
    return f"{ctx.run.rc.name}@{ctx.run.rc.version}+pdf2jsonl@{PIPELINE_VERSION}"


# ------------------------------------------------------------------ source identity
def _doi(ctx: RecordContext) -> str | None:
    v = ctx.value(ctx.run.role("semantic", "doi"))
    return v.strip() if isinstance(v, str) and v.strip() else None


@rule("document_source_id", order=10)
def _source_id(ctx: RecordContext, params: dict):
    doi = _doi(ctx)
    if doi:
        return "doi:" + doi.lower()
    return "urn:sha256:" + ctx.run.doc.sha256


@rule("doi_uri")
def _doi_uri(ctx: RecordContext, params: dict):
    doi = _doi(ctx)
    return "https://doi.org/" + doi if doi else MISSING


@rule("input_file_sha256")
def _file_sha(ctx: RecordContext, params: dict):
    return ctx.run.doc.sha256


@rule("input_file_size")
def _file_size(ctx: RecordContext, params: dict):
    return ctx.run.doc.size_bytes


# ------------------------------------------------------------------ evidence anchors
def _anchor(ctx: RecordContext) -> str:
    e = ctx.evidence
    return build_locator(page=e.get("page"), section=e.get("section"), table=e.get("table_figure"),
                         row=e.get("row_key"), col=e.get("column_key"))


@rule("evidence_locator", order=20)
def _locator(ctx: RecordContext, params: dict):
    if not ctx.evidence:
        return "document"  # system records (e.g. the PDF asset itself) are located at document level
    return _anchor(ctx)


@rule("evidence_span", order=20)
def _span(ctx: RecordContext, params: dict):
    if not ctx.span or not ctx.evidence.get("page"):
        return MISSING
    return build_span(ctx.evidence["page"], *ctx.span)


@rule("stable_record_id", order=90)
def _record_id(ctx: RecordContext, params: dict):
    """Identity = source + kind + page/table/row/column + normalized quote + ordinal (AMB-011). The section is
    left out: parsers and agents may or may not supply it, and a heading's spelling must not change the ID."""
    source_id = ctx.value(ctx.run.role("provenance", "document_id"))
    e = ctx.evidence
    anchor = build_locator(page=e.get("page"), table=e.get("table_figure"), row=e.get("row_key"),
                           col=e.get("column_key")) if e else "document"
    return stable_record_id(str(source_id), ctx.record_kind, anchor, ctx.evidence.get("quote"), ctx.ordinal)


# ------------------------------------------------------------------ generated (only when actually provided)
@rule("backend_confidence")
def _confidence(ctx: RecordContext, params: dict):
    c = (ctx.candidate or {}).get("confidence")
    if isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 1:
        return c
    return MISSING


# ------------------------------------------------------------------ normalizers
@rule("unit_normalization", kind="normalizer")
def _unit_normalization(ctx: RecordContext, params: dict) -> dict:
    """params = {"inputs": {raw_value, raw_unit}, "outputs": {value, min, max, unit}} -> {path: value}"""
    raw_value = ctx.value(params["inputs"].get("raw_value"))
    raw_unit = ctx.value(params["inputs"].get("raw_unit"))
    if raw_value is MISSING:
        return {}
    unit = None if raw_unit is MISSING else raw_unit
    out, reason = normalize_value(raw_value, unit, ctx.run.units)
    if reason:
        ctx.notes.setdefault("normalization", []).append({"raw_value": raw_value, "raw_unit": unit,
                                                          "skipped": reason})
        return {}
    ctx.notes.setdefault("normalization", []).append({"raw_value": raw_value, "raw_unit": unit, "result": out})
    return {params["outputs"][k]: v for k, v in out.items() if k in params["outputs"]}


@rule("relation_anchors", kind="normalizer")
def _relation_anchors(ctx: RecordContext, params: dict) -> dict:
    """Downstream hooks (AMB-038): one marker per entity mention with its offsets in the quote, the anchor of the
    verbatim predicate, and the predicate code when the vocabulary's cue phrases identify exactly one and neither
    the predicate nor the quote between the two ends negates the relation.

    params = {"inputs": {quote, subject, predicate, object}, "outputs": {markers, predicate_start,
    predicate_end, predicate_code}} -> {path: value}. Literal search only: what is not found is left out."""
    inputs, outputs = params["inputs"], params["outputs"]

    def text(name: str):
        v = ctx.value(inputs.get(name))
        return v if isinstance(v, str) and v.strip() else None
    quote, predicate = text("quote"), text("predicate")
    ends = {role: (inputs[role], text(role)) for role in ("subject", "object") if inputs.get(role) and text(role)}
    out: dict = {}
    markers = entity_markers(ctx.record, ctx.run.rc.contract, quote, ends)
    if markers and outputs.get("markers"):
        out[outputs["markers"]] = markers
    if predicate:
        span = find_span(quote, predicate)
        if span and outputs.get("predicate_start") and outputs.get("predicate_end"):
            out[outputs["predicate_start"]], out[outputs["predicate_end"]] = span
        code_path = outputs.get("predicate_code")
        field = next((f for f in ctx.run.profile["fields"] if f["path"] == code_path), None)
        vocabulary = ctx.run.rc.contract["vocabularies"].get((field or {}).get("vocabulary") or "")
        context = relation_context(quote, markers)
        code = predicate_code(vocabulary, predicate, end_types(markers, "subject"),
                              end_types(markers, "object"), context) if vocabulary else None
        if code:
            out[code_path] = code
        elif code_path:
            ctx.notes.setdefault("relation", {})["predicate_code"] = (
                "negated" if negated(predicate, context) else "no_unique_cue_match")
    return out


# ------------------------------------------------------------------ system records
@rule("input_asset_manifest", kind="record")
def _asset_manifest(ctx: RecordContext, params: dict):
    """Emit one record describing the input file itself — only when the input really is a PDF (a bare text
    layer is not the raw_pdf asset, so describing it as one would be a fabricated fact)."""
    if ctx.run.doc.media_type != "application/pdf":
        ctx.notes["skipped"] = "input is not a PDF file"
        return False
    return True


# ------------------------------------------------------------------ phase 2 (after validation)
def _warnings(ctx: RecordContext) -> list:
    return [i for i in ctx.issues if i.severity == "warning"]


@rule("validation_outcome", phase=2)
def _review_status(ctx: RecordContext, params: dict):
    return params["needs_review"] if _warnings(ctx) else params["clean"]


@rule("warning_codes", phase=2)
def _warning_codes(ctx: RecordContext, params: dict):
    codes = sorted({i.code for i in _warnings(ctx)})
    return codes or MISSING


@rule("missing_audit", phase=2)
def _missing_audit(ctx: RecordContext, params: dict):
    vocab = ctx.run.rc.contract["vocabularies"].get("missing_reason", {})
    allowed = {v["code"] for v in vocab.get("values", [])}
    out = {}
    external = {path for path, spec in (ctx.run.profile.get("system_fields") or {}).items()
                if spec["rule"] == "cli_option"}
    for sr in ctx.run.profile.get("system_records") or []:
        external |= {path for path, spec in sr["fields"].items() if spec["rule"] == "cli_option"}
    for i in _warnings(ctx):
        if not (i.code.startswith("RULE_") and i.path) or get_path(ctx.record, i.path) is not MISSING:
            continue
        # Operator-supplied values come from outside the paper. For everything else the pipeline cannot tell
        # "not reported by the paper" from "not found by the extractor", so it says not_located.
        reason = "requires_external_source" if i.path in external else "not_located"
        if reason in allowed:
            out.setdefault(i.path, reason)
    grain_reason = (ctx.notes.get("missing") or {}).get("grain")
    grain_path = next((p for p, spec in (ctx.run.profile.get("system_fields") or {}).items()
                       if spec["rule"] == "grain_from_record_kind"), None)
    if grain_reason and grain_path and grain_reason in allowed:
        out[grain_path] = grain_reason
    return out or MISSING


IMPLEMENTED_RULES = frozenset(REGISTRY)
