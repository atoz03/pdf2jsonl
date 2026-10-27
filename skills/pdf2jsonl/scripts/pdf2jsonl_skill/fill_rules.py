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
from .pdf_parse import MAIN_PART

ensure_contract_importable()
from breeding_contract.ids import build_locator, build_span, stable_record_id  # noqa: E402
from breeding_contract.normalize import normalize_value  # noqa: E402
from breeding_contract.relations import (end_types, entity_markers, find_span, predicate_match,  # noqa: E402
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
    part: str = MAIN_PART                          # which file of the source the record comes from (AMB-041)

    @property
    def part_doc(self):
        return self.run.doc.part_doc(self.part) or self.run.doc

    @property
    def part_label(self) -> str | None:
        """The part as written into locators, spans and ID anchors: nothing for the main text."""
        return None if self.part == MAIN_PART else self.part

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


MAIN_FILE_OPTIONS = frozenset({"asset_uri", "source_asset_id"})  # operator values that describe the main file


@rule("cli_option")
def _cli_option(ctx: RecordContext, params: dict):
    if ctx.part != MAIN_PART and params["option"] in MAIN_FILE_OPTIONS:
        return MISSING  # never attach the main file's URI or asset ID to a supplement
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
    return ctx.part_doc.sha256


@rule("input_file_size")
def _file_size(ctx: RecordContext, params: dict):
    return ctx.part_doc.size_bytes


@rule("evidence_source_part")
def _source_part(ctx: RecordContext, params: dict):
    """The part of the source a record comes from, as a vocabulary code. ``params`` maps the pipeline's part
    kinds (main, supplement) to the codes of the contract, so the codes stay in the profile."""
    return params.get(ctx.part_doc.part_kind) or MISSING


# ------------------------------------------------------------------ evidence anchors
def _anchor(ctx: RecordContext) -> str:
    e = ctx.evidence
    return build_locator(page=e.get("page"), section=e.get("section"), table=e.get("table_figure"),
                         row=e.get("row_key"), col=e.get("column_key"), part=ctx.part_label)


@rule("evidence_locator", order=20)
def _locator(ctx: RecordContext, params: dict):
    if not ctx.evidence:  # system records (e.g. the PDF asset itself) are located at document level
        return build_locator(part=ctx.part_label) or "document"
    return _anchor(ctx)


@rule("evidence_span", order=20)
def _span(ctx: RecordContext, params: dict):
    if not ctx.span or not ctx.evidence.get("page"):
        return MISSING
    return build_span(ctx.evidence["page"], *ctx.span, part=ctx.part_label)


@rule("stable_record_id", order=90)
def _record_id(ctx: RecordContext, params: dict):
    """Identity = source + kind + page/table/row/column + normalized quote + ordinal (AMB-011). The section is
    left out: parsers and agents may or may not supply it, and a heading's spelling must not change the ID."""
    source_id = ctx.value(ctx.run.role("provenance", "document_id"))
    e = ctx.evidence
    anchor = build_locator(page=e.get("page"), table=e.get("table_figure"), row=e.get("row_key"),
                           col=e.get("column_key"), part=ctx.part_label) if e else \
        (build_locator(part=ctx.part_label) or "document")
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
    verbatim predicate, the predicate code when the vocabulary's cue phrases identify exactly one and neither
    the predicate nor the quote between the two ends negates the relation, and why no code was assigned
    otherwise (``transform.relation_resolution``, AMB-043).

    params = {"inputs": {quote, subject, predicate, object}, "outputs": {markers, predicate_start,
    predicate_end, predicate_code, resolution}} -> {path: value}. Literal search only: what is not found is
    left out."""
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
        code, reason = predicate_match(vocabulary, predicate, end_types(markers, "subject"),
                                       end_types(markers, "object"), context) if vocabulary else (None, "no_cue")
        if code and code_path:
            out[code_path] = code
        if outputs.get("resolution") and (code or reason):
            out[outputs["resolution"]] = "coded" if code else reason
        if not code:
            ctx.notes.setdefault("relation", {})["predicate_code"] = reason or "no_predicate"
    return out


@rule("relation_nature_from_predicate", kind="normalizer")
def _relation_nature_from_predicate(ctx: RecordContext, params: dict) -> dict:
    """Derive the semantic nature (causal / associational / …) of a relation from the contract, not from the
    extraction model: the `predicate_label` vocabulary carries `nature` per code and the compiled contract exposes
    it as `contract["relation_natures"]` (AMB-042). The reviewed `predicate_label` wins; when the record has none
    — a fresh extraction never does, because that field is human judgement — the code the pipeline matched
    (`predicate_code`) names the same judgement deterministically, so the nature reaches the record instead of
    only the derived views (AMB-043). Literal lookup only: a missing or unknown code yields nothing, so the field
    stays absent rather than guessing "unknown".

    params = {"inputs": {predicate, code}, "outputs": {nature}} -> {path: value}."""
    inputs, outputs = params["inputs"], params["outputs"]
    out_path = outputs.get("nature")
    if not out_path:
        return {}
    natures = ctx.run.rc.contract.get("relation_natures") or {}
    for name in ("predicate", "code"):
        path = inputs.get(name)
        code = ctx.value(path) if path else MISSING
        if isinstance(code, str) and code.strip() and natures.get(code):
            return {out_path: natures[code]}
    return {}


@rule("claim_strength_from_evidence", kind="normalizer")
def _claim_strength(ctx: RecordContext, params: dict) -> dict:
    """Combine what the predicate asserts (nature) with how strong its evidence is (relation_evidence_type,
    human judgement) into one reading (AMB-046).

    A causal wording is never settled by the verb alone: with intervention-level evidence it is
    ``causal_supported``, with expression support ``causal_expression_supported``, with statistical mapping only
    ``causal_statistical_only`` (R038 then asks for a validation method), and with no evidence type at all
    ``causal_unverified`` — the record keeps the paper's causal wording, but the data does not call it proven.
    Associational / structural / descriptive pass through unchanged.

    params = {"inputs": {nature, evidence_type}, "outputs": {strength}} -> {path: value}."""
    inputs, outputs = params["inputs"], params["outputs"]
    out_path = outputs.get("strength")
    nature = ctx.value(inputs.get("nature"))
    if not out_path or not isinstance(nature, str):
        return {}
    if nature in ("associational", "structural", "descriptive"):
        return {out_path: nature}
    if nature != "causal":
        return {}
    evidence = ctx.value(inputs.get("evidence_type"))
    if evidence in ("functional_validation", "genetic_interaction", "biochemical_assay",
                    "localization_imaging", "pharmacological_perturbation"):
        return {out_path: "causal_supported"}
    if evidence == "expression_support":
        return {out_path: "causal_expression_supported"}
    if evidence == "statistical_mapping":
        return {out_path: "causal_statistical_only"}
    return {out_path: "causal_unverified"}


@rule("validation_status_from_links", kind="normalizer")
def _validation_status(ctx: RecordContext, params: dict) -> dict:
    """Candidate or "the paper reports an experiment validating it" (AMB-045).

    Read from the ``validated_by`` link alone — never from the wording of the finding — and only for a record that
    states a conclusion (claim / analysis_result) or a relation. A linked method, observation or analysis result
    means the paper supplies a validation experiment; otherwise the conclusion stays a candidate. The status does
    not judge the experiment and does not replace the association record: both keep their own evidence.

    params = {"inputs": {links, predicate}, "outputs": {status}} -> {path: value}."""
    inputs, outputs = params["inputs"], params["outputs"]
    out_path = outputs.get("status")
    if not out_path:
        return {}
    predicate = ctx.value(inputs.get("predicate"))
    if not (isinstance(predicate, str) and predicate.strip()) and \
            ctx.record_kind not in ("claim", "analysis_result"):
        return {}
    links = ctx.value(inputs.get("links"))
    linked = [x for x in links if isinstance(x, str) and x] if isinstance(links, list) else []
    return {out_path: "experiment_reported" if linked else "candidate"}


@rule("evidence_origin_from_document_type", kind="normalizer")
def _evidence_origin(ctx: RecordContext, params: dict) -> dict:
    """A review reports someone else's experiment: mark its records ``review_report`` (AMB-047).

    Only the review case is written: ``common.source_document_type`` already travels with every record, so
    ``primary_study`` would repeat a constant. The value exists for importers and reviewers.

    params = {"inputs": {document_type}, "outputs": {origin}} -> {path: value}."""
    inputs, outputs = params["inputs"], params["outputs"]
    out_path = outputs.get("origin")
    document_type = ctx.value(inputs.get("document_type"))
    if not out_path or document_type != "review":
        return {}
    return {out_path: "review_report"}


@rule("cited_items_from_quote", kind="normalizer")
def _cited_items(ctx: RecordContext, params: dict) -> dict:
    """The supplementary figures/tables a record's own quote cites (AMB-044).

    It is what ties a record to the part of the paper outside the main text: the pipeline detects the item labels
    with the same literal rules it uses for source completeness, so a record and the run's ``source_parts`` agree.
    Empty when the quote cites none.

    params = {"inputs": {quote}, "outputs": {items}} -> {path: value}."""
    from .completeness import cited_items

    inputs, outputs = params["inputs"], params["outputs"]
    out_path = outputs.get("items")
    quote = ctx.value(inputs.get("quote"))
    if not out_path or not isinstance(quote, str):
        return {}
    items = cited_items(quote)
    return {out_path: items} if items else {}


# ------------------------------------------------------------------ system records
@rule("input_asset_manifest", kind="record")
def _asset_manifest(ctx: RecordContext, params: dict):
    """Emit one record describing the input file itself — only when the input really is a PDF (a bare text
    layer is not the raw_pdf asset, so describing it as one would be a fabricated fact)."""
    if ctx.part_doc.media_type != "application/pdf":
        ctx.notes["skipped"] = "input is not a PDF file"
        return False
    return True


# ------------------------------------------------------------------ phase 2 (after validation)
SOURCE_PART_UNAVAILABLE = "SOURCE_PART_UNAVAILABLE"  # the record cites a part of the source that was not supplied
SOURCE_PART_NOT_PARSED = "SOURCE_PART_NOT_PARSED"    # … or a supplied part with no text layer to read it in
PART_WARNING_CODES = (SOURCE_PART_UNAVAILABLE, SOURCE_PART_NOT_PARSED)


def _warnings(ctx: RecordContext) -> list:
    return [i for i in ctx.issues if i.severity == "warning"]


def _blocking_warnings(ctx: RecordContext) -> list:
    """Warnings that put the record in the review queue. A non-blocking warning (rules with ``blocking: false``:
    operator-supplied metadata, inferred review hints) is still reported and counted, but a record whose only
    warnings are of that kind stays auto_validated (AMB-043)."""
    return [i for i in ctx.issues if i.severity == "warning" and getattr(i, "blocking", True)]


@rule("validation_outcome", phase=2)
def _review_status(ctx: RecordContext, params: dict):
    return params["needs_review"] if _blocking_warnings(ctx) else params["clean"]


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
    part_missing = any(i.code in PART_WARNING_CODES for i in _warnings(ctx))
    availability = {f["path"]: f["availability"] for f in ctx.run.rc.contract["fields"]}
    for i in _warnings(ctx):
        if not (i.code.startswith("RULE_") and i.path) or get_path(ctx.record, i.path) is not MISSING:
            continue
        # Operator-supplied values come from outside the paper; a field of human judgement (I) is not something
        # the extractor could have located; a normalized value (N) or a future source (F) is generated elsewhere.
        # A record that cites a part of the source that was not supplied (a supplementary figure, say) may have
        # its missing values there. For everything else the pipeline cannot tell "not reported by the paper" from
        # "not found by the extractor", so it says not_located.
        level = availability.get(i.path)
        if i.path in external:
            reason = "requires_external_source"
        elif level == "I":
            reason = "requires_review"
        elif level in ("N", "F"):
            reason = "requires_external_source"
        elif part_missing:
            reason = "source_part_unavailable"
        else:
            reason = "not_located"
        if reason in allowed:
            out.setdefault(i.path, reason)
    grain_reason = (ctx.notes.get("missing") or {}).get("grain")
    grain_path = next((p for p, spec in (ctx.run.profile.get("system_fields") or {}).items()
                       if spec["rule"] == "grain_from_record_kind"), None)
    if grain_reason and grain_path and grain_reason in allowed:
        out[grain_path] = grain_reason
    return out or MISSING


IMPLEMENTED_RULES = frozenset(REGISTRY)
