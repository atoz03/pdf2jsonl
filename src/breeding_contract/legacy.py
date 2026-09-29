"""Migrate legacy v1 document-level JSONL (sources/legacy_v1) to atomic records of the current contract.

Follows mappings/legacy_to_current.yaml. Invariants:
  * only paper content is migrated; runtime/governance/quality/embedding/translation blocks are not;
  * every record needs a physical page and a verbatim quote (R001) — legacy journal pages need --page-offset;
  * inferred relations and model-generated values are never migrated; values that the contract reserves for
    human judgement (availability I) become *review candidates* in the residue file, not record fields;
  * every non-empty leaf is either consumed or listed in ``residue.json`` — nothing is dropped silently.
Outputs (stem = input stem): <stem>.migrated.jsonl, <stem>.migrated.errors.jsonl, <stem>.residue.json,
<stem>.migration.json (report + manifest).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import GENERATOR_VERSION
from .api import resolve_schema
from .ids import build_locator, stable_record_id
from .mappings import match_entry
from .paths import repo_root
from .util import ContractError, dumps_json, load_yaml, parse_semver, set_path, sha256_file, utc_now

EMPTY = (None, "", [], {})
MIN_VERSION = (3, 1, 0)
ENTITY_NAME_KEYS = ("gene_symbol", "trait_name", "germplasm_name", "variety_name", "population_name", "marker_name",
                    "qtl_name", "name")
ENTITY_TARGET = {"genes": "common.gene_names", "traits": "common.trait_names", "germplasm": "common.germplasm_names",
                 "varieties": "common.variety_names", "markers": "common.marker_names", "qtls": "common.qtl_names"}
PAPER_TYPES = {"journal_paper", "conference_paper", "dissertation", "review", "dataset_paper", "technical_report",
               "book_chapter"}
NOT_VERBATIM = re.compile(r"\.\.\.|…")


class Tracker:
    """Read access to a legacy document that remembers which leaves were consumed."""

    def __init__(self, doc: dict):
        self.doc = doc
        self.used: set[tuple] = set()

    def get(self, *keys, default=None):
        cur: Any = self.doc
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            elif isinstance(cur, list) and isinstance(k, int) and 0 <= k < len(cur):
                cur = cur[k]
            else:
                return default
        if cur in EMPTY:
            return default
        self.used.add(tuple(keys))
        return cur

    def items(self, *keys) -> list[tuple[int, dict]]:
        seq = self.get(*keys, default=[])
        self.used.discard(tuple(keys))  # iterating a list does not consume its members
        return [(i, x) for i, x in enumerate(seq) if isinstance(x, dict)] if isinstance(seq, list) else []

    def consumed(self, path: tuple) -> bool:
        return any(path[:len(u)] == u for u in self.used)


def _leaves(value: Any, path: tuple = ()):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaves(v, path + (k,))
    elif isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
        for i, v in enumerate(value):
            yield from _leaves(v, path + (i,))
    elif value not in EMPTY:
        yield path, value


def _norm(path: tuple) -> str:
    out = ""
    for k in path:
        out += "[]" if isinstance(k, int) else (("." if out else "") + str(k))
    return out


def _concrete(path: tuple) -> str:
    out = ""
    for k in path:
        out += f"[{k}]" if isinstance(k, int) else (("." if out else "") + str(k))
    return out


class LegacyMigrator:
    def __init__(self, rc, mapping: dict, page_offset: int | None, dataset_id: str | None,
                 source_file_sha256: str | None, run_id: str):
        self.rc = rc
        self.contract = rc.contract
        self.fields = {f["path"]: f for f in self.contract["fields"]}
        self.mapping = mapping
        self.page_offset = page_offset
        self.dataset_id = dataset_id
        self.source_file_sha256 = source_file_sha256
        self.run_id = run_id
        self.validator = rc.validator()
        self.vocab = self.contract["vocabularies"]

    # ------------------------------------------------------------------ helpers
    def _code(self, vocab: str, value: Any) -> str | None:
        """Map a value to a vocabulary code by exact code, Chinese label or alias (no fuzzy matching)."""
        if not isinstance(value, str) or vocab not in self.vocab:
            return None
        v = value.strip()
        for item in self.vocab[vocab].get("values", []):
            forms = [item["code"], item.get("label_zh")] + list(item.get("aliases") or [])
            if any(isinstance(f, str) and f.casefold() == v.casefold() for f in forms):
                return item["code"]
        return None

    def _page(self, journal_page: Any) -> tuple[int | None, str | None]:
        if not isinstance(journal_page, int) or isinstance(journal_page, bool):
            return None, "LEGACY_PAGE_MISSING"
        if self.page_offset is None:
            return None, "LEGACY_PAGE_OFFSET_REQUIRED"
        physical = journal_page - self.page_offset
        return (physical, None) if physical >= 1 else (None, "LEGACY_PAGE_OFFSET_INVALID")

    # ------------------------------------------------------------------ document level
    def document_values(self, t: Tracker) -> tuple[dict, list[str]]:
        d: dict = {}
        notes: list[str] = []

        def put(path, value):
            if value not in EMPTY:
                d[path] = value
        put("common.source_title", t.get("doc_meta", "title"))
        put("common.source_doi", t.get("doc_meta", "doi"))
        put("common.source_year", t.get("doc_meta", "year"))
        authors = sorted(t.items("doc_meta", "authors"), key=lambda ia: (ia[1].get("rank") is None, ia[1].get("rank") or 0, ia[0]))
        names, affs = [], []
        for i, _ in authors:
            t.get("doc_meta", "authors", i, "rank")
            n = t.get("doc_meta", "authors", i, "name")
            if isinstance(n, str):
                names.append(n)
            a = t.get("doc_meta", "authors", i, "affiliation_name")
            if isinstance(a, str) and a not in affs:
                affs.append(a)
        for a in t.get("doc_meta", "affiliations", default=[]) or []:
            name = a.get("name") if isinstance(a, dict) else a
            if isinstance(name, str) and name not in affs:
                affs.append(name)
        put("common.source_authors", names)
        put("common.source_affiliations", affs)
        for leaf, path in (("journal", "common.source_journal"), ("volume", "common.source_volume"),
                           ("issue", "common.source_issue"), ("pages", "common.source_page_range"),
                           ("abstract", "common.source_abstract")):
            v = t.get("doc_meta", leaf)
            put(path, str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
        for leaf, path in (("keywords", "common.source_keywords"), ("funding", "common.source_funding")):
            v = t.get("doc_meta", leaf)
            put(path, [str(x) for x in v if x not in EMPTY] if isinstance(v, list) else ([v] if isinstance(v, str) else None))
        put("common.source_language", t.get("record_info", "lang"))
        doc_type = t.get("record_info", "doc_type")
        put("common.source_document_type", self._code("document_type", doc_type))
        if doc_type in PAPER_TYPES:
            d["common.source_type"] = "paper"
        elif doc_type == "experiment_report":
            d["common.source_type"] = "experiment_record"
        field = t.get("doc_meta", "field")
        crops = field if isinstance(field, list) else ([field] if field else [])
        if len(crops) == 1:
            put("common.crop_name", self._code("crop_name", crops[0]) or crops[0])
        elif len(crops) > 1:
            notes.append("doc_meta.field 含多个作物，crop_name 不确定（LEG-008）")
        species = t.items("doc_meta", "species_list")
        if len(species) == 1:
            put("common.species_name", t.get("doc_meta", "species_list", 0, "name"))
            if "common.crop_name" not in d:
                zh = t.get("doc_meta", "species_list", 0, "name_zh")
                put("common.crop_name", self._code("crop_name", zh) or zh)
        doi = d.get("common.source_doi")
        rid = t.get("record_id")
        d["common.source_id"] = f"doi:{doi.lower()}" if isinstance(doi, str) else f"urn:legacy-v1:{rid}"
        if isinstance(doi, str):
            d["common.source_uri"] = f"https://doi.org/{doi}"
        put("common.source_record_id", rid)
        sha = self.source_file_sha256
        if not sha:
            h = t.get("provenance", "integrity", "source_file_hash")
            sha = h if isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h) else None
        put("common.source_file_sha256", sha)
        method = t.get("provenance", "extraction", "method")
        if isinstance(method, str):
            m = self._code("extraction_method", method)
            if m is None and re.search(r"llm|模型|model", method, re.I):
                m = "model"
            elif m is None and re.search(r"rule|规则", method, re.I):
                m = "rule"
            put("common.extraction_method", m)
        return d, notes

    # ------------------------------------------------------------------ evidence
    def evidence_from_span(self, t: Tracker, keys: tuple, sections: dict) -> tuple[dict, list[str]]:
        span = t.get(*keys, default={}) or {}
        t.used.discard(keys)
        codes: list[str] = []
        sec = sections.get(span.get("section_id")) if isinstance(span, dict) else None
        if isinstance(span, dict) and span.get("section_id"):
            t.get(*keys, "section_id")
            if sec is None:
                codes.append("LEGACY_SECTION_REF_DANGLING")
        jp = t.get(*keys, "page")
        if jp is None and sec is not None:
            jp = sec[1].get("page")
            t.get("doc_meta", "document_sections", sec[0], "page")
        page, code = self._page(jp)
        if code:
            codes.append(code)
        snippet = t.get(*keys, "text_snippet")
        quote = None
        if isinstance(snippet, str):
            if NOT_VERBATIM.search(snippet):
                codes.append("LEGACY_SNIPPET_NOT_VERBATIM")
            else:
                quote = snippet
        ev = {k: v for k, v in (("page", page), ("quote", quote)) if v is not None}
        if jp is not None:
            ev["journal_page"] = jp
        return ev, codes

    # ------------------------------------------------------------------ records
    def record(self, kind: str, doc_values: dict, ev: dict, fields: dict, section: str | None, qc: list[str],
               ordinal: int) -> dict:
        rec: dict = {}
        for p, v in doc_values.items():
            set_path(rec, p, v)
        if "page" in ev:
            set_path(rec, "common.source_page", ev["page"])
        if "quote" in ev:
            set_path(rec, "common.source_quote", ev["quote"])
        if section:
            set_path(rec, "common.source_section", section)
        for p, v in fields.items():
            if v not in EMPTY:
                set_path(rec, p, v)
        locator = build_locator(page=ev.get("page"), section=section) or "document"
        grain = (self.contract["record_kinds"].get(kind) or {}).get("grain")
        codes = sorted(set(qc) | {"LEGACY_MIGRATED"} | ({"LEGACY_QUOTE_UNVERIFIED"} if "quote" in ev else set()))
        system = {
            "common.record_id": stable_record_id(doc_values["common.source_id"], kind, locator, ev.get("quote"), ordinal),
            "common.schema_name": self.rc.name, "common.schema_version": self.rc.version, "common.record_kind": kind,
            "common.record_grain": grain, "common.source_locator": locator, "common.review_status": "pending_review",
            "common.record_version": 1, "common.extraction_run_id": self.run_id,
            "common.qc_rule_set_version": f"{self.rc.name}@{self.rc.version}+legacy-migration@{GENERATOR_VERSION}",
            "common.qc_failure_codes": codes, "common.dataset_id": self.dataset_id,
        }
        for p, v in system.items():
            if v not in EMPTY and p in self.fields:
                set_path(rec, p, v)
        return rec

    def migrate(self, doc: dict) -> dict:
        t = Tracker(doc)
        doc_values, doc_notes = self.document_values(t)
        sections = {s.get("section_id"): (i, s) for i, s in t.items("doc_meta", "document_sections")}
        entities: dict[str, tuple[str, str, int, dict]] = {}   # entity_id -> (kind, name, index, raw)
        for kind in doc.get("breed_entities") or {}:
            for i, ent in t.items("breed_entities", kind):
                eid = ent.get("entity_id")
                name = next((ent[k] for k in ENTITY_NAME_KEYS if isinstance(ent.get(k), str) and ent.get(k)), None)
                if eid and name:
                    entities[eid] = (kind, name, i, ent)
        out: list[tuple[dict, str, int | None]] = []   # (record, source path, ...)
        candidates: dict[str, dict] = {}
        rejected: list[dict] = []
        ordinals: dict = {}

        def use_entity(eid: str, fields: dict) -> str | None:
            if eid not in entities:
                return None
            kind, name, i, ent = entities[eid]
            for key in ENTITY_NAME_KEYS:
                if ent.get(key) == name:
                    t.get("breed_entities", kind, i, key)
            target = ENTITY_TARGET.get(kind)
            if target:
                fields.setdefault(target, [])
                if name not in fields[target]:
                    fields[target].append(name)
            elif kind == "populations":
                fields["common.population_name"] = name
            return name

        def emit(kind, ev, fields, section, qc, source, review=None):
            key = (kind, ev.get("page"), section, ev.get("quote"))
            ordinal = ordinals.get(key, 0)
            ordinals[key] = ordinal + 1
            rec = self.record(kind, doc_values, ev, fields, section, qc, ordinal)
            res = self.validator.validate(rec)
            rid = rec["common"]["record_id"]
            if review:
                candidates[rid] = {"source": source, "values": review}
            if res.valid:
                out.append((rec, source, None))
                return rid
            rejected.append({"error_format": 1, "stage": "migration", "code": "RECORD_INVALID",
                             "message": "迁移记录未通过契约校验", "source_path": source,
                             "issues": [i.to_dict() for i in res.errors], "record": rec})
            return None

        # relations -> claim (S-P-O); inferred relations are skipped
        relation_ids: dict[str, str] = {}
        relation_evidence: dict[str, tuple[dict, list[str], str | None]] = {}
        for i, rel in t.items("relations"):
            src = f"relations[{i}]"
            if rel.get("is_inferred") is True:
                t.get("relations", i, "is_inferred")
                continue
            t.get("relations", i, "is_inferred")
            fields: dict = {}
            s = use_entity(t.get("relations", i, "subject", "entity_id") or "", fields)
            o = use_entity(t.get("relations", i, "object", "entity_id") or "", fields)
            if s:
                fields["transform.subject_mention"] = s
            if o:
                fields["transform.object_mention"] = o
            vm = t.get("relations", i, "supporting_method")
            if vm:
                fields["agent.validation_methods"] = vm if isinstance(vm, list) else [str(vm)]
            section = t.get("relations", i, "source_section")
            ev, codes = {}, ["LEGACY_NO_EVIDENCE"]
            for j, _ in t.items("relations", i, "evidence_spans"):
                ev, codes = self.evidence_from_span(t, ("relations", i, "evidence_spans", j), sections)
                if "page" in ev and "quote" in ev:
                    break
            review = {}
            for leaf, field, vocab in (("relation_type", "transform.predicate_label", "predicate_label"),
                                       ("effect_direction", "transform.relation_polarity", "relation_polarity")):
                raw = t.get("relations", i, leaf)
                if raw is not None:
                    review[field] = {"raw": raw, "code": self._code(vocab, raw)}
            for leaf, field in (("relation_mechanism", "agent.candidate_mechanism"),):
                raw = t.get("relations", i, leaf)
                if raw is not None:
                    review[field] = {"raw": raw}
            for side, field in (("subject", "transform.subject_type"), ("object", "transform.object_type")):
                raw = t.get("relations", i, side, "entity_type")
                if raw is not None:
                    review[field] = {"raw": raw}
            rid = emit("claim", ev, fields, section, codes, src, review)
            if rel.get("relation_id"):
                t.get("relations", i, "relation_id")
                relation_evidence[rel["relation_id"]] = (ev, codes, section)
                if rid:
                    relation_ids[rel["relation_id"]] = rid

        # conclusions -> claim (evidence resolved through supporting relations)
        for i, c in t.items("conclusions"):
            src = f"conclusions[{i}]"
            text = t.get("conclusions", i, "claim_text")
            if not text:
                continue
            fields = {"agent.finding_text": text}
            ev, codes, section = {}, ["LEGACY_NO_EVIDENCE"], None
            supporting = t.get("conclusions", i, "supporting_relations", default=[]) or []
            for rel_id in supporting:
                if rel_id in relation_evidence and "quote" in relation_evidence[rel_id][0]:
                    ev, codes, section = relation_evidence[rel_id]
                    codes = codes + ["LEGACY_INDIRECT_EVIDENCE"]
                    break
            ids = [relation_ids[r] for r in supporting if r in relation_ids]
            if ids:
                fields["agent.evidence_record_ids"] = ids
            review = {}
            for leaf, field in (("conclusion_type", "agent.finding_kind"), ("confidence_level", "agent.evidence_strength"),
                                ("scope_constraints", "agent.external_validity_scope"),
                                ("causal_flag", "agent.association_vs_causation"),
                                ("contradiction_note", "agent.uncertainty_note")):
                raw = t.get("conclusions", i, leaf)
                if raw is not None:
                    review[field] = {"raw": raw}
            emit("claim", ev, fields, section, codes, src, review)

        # QTLs -> observation (+ one analysis_result per effect estimate)
        analyses = {a.get("analysis_id"): a for _, a in t.items("analyses")}
        qtl_kind = next((k for k in (doc.get("breed_entities") or {}) if k == "qtls"), None)
        for i, q in (t.items("breed_entities", "qtls") if qtl_kind else []):
            src = f"breed_entities.qtls[{i}]"
            fields: dict = {}
            name = t.get("breed_entities", "qtls", i, "qtl_name") or q.get("name")
            if not name:
                continue
            fields["common.qtl_names"] = [name]
            fields["common.chromosome"] = (lambda c: str(c) if c is not None else None)(t.get("breed_entities", "qtls", i, "chromosome"))
            unit = t.get("breed_entities", "qtls", i, "interval", "unit")
            lo, hi = t.get("breed_entities", "qtls", i, "interval", "start"), t.get("breed_entities", "qtls", i, "interval", "end")
            qc: list[str] = []
            if unit == "cM":
                fields["common.locus_interval_start_cm"], fields["common.locus_interval_end_cm"] = lo, hi
            elif unit in ("bp", "kb", "Mb"):
                factor = {"bp": 1, "kb": 1000, "Mb": 1_000_000}[unit]
                for p, v in (("common.locus_interval_start_bp", lo), ("common.locus_interval_end_bp", hi)):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        fields[p] = int(round(v * factor))
                if unit != "bp":
                    qc.append("LEGACY_INTERVAL_UNIT_CONVERTED")
            elif unit is not None:
                t.used.discard(("breed_entities", "qtls", i, "interval", "unit"))
                t.used.discard(("breed_entities", "qtls", i, "interval", "start"))
                t.used.discard(("breed_entities", "qtls", i, "interval", "end"))
            pv = t.get("breed_entities", "qtls", i, "p_value")
            if isinstance(pv, (int, float)) and 0 <= pv <= 1:
                fields["agent.p_value"] = pv
            pve = t.get("breed_entities", "qtls", i, "pve")
            if isinstance(pve, (int, float)):
                fields["agent.pve_percent"] = pve
            refs = q.get("analysis_ref") or []
            types = [str((analyses.get(r) or {}).get("analysis_type", "")) for r in refs]
            if q.get("lod") is not None and types and not any("GWAS" in x.upper() for x in types) \
                    and any(re.search(r"QTL|连锁|linkage", x, re.I) for x in types):
                fields["agent.lod_score"] = t.get("breed_entities", "qtls", i, "lod")
            pop = t.get("breed_entities", "qtls", i, "population_used")
            if isinstance(pop, str):
                use_entity(pop, fields) or fields.setdefault("common.population_name", pop)
            for leaf in ("nearest_markers", "candidate_genes"):
                for ref in t.get("breed_entities", "qtls", i, leaf, default=[]) or []:
                    if not use_entity(ref, fields) and isinstance(ref, str):
                        target = "common.marker_names" if leaf == "nearest_markers" else "common.gene_names"
                        fields.setdefault(target, [])
                        if ref not in fields[target]:
                            fields[target].append(ref)
            ev, codes = {}, ["LEGACY_NO_EVIDENCE"]
            eid = q.get("entity_id")
            for rel_id, (rev, rcodes, rsec) in relation_evidence.items():
                rel = next((r for r in doc.get("relations") or [] if r.get("relation_id") == rel_id), {})
                if eid and eid in ((rel.get("subject") or {}).get("entity_id"), (rel.get("object") or {}).get("entity_id")) \
                        and "quote" in rev:
                    ev, codes = rev, rcodes + ["LEGACY_INDIRECT_EVIDENCE"]
                    break
            emit("observation", ev, fields, None, codes + qc, src)
            for leaf in ("additive_effect", "dominance_effect"):
                val = t.get("breed_entities", "qtls", i, leaf)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    emit("analysis_result", ev, {"common.qtl_names": [name], "agent.effect_estimate": val,
                                                 "agent.effect_type": leaf}, None, codes, f"{src}.{leaf}")

        # gene / trait entities that carry their own resolvable evidence -> observation
        for kind in ("genes", "traits"):
            for i, ent in t.items("breed_entities", kind):
                ev, codes = {}, []
                for j, _ in t.items("breed_entities", kind, i, "evidence_spans"):
                    ev, codes = self.evidence_from_span(t, ("breed_entities", kind, i, "evidence_spans", j), sections)
                    if "page" in ev and "quote" in ev:
                        break
                if not ("page" in ev and "quote" in ev):
                    continue
                src = f"breed_entities.{kind}[{i}]"
                fields: dict = {}
                use_entity(ent.get("entity_id", ""), fields)
                review: dict = {}
                if kind == "genes":
                    chrom = t.get("breed_entities", kind, i, "chromosome")
                    fields["common.chromosome"] = str(chrom) if chrom is not None else None
                    fields["common.genome_assembly"] = t.get("breed_entities", kind, i, "position", "ref_genome")
                    for leaf, path in (("start_bp", "common.locus_interval_start_bp"), ("end_bp", "common.locus_interval_end_bp")):
                        val = t.get("breed_entities", kind, i, "position", leaf)
                        if isinstance(val, int) and not isinstance(val, bool):
                            fields[path] = val
                    linked = t.get("breed_entities", kind, i, "linked_traits", default=[]) or []
                    for ref in linked if isinstance(linked, list) else [linked]:
                        if not use_entity(ref, fields) and isinstance(ref, str):
                            fields.setdefault("common.trait_names", []).append(ref)
                else:
                    fields["common.growth_stage"] = t.get("breed_entities", kind, i, "measurement_detail", "stage")
                    fields["common.organ"] = t.get("breed_entities", kind, i, "measurement_detail", "organ")
                    fields["common.trait_measurement_protocol"] = t.get("breed_entities", kind, i, "measurement_detail", "method_standard")
                    cat = t.get("breed_entities", kind, i, "trait_category")
                    if cat is not None:
                        review["common.trait_category"] = {"raw": cat, "code": [self._code("trait_category", c) for c in cat]
                                                           if isinstance(cat, list) else self._code("trait_category", cat)}
                    h2 = t.get("breed_entities", kind, i, "heritability_h2_estimate")
                    if isinstance(h2, (int, float)) and not isinstance(h2, bool):
                        emit("analysis_result", ev, {"common.trait_names": fields.get("common.trait_names"),
                                                     "skills.metric_name": "heritability_h2_estimate", "skills.metric_value": h2},
                             None, codes + ["LEGACY_ENTITY_EVIDENCE"], f"{src}.heritability_h2_estimate")
                emit("observation", ev, fields, None, codes + ["LEGACY_ENTITY_EVIDENCE"], src, review)

        # analyses -> method (one per software tool); key_results -> analysis_result
        for i, a in t.items("analyses"):
            src = f"analyses[{i}]"
            base: dict = {}
            base["skills.method_name"] = t.get("analyses", i, "analysis_name")
            base["skills.algorithm_name"] = t.get("analyses", i, "model_name")
            cat = self._code("method_category", a.get("analysis_type"))
            if cat is None and isinstance(a.get("analysis_type"), str):
                cat = next((v["code"] for v in self.vocab["method_category"]["values"]
                            if v.get("label_zh") and v["label_zh"] in a["analysis_type"]), None)
            if cat:
                t.get("analyses", i, "analysis_type")
                base["skills.method_category"] = cat
            thr = []
            for j, _ in t.items("analyses", i, "significance_thresholds"):
                parts = [t.get("analyses", i, "significance_thresholds", j, k) for k in ("metric", "value", "correction_method")]
                thr.append(" ".join(str(p) for p in parts if p not in EMPTY))
            if thr:
                base["skills.significance_threshold"] = "; ".join(thr)
            params = []
            for j, p in t.items("analyses", i, "parameters"):
                pname = t.get("analyses", i, "parameters", j, "param_name")
                if not pname:
                    continue
                item = {"name": str(pname)}
                val = t.get("analyses", i, "parameters", j, "param_value")
                if isinstance(val, (str, int, float, bool)):
                    item["value"] = val
                kind = t.get("analyses", i, "parameters", j, "param_type")
                if isinstance(kind, str):
                    item["value_kind"] = kind
                params.append(item)
            if params:
                base["skills.parameters"] = params
            for leaf, field in (("strategy", "skills.validation_strategy"), ("k_folds", "skills.folds"),
                                ("metric", "skills.metric_name")):
                v = t.get("analyses", i, "validation_design", leaf)
                if v is not None:
                    base[field] = v
            tools = t.items("analyses", i, "software_tools") or [(None, {})]
            for j, _ in tools:
                fields = dict(base)
                if j is not None:
                    fields["skills.software_name"] = t.get("analyses", i, "software_tools", j, "tool_name")
                    ver = t.get("analyses", i, "software_tools", j, "version")
                    fields["skills.software_version"] = str(ver) if ver is not None else None
                emit("method", {}, fields, None, ["LEGACY_NO_EVIDENCE"], src)
            kr = a.get("key_results")
            if isinstance(kr, dict):
                for k, v in kr.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        emit("analysis_result", {}, {"skills.metric_name": str(k), "skills.metric_value": v},
                             None, ["LEGACY_NO_EVIDENCE"], f"{src}.key_results.{k}")
                if any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in kr.values()):
                    t.used.add(("analyses", i, "key_results"))

        # residue: every non-empty leaf not consumed
        residue = []
        for path, value in _leaves(doc):
            if t.consumed(path):
                continue
            norm = _norm(path)
            entry = match_entry(self.mapping["entries"], norm)
            residue.append({"path": _concrete(path), "value": value,
                            "mapping": ({k: entry[k] for k in ("status", "target", "targets", "note_zh", "issues") if k in entry}
                                        if entry else {"status": "not_in_legacy_schema"})})
        return {"records": [r for r, _, _ in out], "record_sources": {r["common"]["record_id"]: src for r, src, _ in out},
                "rejected": rejected, "review_candidates": candidates,
                "residue": residue, "notes": doc_notes, "consumed_leaf_paths": sorted({_norm(p) for p, _ in _leaves(doc) if t.consumed(p)})}


def load_legacy_mapping(root: Path) -> dict:
    return load_yaml(root / "mappings/legacy_to_current.yaml")


def _item_id(doc: dict, source_path: str) -> str | None:
    """Legacy ID (relation_id, conclusion_id, entity_id, ...) of the innermost item on ``source_path``."""
    node, found = doc, None
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", source_path):
        node = node[int(part[1:-1])] if part.startswith("[") and isinstance(node, list) else \
            (node.get(part) if isinstance(node, dict) else None)
        if isinstance(node, dict):
            ids = [v for k, v in node.items() if k.endswith("_id") and isinstance(v, str) and k != "section_id"]
            found = ids[0] if ids else found
    return found


def migrate_legacy_file(path: Path | str, out_dir: Path | str, version: str = "latest", page_offset: int | None = None,
                        dataset_id: str | None = None, source_file_sha256: str | None = None,
                        root: Path | str | None = None) -> dict:
    root = repo_root(root)
    path, out_dir = Path(path), Path(out_dir)
    rc = resolve_schema(version, root)
    if parse_semver(rc.version.split("-")[0]) < MIN_VERSION:
        raise ContractError(f"legacy migration targets contract >= 3.1.0 (got {rc.version})")
    mapping = load_legacy_mapping(root)
    started = utc_now()
    run_id = "mig_" + started.strftime("%Y%m%dT%H%M%SZ") + "_" + sha256_file(path)[:8]
    mig = LegacyMigrator(rc, mapping, page_offset, dataset_id, source_file_sha256, run_id)
    records, rejected, residue, candidates, notes, consumed, sources = [], [], [], {}, [], set(), {}
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for n, line in enumerate(lines, 1):
        doc = json.loads(line)
        res = mig.migrate(doc)
        records += res["records"]
        for rid, sp in res["record_sources"].items():
            sources[rid] = {"input_line": n, "source_path": sp,
                            **({"source_item_id": iid} if (iid := _item_id(doc, sp)) else {})}
        rejected += [{**e, "input_line": n} for e in res["rejected"]]
        residue += [{**r, "input_line": n} for r in res["residue"]]
        candidates.update(res["review_candidates"])
        notes += res["notes"]
        consumed |= set(res["consumed_leaf_paths"])
    dataset_issues = mig.validator.validate_dataset(records)
    for idx, issue in sorted(dataset_issues, key=lambda x: -x[0]):
        if issue.severity == "error":
            rejected.append({"error_format": 1, "stage": "dataset", "code": "DATASET_RULE", "message": issue.message,
                             "issues": [issue.to_dict()], "record": records.pop(idx)})
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.name[:-6] if path.name.endswith(".jsonl") else path.stem
    outs = {"records": out_dir / f"{stem}.migrated.jsonl", "errors": out_dir / f"{stem}.migrated.errors.jsonl",
            "residue": out_dir / f"{stem}.residue.json", "report": out_dir / f"{stem}.migration.json"}
    outs["records"].write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    outs["errors"].write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in rejected), encoding="utf-8")
    outs["residue"].write_text(dumps_json({"residue_format": 1, "source": path.name, "unconsumed": residue,
                                           "review_candidates": candidates}), encoding="utf-8")
    by_code: dict = {}
    for e in rejected:
        for i in e.get("issues") or [{"code": e["code"]}]:
            by_code[i["code"]] = by_code.get(i["code"], 0) + 1
    report = {
        "migration_format": 1, "run_id": run_id, "created_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"file_name": path.name, "sha256": sha256_file(path), "documents": len(lines), "schema_version": "v1.0.0"},
        "contract": rc.identity(), "mapping": {"id": mapping["id"], "sha256": sha256_file(root / "mappings/legacy_to_current.yaml")},
        "options": {"page_offset": page_offset, "dataset_id": dataset_id, "source_file_sha256": source_file_sha256},
        "counts": {"records": len(records), "rejected": len(rejected), "residue_leaves": len(residue),
                   "review_candidates": len(candidates), "rejected_issue_codes": dict(sorted(by_code.items()))},
        "notes": notes,
        "consumed_leaf_paths": sorted(consumed),
        "record_sources": {r["common"]["record_id"]: sources[r["common"]["record_id"]] for r in records},
        "outputs": {k: {"file": p.name, "sha256": sha256_file(p)} for k, p in outs.items() if k != "report"},
        "tooling": {"breeding_contract": GENERATOR_VERSION},
    }
    outs["report"].write_text(dumps_json(report), encoding="utf-8")
    return {"outputs": {k: str(v) for k, v in outs.items()}, **report["counts"]}
