"""3.4.0: the hooks a record carries for its consumers (AMB-038) and the views `bdc derive` builds from them."""
from __future__ import annotations

import copy
import json

import pytest

from breeding_contract import resolve_schema
from breeding_contract.derive import CLOZE_BLANK, Deriver, counts
from breeding_contract.ids import normalize_text
from breeding_contract.relations import find_span, predicate_code, span_matches
from breeding_contract.util import del_path, get_path, set_path
from pdf2jsonl_skill.pipeline import RunOptions, run

from conftest import EXAMPLE_CANDIDATES, EXAMPLE_PDF, read_jsonl, run_skill


@pytest.fixture(scope="module")
def rc(root):
    return resolve_schema("latest", root)


@pytest.fixture(scope="module")
def records(root, tmp_path_factory):
    out = tmp_path_factory.mktemp("hooks")
    opts = RunOptions(backend="candidates", candidates_file=str(EXAMPLE_CANDIDATES), out_dir=str(out), run_id="run_hooks")
    return read_jsonl(run(EXAMPLE_PDF, opts).outputs["records"])


def by_quote(records, text):
    return next(r for r in records if text in (get_path(r, "common.source_quote", None) or ""))


# ------------------------------------------------------------------ anchors

def test_spans_are_literal_and_word_bounded():
    quote = "qPH7.1 was  associated with plant height (PH)."
    assert find_span(quote, "qph7.1") == (0, 6)
    assert quote[slice(*find_span(quote, "associated with"))] == "associated with"
    assert quote[slice(*find_span(quote, "was associated"))] == "was  associated"   # whitespace runs differ
    assert find_span(quote, "PH") == (42, 44)                                       # not the PH inside qPH7.1
    assert find_span(quote, "grain yield") is None and find_span(quote, "") is None
    assert span_matches(quote, "Plant Height", 28, 40) and not span_matches(quote, "plant height", 27, 40)
    assert not span_matches(quote, "PH", 42, 400)


def test_predicate_code_needs_one_cue_and_matching_end_types(rc):
    voc = rc.contract["vocabularies"]["predicate_label"]
    assert predicate_code(voc, "was significantly associated with", ["qtl"], ["trait"]) == "qtl_associated_with_trait"
    assert predicate_code(voc, "was significantly associated with", ["gene"], ["trait"]) == "gene_associated_with_trait"
    assert predicate_code(voc, "was significantly associated with", [], ["trait"]) is None      # untyped subject
    assert predicate_code(voc, "increased", ["qtl"], ["trait"]) is None                          # no cue: stays verbatim
    assert predicate_code(voc, "disassociated without", ["qtl"], ["trait"]) is None              # cue inside a word


def test_pipeline_anchors_the_statement_in_the_quote(records):
    rec = by_quote(records, "explained 23.5%")
    quote, t = rec["common"]["source_quote"], rec["transform"]
    assert (t["subject_mention"], t["predicate_mention"], t["object_mention"]) == \
        ("qPH7.1", "was significantly associated with", "plant height")
    assert quote[t["predicate_start_offset"]:t["predicate_end_offset"]] == t["predicate_mention"]
    assert t["predicate_code"] == "qtl_associated_with_trait" and "predicate_label" not in t   # never the reviewed field
    roles = {m["relation_role"]: m for m in t["entity_links"] if "relation_role" in m}
    assert (roles["subject"]["entity_type"], roles["object"]["entity_type"]) == ("qtl", "trait")
    for r in records:  # every anchor of every record points at its mention
        q = get_path(r, "common.source_quote", None)
        for m in get_path(r, "transform.entity_links", None) or []:
            assert ("start" in m) == ("end" in m)
            if "start" in m:
                assert normalize_text(q[m["start"]:m["end"]]) == normalize_text(m["mention"])


