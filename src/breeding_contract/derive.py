"""Derived views for function 3: relational tables, knowledge-graph triples and an evidence corpus.

Everything is driven by the catalog, never by field lists in code: each field's ``key_role`` decides where it
lands (see ``codes.key_role.*.projection``). The views are lossless for the values they carry and never add a
value that is not in the records. QA pairs are not generated here (the ``transform.qa_*`` fields are G,
produced downstream); the evidence corpus gives them the citable units they must point to.

    tables   records, sources, record_entities, record_links, record_values   (one row per value; CSV-ready)
    triples  {s, p, o, o_kind, record_id}; statements from transform subject/predicate/object carry qualifiers
    corpus   one chunk per distinct verbatim quote, with the IDs of every record it supports
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from .ids import normalize_text
from .util import MISSING, dumps_json, dumps_jsonl, get_path, iter_fields

ENTITY_SUFFIX = re.compile(r"(_names|_name|_ids|_id|_accessions)$")
SOURCE_ROLES = ("source_identity", "bibliographic")
ENTITY_ROLES = ("entity_mention", "entity_id")


def entity_type(path: str) -> str:
    """Entity type named by the field (common.gene_names -> gene, common.crop_taxon_id -> crop_taxon)."""
    return ENTITY_SUFFIX.sub("", path.split(".", 1)[1]) or path.split(".", 1)[1]


def _cell(v) -> str | int | float | bool:
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v


_WS = re.compile(r"\s+")


_IRI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:\S+$")


def _ent_iri(etype: str, value: str) -> str:
    return f"ent:{etype}/" + _WS.sub("_", normalize_text(value))


def _id_kind(value: str) -> str:
    """An identifier is an IRI only when it already is one (scheme or CURIE); a bare accession, DOI or hash
    stays an ``id`` literal so the consumer applies its own namespace policy instead of ours."""
    return "iri" if _IRI.match(value) else "id"


class Deriver:
    def __init__(self, contract: dict):
        self.contract = contract
        self.fields = {f["path"]: f for f in contract["fields"]}
        self.order = [f["path"] for f in contract["fields"]]
        self.role = {p: f.get("key_role") for p, f in self.fields.items()}

    def _role_paths(self, *roles: str) -> list[str]:
        return [p for p in self.order if self.role.get(p) in roles]

    # ------------------------------------------------------------------ relational tables
    def tables(self, records: list[dict]) -> dict[str, list[dict]]:
        rec_rows, entities, links, values = [], [], [], []
        sources: dict[str, dict] = {}
        source_paths = self._role_paths(*SOURCE_ROLES)
        for rec in records:
            rid = get_path(rec, "common.record_id", None)
            row = {"record_id": rid}
            for path, v in iter_fields(rec):
                role = self.role.get(path)
                if role in SOURCE_ROLES and path != "common.source_id":
                    continue  # lives in `sources`
                if role in ENTITY_ROLES:
                    for i, x in enumerate(v if isinstance(v, list) else [v]):
                        entities.append({"record_id": rid, "field": path, "position": i, "entity_type": entity_type(path),
                                         ("entity_id" if role == "entity_id" else "mention"): x})
                elif role == "record_link" and self.fields[path]["type"] == "array_string":
                    for x in v:
                        links.append({"record_id": rid, "field": path, "target_record_id": x,
                                      "argument_role": self.fields[path].get("argument_role", "")})
                elif isinstance(v, list):
                    for i, x in enumerate(v):
                        values.append({"record_id": rid, "field": path, "position": i, "value": _cell(x)})
                else:
                    row[path] = _cell(v)
            rec_rows.append(row)
            sid = get_path(rec, "common.source_id", None)
            if sid is not None:
                src = sources.setdefault(sid, {"source_id": sid})
                for p in source_paths:
                    v = get_path(rec, p)
                    if v is not MISSING and p not in src:
                        src[p] = _cell(v)
        for rec in records:  # explicit mention -> ID pairs from entity alignment (AMB-034)
            rid = get_path(rec, "common.record_id", None)
            for p in self._role_paths("entity_alignment"):
                if self.fields[p]["type"] != "array_entity_link":
                    continue
                for i, link in enumerate(get_path(rec, p, None) or []):
                    entities.append({"record_id": rid, "field": link.get("source_field", p), "position": i,
                                     "entity_type": link.get("entity_type") or entity_type(link.get("source_field", p)),
                                     "mention": link.get("mention"), "entity_id": link.get("entity_id", ""),
                                     "alignment_status": link.get("alignment_status", "")})
        return {"records": rec_rows, "sources": list(sources.values()), "record_entities": entities,
                "record_links": links, "record_values": values}

    # ------------------------------------------------------------------ triples
    def triples(self, records: list[dict]) -> list[dict]:
        out: list[dict] = []
        relation = {p.split(".", 1)[1]: p for p in self._role_paths("relation")}

        def add(s, p, o, kind, rid, **extra):
            out.append({"s": s, "p": p, "o": o, "o_kind": kind, "record_id": rid, **extra})
        for rec in records:
            rid = get_path(rec, "common.record_id", None)
            node = f"rec:{rid}"
            kind = get_path(rec, "common.record_kind", None)
            if kind:
                add(node, "rdf:type", f"bdc:{kind}", "iri", rid)
            for path, v in iter_fields(rec):
                role = self.role.get(path)
                if role in ("record_identity",) or path in relation.values():
                    continue
                items = v if isinstance(v, list) else [v]
                for x in items:
                    if role == "entity_mention" and isinstance(x, str):
                        iri = _ent_iri(entity_type(path), x)
                        add(node, f"bdc:{path}", iri, "iri", rid)
                        add(iri, "rdfs:label", x, "literal", rid)
                        add(iri, "rdf:type", f"bdc:entity/{entity_type(path)}", "iri", rid)
                    elif role == "record_link" and isinstance(x, str):
                        add(node, f"bdc:{path}", f"rec:{x}", "iri", rid)
                    elif role in ("entity_id", "source_identity") and isinstance(x, str) \
                            and not self.fields[path].get("vocabulary"):
                        add(node, f"bdc:{path}", x, _id_kind(x), rid)
                    elif not isinstance(x, (dict, list)):
                        add(node, f"bdc:{path}", x, "literal", rid)
                    else:
                        add(node, f"bdc:{path}", json.dumps(x, ensure_ascii=False), "json", rid)
            subj = self._relation_end(rec, relation, "subject")
            obj = self._relation_end(rec, relation, "object")
            pred = get_path(rec, relation.get("predicate_id", ""), None) or get_path(rec, relation.get("predicate_label", ""), None)
            if subj and obj:
                extra = {"statement": get_path(rec, relation.get("graph_statement_id", ""), None) or node}
                for k in ("relation_polarity", "relation_qualifiers", "relation_evidence_type"):
                    v = get_path(rec, relation.get(k, ""), None)
                    if v is not None:
                        extra[k] = v
                # A statement without a reviewed predicate keeps the gap visible instead of inventing one.
                add(subj, f"bdc:{pred}" if pred else "bdc:unlabelled_relation", obj, "iri", rid, **extra)
        return out

    def _relation_end(self, rec: dict, relation: dict[str, str], end: str) -> str | None:
        """IRI of a statement end: the aligned ID, else the typed entity node of the mention. Without a
        reviewed type, the type is taken from the record's own entity fields when exactly one of them lists
        the same mention, so the statement joins the entity graph; otherwise it stays generic."""
        eid = get_path(rec, relation.get(f"{end}_id", ""), None)
        if eid:
            return eid
        mention = get_path(rec, relation.get(f"{end}_mention", ""), None)
        if not mention:
            return None
        etype = get_path(rec, relation.get(f"{end}_type", ""), None)
        if not etype:
            key = normalize_text(mention)
            types = {entity_type(p) for p, v in iter_fields(rec) if self.role.get(p) == "entity_mention"
                     and any(isinstance(x, str) and normalize_text(x) == key for x in (v if isinstance(v, list) else [v]))}
            etype = types.pop() if len(types) == 1 else "entity"
        return _ent_iri(etype, mention)

    # ------------------------------------------------------------------ corpus
    def corpus(self, records: list[dict]) -> list[dict]:
        quote_path = next((p for p in self._role_paths("evidence_locator") if p.endswith("source_quote")), None)
        chunks: dict[tuple, dict] = {}
        for rec in records:
            q = get_path(rec, quote_path, None) if quote_path else None
            if not q:
                continue
            sid = get_path(rec, "common.source_id", None)
            page = get_path(rec, "common.source_page", None)
            key = (sid, page, normalize_text(q))
            c = chunks.get(key)
            if c is None:
                cid = "chk_" + hashlib.sha256("\x1f".join(map(str, key)).encode("utf-8")).hexdigest()[:24]
                c = chunks[key] = {"chunk_id": cid, "text": q, "source_id": sid, "page": page,
                                   "section": get_path(rec, "common.source_section", None),
                                   "support_ids": [], "record_kinds": []}
                for p in ("common.license_id", "common.access_level"):
                    v = get_path(rec, p, None)
                    if v is not None:
                        c[p.split(".")[1]] = v
            c["support_ids"].append(get_path(rec, "common.record_id", None))
            k = get_path(rec, "common.record_kind", None)
            if k not in c["record_kinds"]:
                c["record_kinds"].append(k)
        return [{k: v for k, v in c.items() if v is not None} for c in chunks.values()]


def derive_file(path: Path | str, out_dir: Path | str, rc) -> dict:
    """Write <stem>.tables/*.csv, <stem>.triples.jsonl, <stem>.corpus.jsonl and <stem>.derive.json."""
    path, out_dir = Path(path), Path(out_dir)
    records = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    d = Deriver(rc.contract)
    stem = path.name[:-6] if path.name.endswith(".jsonl") else path.stem
    tdir = out_dir / f"{stem}.tables"
    tdir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, rows in d.tables(records).items():
        cols: list[str] = []
        for r in rows:
            cols += [k for k in r if k not in cols]
        with (tdir / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols or ["record_id"])
            w.writeheader()
            w.writerows(rows)
        counts[f"table:{name}"] = len(rows)
    triples, corpus = d.triples(records), d.corpus(records)
    (out_dir / f"{stem}.triples.jsonl").write_text(dumps_jsonl(triples), encoding="utf-8")
    (out_dir / f"{stem}.corpus.jsonl").write_text(dumps_jsonl(corpus), encoding="utf-8")
    counts.update({"triples": len(triples), "corpus_chunks": len(corpus), "records": len(records)})
    report = {"derive_format": 1, "input": path.name, "contract": rc.identity(), "counts": counts}
    (out_dir / f"{stem}.derive.json").write_text(dumps_json(report), encoding="utf-8")
    return report
