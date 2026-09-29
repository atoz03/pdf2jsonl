"""Derived per-document views over atomic records (never a source of truth).

* ``document_bundle`` — one object per source document: document-level values, records grouped by kind,
  entity name index, evidence index (page/section/quote -> record IDs). Schema: schemas/runtime/document_bundle.schema.json
* ``legacy_v1`` projection — the legacy v1 document layout rebuilt from records, validated against
  sources/legacy_v1/breeding_jsonl_schema.json. It is lossy by design: items whose legacy-required values do not
  exist in the records (e.g. relation_type is a human-judgement field) are skipped and reported. Pages in the
  projection are physical PDF pages, not journal pages (AMB-029).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from .api import declared_version, resolve_schema
from .paths import repo_root
from .util import ContractError, dumps_json, get_path, load_json, utc_now

DOCUMENT_FIELDS = (
    "common.source_id", "common.source_type", "common.source_document_type", "common.source_title",
    "common.source_doi", "common.source_pmid", "common.source_year", "common.source_authors",
    "common.source_affiliations", "common.source_journal", "common.source_volume", "common.source_issue",
    "common.source_page_range", "common.source_abstract", "common.source_keywords", "common.source_funding",
    "common.source_language", "common.source_uri", "common.source_file_sha256", "common.source_record_id",
    "common.crop_name", "common.species_name",
)
ENTITY_FIELDS = ("common.gene_names", "common.trait_names", "common.qtl_names", "common.marker_names",
                 "common.germplasm_names", "common.variety_names", "common.parent_names")


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _document_values(recs: list[dict], fields: set[str]) -> dict:
    out = {}
    for p in DOCUMENT_FIELDS:
        if p not in fields:
            continue
        vals = [get_path(r, p, None) for r in recs if get_path(r, p, None) is not None]
        if vals and all(v == vals[0] for v in vals):
            out[p] = vals[0]
    return out


def bundle_records(records: list[dict], rc=None) -> dict:
    versions = {declared_version(r) for r in records}
    if len(versions) > 1:
        raise ContractError(f"records declare several contract versions: {sorted(map(str, versions))}")
    if rc is None:
        v = versions.pop() if versions else None
        if v is None:
            raise ContractError("records do not declare common.schema_version")
        rc = resolve_schema(v)
    fields = {f["path"] for f in rc.fields}
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(str(get_path(r, "common.source_id", "unknown")), []).append(r)
    docs = []
    for source_id, recs in groups.items():
        by_kind: dict[str, list[str]] = {}
        entities: dict[str, list[str]] = {}
        evidence: dict[tuple, list[str]] = {}
        for r in recs:
            rid = get_path(r, "common.record_id", None)
            by_kind.setdefault(str(get_path(r, "common.record_kind", "unknown")), []).append(rid)
            for p in ENTITY_FIELDS:
                for name in get_path(r, p, []) or []:
                    lst = entities.setdefault(p.split(".", 1)[1], [])
                    if name not in lst:
                        lst.append(name)
            page, quote = get_path(r, "common.source_page", None), get_path(r, "common.source_quote", None)
            if page is not None and quote is not None:
                key = (page, get_path(r, "common.source_section", None), get_path(r, "common.source_table_figure", None), quote)
                evidence.setdefault(key, []).append(rid)
        ev = [{k: v for k, v in (("page", k[0]), ("section", k[1]), ("table_figure", k[2]), ("quote", k[3]),
                                  ("record_ids", ids)) if v is not None}
              for k, ids in sorted(evidence.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][3]))]
        docs.append({"source_id": source_id, "document": _document_values(recs, fields),
                     "counts": {"records": len(recs), "by_record_kind": {k: len(v) for k, v in sorted(by_kind.items())}},
                     "records_by_kind": dict(sorted(by_kind.items())), "entities": entities, "evidence_index": ev,
                     "records": recs})
    return {"bundle_format": 1, "view": "document_bundle",
            "contract": {"schema_name": rc.name, "schema_version": rc.version}, "documents": docs}


# ---------------------------------------------------------------------------------------------- legacy v1
LEGACY_METHODS = {"model": "LLM抽取", "rule": "规则", "manual": "人工"}  # inverse of mappings/legacy_to_current.yaml


def _legacy_method(methods: set[str]) -> str | None:
    if not methods:
        return None
    if len(methods) == 1:
        return LEGACY_METHODS.get(next(iter(methods)))
    return "混合(LLM+规则)" if methods == {"model", "rule"} else "混合"


def legacy_projection(doc: dict, created_at: str | None = None) -> tuple[dict, list[str]]:
    """Project one document_bundle document into the legacy v1 layout. -> (legacy_doc, skipped notes)"""
    d, recs = doc["document"], doc["records"]
    skipped: list[str] = []
    g = lambda p: d.get(p)  # noqa: E731
    doc_meta = {"title": g("common.source_title")}
    authors = g("common.source_authors") or []
    if authors:
        doc_meta["authors"] = [{"rank": i + 1, "name": n} for i, n in enumerate(authors)]
    for leaf, p in (("journal", "common.source_journal"), ("year", "common.source_year"), ("volume", "common.source_volume"),
                    ("issue", "common.source_issue"), ("pages", "common.source_page_range"), ("doi", "common.source_doi"),
                    ("abstract", "common.source_abstract"), ("keywords", "common.source_keywords"),
                    ("funding", "common.source_funding")):
        if g(p) is not None:
            doc_meta[leaf] = g(p)
    sections, sec_ids = [], {}
    for ev in doc["evidence_index"]:
        sid = f"sec-p{ev['page']}-{len(sections) + 1}"
        sections.append({"section_id": sid, "page": ev["page"], "text_snippet": ev["quote"]})
        for rid in ev["record_ids"]:
            sec_ids.setdefault(rid, sid)
    if sections:
        doc_meta["document_sections"] = sections
    entities: dict[str, list[dict]] = {}
    ent_ids: dict[tuple[str, str], str] = {}

    prefixes = {"genes": "gene", "traits": "trait", "germplasm": "germplasm", "varieties": "variety", "qtls": "qtl",
                "markers": "marker", "populations": "pop", "environments": "env", "other_entities": "oth"}

    def entity(kind: str, name: str, extra_key: str | None = None) -> str:
        key = (kind, name)
        if key not in ent_ids:
            eid = f"{prefixes[kind]}:{len(entities.get(kind, [])) + 1}"
            item = {"entity_id": eid, "name": name}
            if extra_key:
                item[extra_key] = name
            entities.setdefault(kind, []).append(item)
            ent_ids[key] = eid
        return ent_ids[key]
    for name in doc["entities"].get("gene_names", []):
        entity("genes", name, "gene_symbol")
    for name in doc["entities"].get("trait_names", []):
        entity("traits", name, "trait_name")
    for name in doc["entities"].get("qtl_names", []):
        entity("qtls", name, "qtl_name")
    for name in doc["entities"].get("marker_names", []):
        entity("markers", name, "marker_name")
    for name in doc["entities"].get("germplasm_names", []):
        entity("germplasm", name, "germplasm_name")
    for name in doc["entities"].get("variety_names", []):
        entity("varieties", name, "variety_name")
    relations, conclusions, analyses = [], [], []
    for r in recs:
        rid = get_path(r, "common.record_id", None)
        kind = get_path(r, "common.record_kind", None)
        subj, obj = get_path(r, "transform.subject_mention", None), get_path(r, "transform.object_mention", None)
        if subj and obj:
            pred = get_path(r, "transform.predicate_label", None)
            if pred is None:
                skipped.append(f"{rid}: relation without transform.predicate_label (legacy relation_type is required)")
            else:
                rel = {"relation_id": f"rel:{rid}", "relation_type": pred,
                       "subject": {"entity_id": entity("other_entities", subj), "entity_type": get_path(r, "transform.subject_type", "other")},
                       "object": {"entity_id": entity("other_entities", obj), "entity_type": get_path(r, "transform.object_type", "other")}}
                if rid in sec_ids:
                    rel["evidence_spans"] = [{"section_id": sec_ids[rid]}]
                relations.append(rel)
        text = get_path(r, "agent.finding_text", None)
        if kind == "claim" and text:
            conclusions.append({"conclusion_id": f"clu:{rid}", "claim_text": text})
        if kind == "method" and get_path(r, "skills.software_name", None):
            name = get_path(r, "skills.method_name", None) or get_path(r, "skills.software_name", None)
            atype = get_path(r, "skills.method_category", None)
            if atype is None:
                skipped.append(f"{rid}: method without skills.method_category (legacy analysis_type is required)")
            else:
                tool = {"tool_name": get_path(r, "skills.software_name", None)}
                if get_path(r, "skills.software_version", None):
                    tool["version"] = get_path(r, "skills.software_version", None)
                analyses.append({"analysis_id": f"ana:{rid}", "analysis_name": name, "analysis_type": atype,
                                 "software_tools": [tool]})
    for item in entities.get("other_entities", []):
        item["entity_type"] = "other"
    record_info = {"doc_type": g("common.source_document_type"), "lang": g("common.source_language"),
                   "created_at": created_at or utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")}
    for k in ("doc_type", "lang"):
        if record_info[k] is None:
            skipped.append(f"record_info.{k}: no value in records (legacy requires it)")
            del record_info[k]
    methods = {get_path(r, "common.extraction_method", None) for r in recs} - {None}
    legacy_method = _legacy_method(methods)
    if legacy_method is None:
        skipped.append(f"provenance.extraction.method: {sorted(methods)} has no legacy equivalent (legacy requires it)")
    legacy = {
        "record_id": doc["source_id"], "schema_version": "v1.0.0", "record_info": record_info, "doc_meta": doc_meta,
        "breed_entities": entities, "relations": relations, "experiments": [], "analyses": analyses,
        "conclusions": conclusions, "pipeline": {}, "governance": {},
        "provenance": {"extraction": {"method": legacy_method} if legacy_method else {}},
        "agent": {}, "skill": {},
    }
    return legacy, skipped


def legacy_bundle(bundle: dict, root: Path | str | None = None) -> dict:
    root = repo_root(root)
    schema = load_json(root / "sources/legacy_v1/breeding_jsonl_schema.json")
    v = jsonschema.Draft202012Validator(schema)
    out = []
    for doc in bundle["documents"]:
        legacy, skipped = legacy_projection(doc)
        errors = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}" for e in v.iter_errors(legacy)]
        out.append({"legacy_v1": legacy, "skipped": skipped, "legacy_schema_errors": errors,
                    "valid_against_legacy_schema": not errors})
    return {"bundle_format": 1, "view": "legacy_v1_projection", "contract": bundle["contract"],
            "note_zh": "由原子记录派生的 legacy v1 视图；有损，页码为 PDF 物理页（AMB-029）。", "documents": out}


def bundle_file(path: Path | str, out: Path | str | None = None, legacy_v1: bool = False,
                root: Path | str | None = None) -> Path:
    path = Path(path)
    records = read_records(path)
    versions = {declared_version(r) for r in records} - {None}
    rc = resolve_schema(versions.pop(), root) if len(versions) == 1 else None
    bundle = bundle_records(records, rc)
    if legacy_v1:
        bundle = legacy_bundle(bundle, root)
    stem = path.name[:-6] if path.name.endswith(".jsonl") else path.stem
    out = Path(out) if out else path.with_name(f"{stem}.{'legacy_v1' if legacy_v1 else 'bundle'}.json")
    out.write_text(dumps_json(bundle), encoding="utf-8")
    return out