def test_verbatim_predicate_is_kept_when_no_code_fits(records):
    rec = by_quote(records, "increased plant height by 8.6 cm")
    t = rec["transform"]
    assert t["predicate_mention"] == "increased" and "predicate_code" not in t
    subject = next(m for m in t["entity_links"] if m.get("relation_role") == "subject")
    assert subject["mention"] == "The allele from Parent1" and "entity_type" not in subject   # no entity field lists it


def test_records_without_a_statement_still_get_entity_markers(records):
    rec = by_quote(records, "We identified a major QTL")
    assert "subject_mention" not in rec.get("transform", {})
    marker = next(m for m in rec["transform"]["entity_links"] if m["mention"] == "qPH7.1")
    assert (marker["entity_type"], marker["start"], marker["end"]) == ("qtl", 27, 33) and "relation_role" not in marker
    absent = next(m for m in rec["transform"]["entity_links"] if m["mention"] == "plant height")
    assert "start" not in absent   # listed for the record but not printed in this quote


def test_rules_flag_a_missing_predicate_and_a_wrong_offset(rc, records):
    v = rc.validator()
    rec = copy.deepcopy(by_quote(records, "explained 23.5%"))
    codes = lambda r: {i.code for i in v.validate(r).warnings}  # noqa: E731
    assert not {"RULE_R033", "RULE_R034"} & codes(rec)
    shifted = copy.deepcopy(rec)
    shifted["transform"]["predicate_start_offset"] += 1
    assert "RULE_R034" in codes(shifted)
    moved = copy.deepcopy(rec)
    moved["transform"]["entity_links"][0]["end"] += 3
    assert "RULE_R034" in codes(moved)
    for leaf in ("predicate_mention", "predicate_code", "predicate_start_offset", "predicate_end_offset"):
        del_path(rec, f"transform.{leaf}")
    assert "RULE_R033" in codes(rec) and v.validate(rec).valid   # a warning, never a rejection


def test_brief_asks_for_the_statement_and_nothing_computed(root):
    brief = run_skill(root, "brief").stdout
    relations = brief.split("## Relations")[1].split("## Linking candidates")[0]
    for path in ("transform.subject_mention", "transform.predicate_mention", "transform.object_mention"):
        assert f"`{path}`" in relations
    never = brief.split("## Computed by the pipeline")[1]
    for path in ("transform.predicate_code", "transform.predicate_start_offset", "transform.entity_links"):
        assert path in never and path not in relations


# ------------------------------------------------------------------ derived views

def test_statements_report_how_far_the_predicate_was_reviewed(rc, records):
    d = Deriver(rc.contract)
    stmts = {s["subject_mention"] + "|" + s["predicate_mention"]: s for s in d.statements(records)}
    assert {k: s["predicate_status"] for k, s in stmts.items()} == {
        "qPH7.1|was significantly associated with": "lexicon",
        "The allele from Parent1|increased": "verbatim", "qPH7.1|co-localized with": "verbatim"}
    coded = stmts["qPH7.1|was significantly associated with"]
    assert (coded["subject"], coded["predicate"], coded["object"]) == \
        ("ent:qtl/qph7.1", "bdc:qtl_associated_with_trait", "ent:trait/plant_height")
    assert coded["anchors"] == {"subject": [0, 6], "predicate": [54, 87], "object": [88, 100]}
    hedged = stmts["qPH7.1|co-localized with"]
    assert hedged["predicate"] == "bdc:stated_relation" and "requires validation" in hedged["hedge"]

    rec = copy.deepcopy(by_quote(records, "explained 23.5%"))
    set_path(rec, "transform.predicate_label", "gene_associated_with_trait")   # the reviewer overrides the lexicon
    set_path(rec, "common.population_type", "ril")
    reviewed = d.statement(rec)
    assert (reviewed["predicate"], reviewed["predicate_status"]) == ("bdc:gene_associated_with_trait", "reviewed")
    assert reviewed["qualifiers"] == {"common.population_type": "ril"}
    assert reviewed["statement_id"] != coded["statement_id"]                   # another predicate, another statement
    for leaf in ("predicate_label", "predicate_code", "predicate_mention"):
        del_path(rec, f"transform.{leaf}")
    assert d.statement(rec)["predicate"] == "bdc:unlabelled_relation"


