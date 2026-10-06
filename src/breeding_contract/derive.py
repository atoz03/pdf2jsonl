"""Derived views for function 3: one set of records, several downstream forms.

    tables      records, sources, record_entities, record_links, record_values, statements   (CSV-ready rows)
    triples     {s, p, o, o_kind, record_id}; a statement carries its predicate status, qualifiers and hedge
    graph       {nodes, edges}: entities, records and sources as a property graph
    corpus      one chunk per distinct verbatim quote, with entity offsets and the IDs of what it supports
    qa          cloze seeds: a quote with one anchored answer masked, citing the records that support it

Everything is driven by the catalog, never by field lists in code: each field's ``key_role`` decides where it
lands (see ``codes.key_role.*.projection``). The views are lossless for the values they carry and never add a
value that is not in the records. They read the hooks the records already carry (AMB-038): the statement
(subject, predicate, object), the entity markers with their offsets in the quote, and the record links. Where
a record has no hook, the view has no row; nothing is recovered by parsing text.

Corpus and QA rows are keyed by the catalog's ``transform`` field names (``chunk_id``, ``qa_seed_question`` …),
so a row can be stored back as those G fields.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from .ids import normalize_text
from .relations import RELATION_ENDS, entity_type, find_span
from .util import canonical_json, dumps_json, dumps_jsonl, get_path, iter_fields

DERIVE_FORMAT = 2
SOURCE_ROLES = ("source_identity", "bibliographic")
ENTITY_ROLES = ("entity_mention", "entity_id")
QUALIFIER_ROLES = ("condition", "context_key")   # the conditions under which a statement holds
VALUE_ROLES = ("statistic", "measurement")       # literal values a question can ask for
CLOZE_BLANK = "____"
MIN_CLOZE_CONTEXT = 20                           # characters of quote left around the blank


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


def _digest(prefix: str, *parts, n: int = 24) -> str:
    return prefix + hashlib.sha256("\x1f".join(map(str, parts)).encode("utf-8")).hexdigest()[:n]


def _items(v) -> list:
    return v if isinstance(v, list) else [v]


class Deriver:
    def __init__(self, contract: dict):
        self.contract = contract
        self.fields = {f["path"]: f for f in contract["fields"]}
        self.order = [f["path"] for f in contract["fields"]]
        self.role = {p: f.get("key_role") for p, f in self.fields.items()}
        self.relation = {p.split(".", 1)[1]: p for p in self._role_paths("relation")}
        self.markers_path = next((p for p, f in self.fields.items() if f["type"] == "array_entity_link"), None)
        self.quote_path = "common.source_quote"
        self.hedge_paths = [p for p in self._role_paths("assertion") if self.fields[p].get("argument_role") == "qualifier"]
        self.assertion_paths = [p for p in self._role_paths("assertion") if not self.fields[p].get("argument_role")
                                or self.fields[p].get("argument_role") == "claim"]

    def _role_paths(self, *roles: str) -> list[str]:
        return [p for p in self.order if self.role.get(p) in roles]

    def _rel(self, rec: dict, leaf: str):
        path = self.relation.get(leaf)
        return get_path(rec, path, None) if path else None

    def _markers(self, rec: dict) -> list[dict]:
        value = get_path(rec, self.markers_path, None) if self.markers_path else None
        return [m for m in value or [] if isinstance(m, dict) and m.get("mention")]

    def _quote(self, rec: dict):
        return get_path(rec, self.quote_path, None) if self.quote_path else None

    # ------------------------------------------------------------------ statements
    def statement(self, rec: dict) -> dict | None:
        """The record's relation as an explicit statement, or None when it states none.

        Ends are resolved in this order: a reviewed ID, the entity marker playing the role (its type and
        offsets), and for records without markers the record's own entity fields when exactly one of them lists
        the mention. The predicate is the ontology ID, else the reviewed label, else the lexicon code, else the
        verbatim words; ``predicate_status`` says which, so a consumer can filter on how much was reviewed.
        """
        ends: dict[str, dict] = {}
        markers = self._markers(rec)
        for end in RELATION_ENDS:
            mention, eid = self._rel(rec, f"{end}_mention"), self._rel(rec, f"{end}_id")
            if not mention and not eid:
                return None
            mine = [m for m in markers if m.get("relation_role") == end]
            etype = self._rel(rec, f"{end}_type")
            if not etype:
                types = {m["entity_type"] for m in mine if m.get("entity_type")}
                if not mine and mention:
                    key = normalize_text(mention)
                    types = {entity_type(p) for p, v in iter_fields(rec) if self.role.get(p) == "entity_mention"
                             and any(isinstance(x, str) and normalize_text(x) == key for x in _items(v))}
                etype = types.pop() if len(types) == 1 else None
            eid = eid or next((m["entity_id"] for m in mine if m.get("entity_id")), None)
            anchor = next((m for m in mine if "start" in m and "end" in m), None)
            ends[end] = {"node": eid or _ent_iri(etype or "entity", mention), "mention": mention, "type": etype,
                         "id": eid, "span": [anchor["start"], anchor["end"]] if anchor else None}
        pid, label, code, verbatim = (self._rel(rec, k) for k in
                                      ("predicate_id", "predicate_label", "predicate_code", "predicate_mention"))
        if pid:
            predicate, status = (pid if _IRI.match(pid) else f"bdc:{pid}"), "ontology"
        elif label:
            predicate, status = f"bdc:{label}", "reviewed"
        elif code:
            predicate, status = f"bdc:{code}", "lexicon"
        elif verbatim:
            predicate, status = "bdc:stated_relation", "verbatim"
        else:  # A statement without a predicate keeps the gap visible instead of inventing one.
            predicate, status = "bdc:unlabelled_relation", "unlabelled"
        qualifiers = {p: v for p, v in iter_fields(rec) if self.role.get(p) in QUALIFIER_ROLES}
        qualifiers.update(self._rel(rec, "relation_qualifiers") or {})
        rid, sid = get_path(rec, "common.record_id", None), get_path(rec, "common.source_id", None)
        out = {
            "statement_id": self._rel(rec, "graph_statement_id") or _digest(
                "stm_", sid, ends["subject"]["node"], predicate, verbatim or "", ends["object"]["node"],
                canonical_json(qualifiers)),
            "record_id": rid,
            "subject": ends["subject"]["node"], "subject_mention": ends["subject"]["mention"],
            "subject_type": ends["subject"]["type"], "subject_id": ends["subject"]["id"],
            "predicate": predicate, "predicate_mention": verbatim, "predicate_status": status,
            "object": ends["object"]["node"], "object_mention": ends["object"]["mention"],
            "object_type": ends["object"]["type"], "object_id": ends["object"]["id"],
            "relation_polarity": self._rel(rec, "relation_polarity"),
            "relation_evidence_type": self._rel(rec, "relation_evidence_type"),
            "hedge": next((get_path(rec, p, None) for p in self.hedge_paths if get_path(rec, p, None)), None),
            "qualifiers": qualifiers or None,
            "source_id": sid, "source_page": get_path(rec, "common.source_page", None),
            "source_quote": self._quote(rec),
        }
        start, end = self._rel(rec, "predicate_start_offset"), self._rel(rec, "predicate_end_offset")
        anchors = {"subject": ends["subject"]["span"], "object": ends["object"]["span"],
                   "predicate": [start, end] if start is not None and end is not None else None}
        if any(anchors.values()):
            out["anchors"] = {k: v for k, v in anchors.items() if v}
        return {k: v for k, v in out.items() if v is not None}

    def statements(self, records: list[dict]) -> list[dict]:
        return [s for s in (self.statement(r) for r in records) if s]

    # ------------------------------------------------------------------ relational tables
    def tables(self, records: list[dict]) -> dict[str, list[dict]]:
        rec_rows, entities, links, values = [], [], [], []
        sources: dict[str, dict] = {}
        source_paths = self._role_paths(*SOURCE_ROLES)
        for rec in records:
            rid = get_path(rec, "common.record_id", None)
            row = {"record_id": rid}
            markers = self._markers(rec)
            marked = {(m.get("source_field"), normalize_text(m["mention"])) for m in markers}
            for path, v in iter_fields(rec):
                role = self.role.get(path)
                if role in SOURCE_ROLES and path != "common.source_id":
                    continue  # lives in `sources`
                if path == self.markers_path:
                    continue  # one row per marker in `record_entities`, below
                if role in ENTITY_ROLES:
                    for i, x in enumerate(_items(v)):
                        if role == "entity_mention" and isinstance(x, str) and (path, normalize_text(x)) in marked:
                            continue  # the marker carries the same mention with its anchor
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
            # explicit mention -> anchor / ID pairs; *_names and *_ids are never paired by position (AMB-034)
            for i, m in enumerate(markers):
                field = m.get("source_field") or self.markers_path
                entities.append({"record_id": rid, "field": field, "position": i,
                                 "entity_type": m.get("entity_type") or (entity_type(field) if self.role.get(field)
                                                                         in ENTITY_ROLES else "entity"),
                                 "mention": m["mention"],
                                 **{k: m[k] for k in ("entity_id", "alignment_status", "start", "end", "relation_role")
                                    if k in m}})
            rec_rows.append(row)
            sid = get_path(rec, "common.source_id", None)
            if sid is not None:
                src = sources.setdefault(sid, {"source_id": sid})
                for p in source_paths:
                    v = get_path(rec, p, None)
                    if v is not None and p not in src:
                        src[p] = _cell(v)
        statements = [{k: _cell(v) for k, v in s.items()} for s in self.statements(records)]
        return {"records": rec_rows, "sources": list(sources.values()), "record_entities": entities,
                "record_links": links, "record_values": values, "statements": statements}

    # ------------------------------------------------------------------ triples
    def triples(self, records: list[dict]) -> list[dict]:
        out: list[dict] = []
        relation_paths = set(self.relation.values())

        def add(s, p, o, kind, rid, **extra):
            out.append({"s": s, "p": p, "o": o, "o_kind": kind, "record_id": rid, **extra})
        for rec in records:
            rid = get_path(rec, "common.record_id", None)
            node, first = f"rec:{rid}", len(out)
            kind = get_path(rec, "common.record_kind", None)
            if kind:
                add(node, "rdf:type", f"bdc:{kind}", "iri", rid)
            for path, v in iter_fields(rec):
                role = self.role.get(path)
                if role in ("record_identity",) or path in relation_paths or path == self.markers_path:
                    continue
                for x in _items(v):
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
            for m in self._markers(rec):  # an aligned mention points at its canonical ID
                if m.get("entity_id") and m.get("entity_type"):
                    add(_ent_iri(m["entity_type"], m["mention"]), "bdc:aligned_to", m["entity_id"],
                        _id_kind(m["entity_id"]), rid)
            s = self.statement(rec)
            if s:
                labelled = {t["s"] for t in out[first:] if t["p"] == "rdfs:label"}
                for end in RELATION_ENDS:  # an end no entity field lists is still a labelled node
                    if s[end] not in labelled and s.get(f"{end}_mention") and s[end].startswith("ent:"):
                        add(s[end], "rdfs:label", s[f"{end}_mention"], "literal", rid)
                        add(s[end], "rdf:type", f"bdc:entity/{s.get(f'{end}_type') or 'entity'}", "iri", rid)
                extra = {k: s[k] for k in ("predicate_status", "predicate_mention", "relation_polarity", "hedge",
                                           "qualifiers", "relation_evidence_type") if k in s}
                add(s["subject"], s["predicate"], s["object"], "iri", rid, statement=s["statement_id"], **extra)
        return out

    # ------------------------------------------------------------------ property graph
    def graph(self, records: list[dict]) -> dict[str, list[dict]]:
        """Entities, records and sources as nodes; statements, mentions, record links and provenance as edges.

        Entity nodes are keyed by type and normalized mention. An aligned ID is a node property, not a merge:
        merging entities is a fusion decision that stays with the consumer."""
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        tables = self.tables(records)

        def node(nid: str, kind: str, **props) -> dict:
            n = nodes.setdefault(nid, {"id": nid, "kind": kind})
            for k, v in props.items():
                if v not in (None, "") and k not in n:
                    n[k] = v
            return n
        for src in tables["sources"]:
            node(src["source_id"], "source", label=src.get("common.source_title") or src["source_id"])
        for rec in records:
            rid = get_path(rec, "common.record_id", None)
            text = next((get_path(rec, p, None) for p in self.assertion_paths if get_path(rec, p, None)), None)
            node(f"rec:{rid}", "record", type=get_path(rec, "common.record_kind", None),
                 label=text if isinstance(text, str) else self._quote(rec))
            sid = get_path(rec, "common.source_id", None)
            if sid is not None:
                edges.append({"s": f"rec:{rid}", "p": "bdc:from_source", "o": sid, "kind": "provenance",
                              "record_id": rid})
        for e in tables["record_entities"]:
            if "mention" not in e:
                continue
            n = node(_ent_iri(e["entity_type"], e["mention"]), "entity", type=e["entity_type"], label=e["mention"],
                     entity_id=e.get("entity_id"))
            n["mentions"] = n.get("mentions", 0) + 1
            edges.append({"s": f"rec:{e['record_id']}", "p": f"bdc:{e['field']}", "o": n["id"], "kind": "mention",
                          "record_id": e["record_id"],
                          **{k: e[k] for k in ("start", "end", "relation_role") if k in e}})
        for link in tables["record_links"]:
            if f"rec:{link['target_record_id']}" not in nodes:  # the target lives in another file
                nodes[f"rec:{link['target_record_id']}"] = {"id": f"rec:{link['target_record_id']}", "kind": "record",
                                                            "external": True}
            edges.append({"s": f"rec:{link['record_id']}", "p": f"bdc:{link['field']}",
                          "o": f"rec:{link['target_record_id']}", "kind": "link", "record_id": link["record_id"],
                          **({"argument_role": link["argument_role"]} if link["argument_role"] else {})})
        for s in self.statements(records):
            for end in RELATION_ENDS:
                node(s[end], "entity", type=s.get(f"{end}_type") or "entity", label=s.get(f"{end}_mention"),
                     entity_id=s.get(f"{end}_id"))
            edges.append({"s": s["subject"], "p": s["predicate"], "o": s["object"], "kind": "statement",
                          "record_id": s["record_id"],
                          **{k: s[k] for k in ("statement_id", "predicate_status", "predicate_mention",
                                               "relation_polarity", "hedge", "qualifiers") if k in s}})
        return {"nodes": list(nodes.values()), "edges": edges}

    # ------------------------------------------------------------------ corpus
    def _chunk_key(self, rec: dict):
        q = self._quote(rec)
        if not q:
            return None
        return (get_path(rec, "common.source_id", None), get_path(rec, "common.source_page", None), normalize_text(q))

    @staticmethod
    def _chunk_id(key) -> str:
        return _digest("chk_", *key)

    def corpus(self, records: list[dict]) -> list[dict]:
        chunks: dict[tuple, dict] = {}
        for rec in records:
            key = self._chunk_key(rec)
            if key is None:
                continue
            q, sid = self._quote(rec), key[0]
            c = chunks.get(key)
            if c is None:
                c = chunks[key] = {"chunk_id": self._chunk_id(key), "chunk_text": q, "source_id": sid,
                                   "chunk_page": key[1], "chunk_section": get_path(rec, "common.source_section", None),
                                   "chunk_support_ids": [], "record_kinds": [], "entities": [], "statement_ids": [],
                                   "leakage_group_id": _digest("lkg_", sid, n=16)}
                for p in ("common.license_id", "common.access_level"):
                    v = get_path(rec, p, None)
                    if v is not None:
                        c[p.split(".")[1]] = v
            c["chunk_support_ids"].append(get_path(rec, "common.record_id", None))
            k = get_path(rec, "common.record_kind", None)
            if k not in c["record_kinds"]:
                c["record_kinds"].append(k)
            for m in self._markers(rec):
                # offsets are stored against the record's own quote; another record may quote the same text
                # with different spacing, so they are re-anchored in the chunk text
                span = (m["start"], m["end"]) if "start" in m and "end" in m and q == c["chunk_text"] \
                    else find_span(c["chunk_text"], m["mention"]) if "start" in m else None
                if not span:
                    continue
                item = {"start": span[0], "end": span[1], "mention": m["mention"],
                        **{k: m[k] for k in ("entity_type", "entity_id", "source_field") if k in m}}
                if item not in c["entities"]:
                    c["entities"].append(item)
            s = self.statement(rec)
            if s and s["statement_id"] not in c["statement_ids"]:
                c["statement_ids"].append(s["statement_id"])
        out = []
        for c in chunks.values():
            c["entities"].sort(key=lambda e: (e["start"], e["end"], e.get("entity_type", "")))
            out.append({k: v for k, v in c.items() if v not in (None, [])})
        return out

    # ------------------------------------------------------------------ QA seeds
    def qa(self, records: list[dict]) -> list[dict]:
        """Cloze seeds from the anchors the records carry: the quote with one answer masked.

        A record that states a relation or makes an assertion yields a seed for each anchored entity (the ends of
        its statement first) and for each numeric statistic or measurement printed in the quote. Other records
        (table cells, methods) yield none; their values are in the relational tables. A seed is a candidate
        (``qa_review_status``): turning it into a natural question is a later, reviewed step."""
        seeds: dict[str, dict] = {}
        for rec in records:
            key = self._chunk_key(rec)
            quote = self._quote(rec)
            if key is None or not isinstance(quote, str):
                continue
            s = self.statement(rec)
            asserts = any(get_path(rec, p, None) for p in self.assertion_paths)
            if not s and not asserts:
                continue
            scope = "; ".join(f"{p.split('.', 1)[1]}={_cell(v)}" for p, v in (s or {}).get("qualifiers", {}).items()) \
                if s else "; ".join(f"{p.split('.', 1)[1]}={_cell(v)}" for p, v in iter_fields(rec)
                                    if self.role.get(p) in QUALIFIER_ROLES)
            answers: list[tuple[int, int, str, str]] = []  # start, end, slot, answer type
            for m in self._markers(rec):
                if "start" in m and "end" in m:
                    answers.append((m["start"], m["end"], m.get("relation_role") or "entity", m.get("entity_type") or "entity"))
            for path, v in iter_fields(rec):
                if self.role.get(path) in VALUE_ROLES and isinstance(v, (int, float)) and not isinstance(v, bool):
                    span = _number_span(quote, v)
                    if span:
                        answers.append((*span, "value", path))
            for start, end, slot, atype in sorted(set(answers)):
                if len(quote) - (end - start) < MIN_CLOZE_CONTEXT:
                    continue
                chunk_id = self._chunk_id(key)
                qid = _digest("qa_", chunk_id, slot, start, end)
                row = seeds.get(qid)
                if row is None:
                    row = seeds[qid] = {
                        "qa_id": qid, "qa_form": "cloze", "qa_slot": slot,
                        "qa_seed_question": quote[:start] + CLOZE_BLANK + quote[end:],
                        "qa_seed_answer": quote[start:end], "answer_type": atype,
                        "answer_start": start, "answer_end": end, "qa_answerable": True,
                        "qa_support_ids": [], "qa_reasoning_path_ids": [],
                        "qa_answer_scope": scope, "qa_difficulty": "single_hop", "qa_review_status": "candidate",
                        "chunk_id": chunk_id, "source_id": key[0], "leakage_group_id": _digest("lkg_", key[0], n=16)}
                    if s and slot in RELATION_ENDS:
                        row["statement"] = {k: s[k] for k in ("subject_mention", "predicate_mention", "predicate",
                                                             "object_mention") if k in s}
                rid = get_path(rec, "common.record_id", None)
                if rid not in row["qa_support_ids"]:
                    row["qa_support_ids"].append(rid)
                if s and s["statement_id"] not in row["qa_reasoning_path_ids"]:
                    row["qa_reasoning_path_ids"].append(s["statement_id"])
        return [{k: v for k, v in row.items() if v not in (None, "", [])} for row in seeds.values()]

    # ------------------------------------------------------------------ all views
    def views(self, records: list[dict]) -> dict:
        return {"tables": self.tables(records), "triples": self.triples(records), "graph": self.graph(records),
                "corpus": self.corpus(records), "qa": self.qa(records)}


def _number_span(text: str, value) -> tuple[int, int] | None:
    """Offsets of a number as printed in ``text``: 23.5 matches "23.5" and "23.50", never "123.5" or "23.51";
    8 never matches the 8 of "8.6", nor 536 the tail of "1,536"."""
    forms = {repr(value), str(value)}
    if isinstance(value, float) and value.is_integer():
        forms.add(str(int(value)))
    for form in sorted(forms, key=len, reverse=True):
        m = re.search(rf"(?<![\d.])(?<!\d,){re.escape(form)}{'0*' if '.' in form else ''}(?!\d|[.,]\d)", text)
        if m:
            return m.start(), m.end()
    return None


def counts(views: dict) -> dict:
    """Row counts of a ``Deriver.views`` result, keyed as in ``<stem>.derive.json``."""
    out = {f"table:{name}": len(rows) for name, rows in views["tables"].items()}
    out.update({"triples": len(views["triples"]), "graph_nodes": len(views["graph"]["nodes"]),
                "graph_edges": len(views["graph"]["edges"]), "statements": len(views["tables"]["statements"]),
                "corpus_chunks": len(views["corpus"]), "qa_seeds": len(views["qa"])})
    return out


def derive_file(path: Path | str, out_dir: Path | str, rc) -> dict:
    """Write <stem>.tables/*.csv, <stem>.triples.jsonl, <stem>.graph.json, <stem>.corpus.jsonl, <stem>.qa.jsonl
    and <stem>.derive.json."""
    path, out_dir = Path(path), Path(out_dir)
    records = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    views = Deriver(rc.contract).views(records)
    stem = path.name[:-6] if path.name.endswith(".jsonl") else path.stem
    tdir = out_dir / f"{stem}.tables"
    tdir.mkdir(parents=True, exist_ok=True)
    for name, rows in views["tables"].items():
        cols: list[str] = []
        for r in rows:
            cols += [k for k in r if k not in cols]
        with (tdir / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols or ["record_id"])
            w.writeheader()
            w.writerows(rows)
    (out_dir / f"{stem}.triples.jsonl").write_text(dumps_jsonl(views["triples"]), encoding="utf-8")
    (out_dir / f"{stem}.graph.json").write_text(dumps_json(views["graph"]), encoding="utf-8")
    (out_dir / f"{stem}.corpus.jsonl").write_text(dumps_jsonl(views["corpus"]), encoding="utf-8")
    (out_dir / f"{stem}.qa.jsonl").write_text(dumps_jsonl(views["qa"]), encoding="utf-8")
    report = {"derive_format": DERIVE_FORMAT, "input": path.name, "contract": rc.identity(),
              "counts": {**counts(views), "records": len(records)}}
    (out_dir / f"{stem}.derive.json").write_text(dumps_json(report), encoding="utf-8")
    return report