def test_graph_is_closed_and_joins_statements_to_entities(rc, records):
    g = Deriver(rc.contract).graph(records)
    ids = {n["id"] for n in g["nodes"]}
    assert len(ids) == len(g["nodes"]) and all(e["s"] in ids and e["o"] in ids for e in g["edges"])
    kinds = {k: sum(e["kind"] == k for e in g["edges"]) for k in ("statement", "mention", "link", "provenance")}
    assert kinds["statement"] == 3 and kinds["link"] == 5 and kinds["provenance"] == len(records)
    qtl = next(n for n in g["nodes"] if n["id"] == "ent:qtl/qph7.1")
    assert (qtl["kind"], qtl["type"], qtl["label"]) == ("entity", "qtl", "qPH7.1")
    assert {e["p"] for e in g["edges"] if e["kind"] == "statement" and e["s"] == qtl["id"]} == \
        {"bdc:qtl_associated_with_trait", "bdc:stated_relation"}


def test_corpus_chunks_are_annotated_sentences(rc, records):
    chunks = Deriver(rc.contract).corpus(records)
    assert len({c["leakage_group_id"] for c in chunks}) == 1          # one paper, one split
    annotated = [c for c in chunks if c.get("entities")]
    assert annotated
    for c in annotated:
        for e in c["entities"]:
            assert normalize_text(c["chunk_text"][e["start"]:e["end"]]) == normalize_text(e["mention"])
    pve = next(c for c in chunks if c["chunk_text"].startswith("qPH7.1 explained"))
    assert [(e["mention"], e["entity_type"]) for e in pve["entities"]] == [("qPH7.1", "qtl"), ("plant height", "trait")]
    assert len(pve["statement_ids"]) == 1


def test_qa_seeds_are_answerable_from_their_chunk(rc, records):
    d = Deriver(rc.contract)
    chunks = {c["chunk_id"]: c for c in d.corpus(records)}
    seeds = d.qa(records)
    assert seeds and len({q["qa_id"] for q in seeds}) == len(seeds)
    fields = {f["path"].split(".", 1)[1] for f in rc.contract["fields"] if f["group"] == "transform"}
    for q in seeds:
        chunk = chunks[q["chunk_id"]]
        assert q["qa_seed_question"].replace(CLOZE_BLANK, q["qa_seed_answer"]) == chunk["chunk_text"]
        assert chunk["chunk_text"][q["answer_start"]:q["answer_end"]] == q["qa_seed_answer"]
        assert set(q["qa_support_ids"]) <= set(chunk["chunk_support_ids"])
        assert q["qa_review_status"] == "candidate" and q["qa_difficulty"] == "single_hop"
        assert {k for k in q if k.startswith("qa_")} - {"qa_form", "qa_slot"} <= fields   # storable as G fields
    slots = {(q["qa_slot"], q["qa_seed_answer"]) for q in seeds}
    assert {("subject", "qPH7.1"), ("object", "plant height"), ("value", "23.5"), ("value", "8.6")} <= slots
    assert not [q for q in seeds if q["qa_seed_question"].startswith("Parent1 118.4")]   # table cells are not cloze items


def test_views_count_what_they_hold(rc, records):
    views = Deriver(rc.contract).views(records)
    c = counts(views)
    assert c["statements"] == c["table:statements"] == 3 and c["qa_seeds"] == len(views["qa"])
    assert c["graph_nodes"] == len(views["graph"]["nodes"]) and c["corpus_chunks"] == len(views["corpus"])
    json.dumps(views)   # every view is plain JSON


def test_older_contracts_derive_without_the_hooks(root, records):
    for version in ("3.0.0", "3.3.0"):
        views = Deriver(resolve_schema(version, root).contract).views(records)
        assert len(views["tables"]["records"]) == len(records) and views["corpus"]
