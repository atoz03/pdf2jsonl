"""3.2.0: key roles and functions, candidate links, the evidence-chain audit, derived views and robustness fixes."""
from __future__ import annotations

import copy
import json
import math

import pytest

from breeding_contract import resolve_schema
from breeding_contract.argument import argument_audit
from breeding_contract.bundle import document_fields, entity_fields
from breeding_contract.check import check_field_functions
from breeding_contract.derive import Deriver
from breeding_contract.functions import added_functions, field_facets, source_functions
from breeding_contract.omics import migrate_omics_file
from breeding_contract.util import dumps_json, get_path, load_yaml, set_path
from pdf2jsonl_skill.pipeline import RunOptions, run

from conftest import EXAMPLE_CANDIDATES, EXAMPLE_PDF, read_jsonl, run_bdc, run_skill


@pytest.fixture(scope="module")
def rc(root):
    return resolve_schema("latest", root)


@pytest.fixture(scope="module")
def example(root, tmp_path_factory):
    out = tmp_path_factory.mktemp("example")
    opts = RunOptions(backend="candidates", candidates_file=str(EXAMPLE_CANDIDATES), out_dir=str(out),
                      run_id="run_chain")
    res = run(EXAMPLE_PDF, opts)
    return {"records": read_jsonl(res.outputs["records"]),
            "report": json.loads(res.outputs["validation"].read_text())}


def by_quote(records, text):
    hits = [r for r in records if text in (get_path(r, "common.source_quote", None) or "")]
    assert len(hits) >= 1, text
    return hits


def run_candidates(tmp_path, candidates, name="c.json"):
    raw = json.loads(EXAMPLE_CANDIDATES.read_text())
    raw["candidates"] = candidates
    path = tmp_path / name
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    res = run(EXAMPLE_PDF, RunOptions(backend="candidates", candidates_file=str(path), out_dir=str(tmp_path / name[:-5]),
                                      run_id="run_small"))
    return res, json.loads(res.outputs["validation"].read_text())


# ------------------------------------------------------------------ key roles and functions

def test_every_field_states_its_role_and_functions(rc):
    codes = rc.contract["codes"]
    for f in rc.contract["fields"]:
        assert f["key_role"] in codes["key_role"], f["path"]
        assert f["serves"] and set(f["serves"]) <= set(codes["function"]), f["path"]
        for fn, facets in field_facets(rc.contract, f).items():
            assert facets, (f["path"], fn)


def test_source_functions_match_labels_longest_first(root):
    cat = load_yaml(root / "field_catalog/field_catalog.yaml")
    probe = {"path": "common.x", "downstream_zh": "全部转化"}
    assert source_functions(cat, probe) == ["derivation"]  # 全部转化 is not 全部
    probe["downstream_zh"] = "全部"
    assert source_functions(cat, probe) == ["topic2", "topic3", "derivation", "iteration"]
    probe["downstream_zh"] = "课题二、图谱"
    assert source_functions(cat, probe) == ["topic2", "derivation"]
    assert source_functions(cat, {"path": "agent.x", "downstream_zh": "图谱"}) == ["topic2", "derivation"]  # group
    assert source_functions(cat, {"path": "common.x"}) == []  # repository field: no source statement


def test_source_stated_functions_and_cards_cannot_be_dropped(root):
    cat = load_yaml(root / "field_catalog/field_catalog.yaml")
    assert not [f for f in check_field_functions(cat) if f.level == "error"]
    f = next(x for x in cat["fields"] if source_functions(cat, x) and len(x["serves"]) > 1)
    dropped = source_functions(cat, f)[0]
    f["serves"] = [s for s in f["serves"] if s != dropped]
    carded = next(x for x in cat["fields"] if x.get("card"))
    carded["card"] = next(c for c in cat["codes"]["card"] if c != carded["card"])
    msgs = [x.message for x in check_field_functions(cat) if x.level == "error"]
    assert any(f["path"] in m and "drops source-stated" in m for m in msgs)
    assert any(carded["path"] in m and "card must be" in m for m in msgs)


def test_added_functions_are_kept_apart_from_source_functions(rc):
    for f in rc.contract["fields"]:
        added = added_functions(rc.contract, f)
        assert set(added).isdisjoint(source_functions(rc.contract, f))
        assert set(added) | set(source_functions(rc.contract, f)) == set(f["serves"])


# ------------------------------------------------------------------ candidate links

def test_links_become_record_ids(example):
    recs = example["records"]
    icim = by_quote(recs, "QTL IciMapping version 4.2")[0]["common"]["record_id"]
    lod = by_quote(recs, "LOD score of 12.8")[0]
    assert lod["skills"]["method_record_ids"] == [icim]
    pve = by_quote(recs, "explained 23.5%")[0]
    assert pve["agent"]["evidence_record_ids"] == [lod["common"]["record_id"]]


def test_link_to_a_rejected_candidate_stays_unresolved_and_needs_review(example):
    rec = by_quote(example["records"], "promising target for marker-assisted")[0]
    pve = by_quote(example["records"], "explained 23.5%")[0]["common"]["record_id"]
    assert rec["agent"]["evidence_record_ids"] == [pve]  # c_fake was rejected; nothing is invented for it
    assert rec["common"]["review_status"] == "pending_review"
    row = next(r for r in example["report"]["records"] if r["record_id"] == rec["common"]["record_id"])
    assert [(w["code"], w["detail"]["ref"]) for w in row["warnings"]] == [("CANDIDATE_LINK_UNRESOLVED", "c_fake")]


def test_link_edge_cases_are_warned(tmp_path):
    q_icim = "QTL analysis was performed with QTL IciMapping version 4.2 using inclusive composite interval mapping."
    q_lod = "qPH7.1 was located between markers S7_1203 and S7_1377 with a LOD score of 12.8."
    cands = [
        {"record_kind": "method", "ref": "m", "fields": {"skills.software_name": "QTL IciMapping"},
         "evidence": {"page": 2, "quote": q_icim}},
        {"record_kind": "analysis_result", "ref": "a", "links": {"method": ["a", "c"], "unknown": ["m"]},
         "fields": {"agent.lod_score": 12.8}, "evidence": {"page": 3, "quote": q_lod}},
        {"record_kind": "claim", "ref": "c", "fields": {"agent.finding_text": q_lod},
         "evidence": {"page": 3, "quote": q_lod}},
        {"record_kind": "claim", "ref": "c", "fields": {"agent.finding_text": q_icim},
         "evidence": {"page": 2, "quote": q_icim}},
    ]
    res, report = run_candidates(tmp_path, cands)
    codes = {w["code"] for r in report["records"] for w in r["warnings"]}
    assert {"CANDIDATE_LINK_SELF", "CANDIDATE_LINK_KIND", "CANDIDATE_REF_DUPLICATE"} <= codes
    lod = next(r for r in res.records if r["common"]["record_kind"] == "analysis_result")
    assert "method_record_ids" not in lod.get("skills", {})  # neither itself nor a claim is a method
    assert "unknown" not in json.dumps(lod)  # link names outside the profile are dropped


def test_record_ids_do_not_depend_on_candidate_order_or_section(tmp_path, example):
    raw = json.loads(EXAMPLE_CANDIDATES.read_text())
    shuffled = list(reversed(copy.deepcopy(raw["candidates"])))
    for c in shuffled:
        ev = c.get("evidence") or {}
        if isinstance(ev.get("section"), str):
            ev["section"] = ev["section"].upper()
    res, _ = run_candidates(tmp_path, shuffled)
    ids = lambda recs: sorted(r["common"]["record_id"] for r in recs)  # noqa: E731
    assert ids(res.records) == ids(example["records"])
    links = lambda recs: sorted(json.dumps([r["common"]["record_id"], r.get("agent", {}).get("evidence_record_ids"),  # noqa: E731
                                            r.get("skills", {}).get("method_record_ids")]) for r in recs)
    assert links(res.records) == links(example["records"])


def test_malformed_candidates_are_rejected_or_repaired(tmp_path):
    q = "qPH7.1 was located between markers S7_1203 and S7_1377 with a LOD score of 12.8."
    cands = [
        {"record_kind": 7, "fields": {"agent.lod_score": 12.8}, "evidence": {"page": 3, "quote": q}},
        {"record_kind": "analysis_result", "fields": {"agent.lod_score": 12.8}, "evidence": {"page": 3, "quote": {"t": q}}},
        {"record_kind": "analysis_result", "fields": {"agent.lod_score": float("nan"), "common.qtl_names": ["qPH7.1"]},
         "evidence": {"page": 3, "quote": q}},
        {"record_kind": "analysis_result", "fields": {"common.marker_names": ["S7_1203"]},
         "evidence": {"page": 3, "quote": 12.8, "row_key": 7}},
    ]
    res, report = run_candidates(tmp_path, cands)
    assert {e["candidate_index"] for e in report["rejected"]} == {0, 1}
    assert len(res.records) == 3  # candidates 2 and 3 (+ asset manifest)
    nan = next(r for r in res.records if r.get("common", {}).get("qtl_names") == ["qPH7.1"])
    assert "lod_score" not in nan.get("agent", {})
    log = {(r["where"], r["action"], r.get("key")) for r in report["repairs"]}
    assert ("candidates[1]", "dropped_malformed_evidence_value", "evidence.quote") in log
    assert ("candidates[2]", "dropped_non_finite_number", "agent.lod_score") in log
    assert {("candidates[3]", "coerced_type", "evidence.quote"), ("candidates[3]", "coerced_type", "evidence.row_key")} <= log


# ------------------------------------------------------------------ validation and rules

def test_non_finite_numbers_are_errors_and_never_written(rc, example):
    rec = copy.deepcopy(by_quote(example["records"], "LOD score of 12.8")[0])
    rec["agent"]["lod_score"] = math.inf
    assert "VALUE_NOT_FINITE" in {i.code for i in rc.validator().validate(rec).errors}
    with pytest.raises(ValueError):
        dumps_json(rec)


def test_evidence_references_must_resolve(rc, example):
    recs = copy.deepcopy(example["records"])
    v = rc.validator()
    assert not [i for _, i in v.validate_dataset(recs) if i.code == "RULE_R031"]
    lod = next(r for r in recs if get_path(r, "agent.lod_score", None) is not None)
    set_path(lod, "skills.method_record_ids", ["rec_00000000000000000000000000000000"])
    hits = [i for _, i in v.validate_dataset(recs) if i.code == "RULE_R031"]
    assert hits and hits[0].severity == "warning" and hits[0].detail["unresolved"] == ["rec_" + "0" * 32]


def test_hedged_claim_should_keep_its_qualifier(rc, example):
    rec = copy.deepcopy(by_quote(example["records"], "requires validation")[0])
    v = rc.validator()
    assert rec["agent"]["claim_qualifier_text"]
    assert not [i for i in v.validate(rec).warnings if i.code == "RULE_R032"]
    del rec["agent"]["claim_qualifier_text"]
    assert [i.severity for i in v.validate(rec).warnings if i.code == "RULE_R032"] == ["warning"]
    plain = by_quote(example["records"], "increased plant height by 8.6 cm")[0]
    assert not [i for i in v.validate(plain).warnings if i.code == "RULE_R032"]


# ------------------------------------------------------------------ evidence-chain audit

def test_audit_in_report_follows_links(example):
    a = example["report"]["argument_structure"]
    assert a["links"] == {"total": 5, "unresolved": 0}
    rows = {r["record_id"]: r for r in a["records"]}
    pve = by_quote(example["records"], "explained 23.5%")[0]["common"]["record_id"]
    assert "warrant" not in rows[pve]["elements"] and "warrant" in rows[pve]["chain_elements"]  # via LOD -> ICIM
    effect = by_quote(example["records"], "increased plant height by 8.6 cm")[0]["common"]["record_id"]
    assert rows[effect]["flags"] == ["NO_WARRANT"]
    assert "score" not in json.dumps(a)


def test_audit_flags(rc, example):
    recs = copy.deepcopy(example["records"])
    hedged = by_quote(recs, "requires validation")[0]
    del hedged["agent"]["claim_qualifier_text"]
    final = by_quote(recs, "promising target")[0]
    final["agent"]["evidence_record_ids"] += [hedged["common"]["record_id"], "rec_missing"]
    a = argument_audit(recs, rc.contract)
    rows = {r["record_id"]: r for r in a["records"]}
    assert "QUALIFIER_NOT_CAPTURED" in rows[hedged["common"]["record_id"]]["flags"]
    assert {"HEDGED_STATEMENT_USED_AS_DATA", "UNRESOLVED_LINK"} <= set(rows[final["common"]["record_id"]]["flags"])
    assert a["links"]["unresolved"] == 1 and set(a["flag_help"]) == set(a["flags"])


def test_scope_qualifiers_are_not_hedges(rc, example):
    recs = copy.deepcopy(example["records"])
    pve = by_quote(recs, "explained 23.5%")[0]
    pve["agent"]["applicable_environment"] = "both environments"
    a = argument_audit(recs, rc.contract)
    final = by_quote(recs, "promising target")[0]["common"]["record_id"]
    assert "HEDGED_STATEMENT_USED_AS_DATA" not in next(r for r in a["records"] if r["record_id"] == final).get("flags", [])


# ------------------------------------------------------------------ derived views (function 3)

def test_tables_are_lossless_for_links_and_entities(rc, example):
    recs = example["records"]
    t = Deriver(rc.contract).tables(recs)
    assert len(t["records"]) == len(recs) and len(t["sources"]) == 1
    n_links = sum(len(get_path(r, p, None) or []) for r in recs
                  for p in ("agent.evidence_record_ids", "skills.method_record_ids"))
    assert len(t["record_links"]) == n_links
    roles = {row["argument_role"] for row in t["record_links"]}
    assert roles == {"data", "warrant"}
    genes = {(e["record_id"], e["mention"]) for e in t["record_entities"] if e["field"] == "common.qtl_names"}
    assert genes == {(r["common"]["record_id"], q) for r in recs for q in r["common"].get("qtl_names", [])}


def test_triples_join_statements_to_typed_entities(rc, example):
    triples = Deriver(rc.contract).triples(example["records"])
    stmt = [t for t in triples if "statement" in t]
    assert ("ent:qtl/qph7.1", "bdc:qtl_associated_with_trait", "ent:trait/plant_height") in \
        {(t["s"], t["p"], t["o"]) for t in stmt}
    kinds = {t["p"]: t["o_kind"] for t in triples}
    assert kinds["bdc:common.source_doi"] == "id" and kinds["bdc:common.source_id"] == "iri"
    assert kinds["bdc:common.source_type"] == "literal"
    assert any(t["p"] == "bdc:skills.method_record_ids" and t["o"].startswith("rec:rec_") for t in triples)


def test_corpus_chunks_cite_every_quoted_record(rc, example):
    recs = example["records"]
    chunks = Deriver(rc.contract).corpus(recs)
    cited = [i for c in chunks for i in c["chunk_support_ids"]]
    quoted = [r["common"]["record_id"] for r in recs if r["common"].get("source_quote")]
    assert sorted(cited) == sorted(quoted)
    table2 = next(c for c in chunks if c["chunk_text"].startswith("Parent1 118.4"))
    assert len(table2["chunk_support_ids"]) == 2  # one table row, two cells


def test_cli_derive_and_audit(root, tmp_path, example):
    src = tmp_path / "in.jsonl"
    src.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in example["records"]), encoding="utf-8")
    d = run_bdc(root, "derive", str(src), "--out", str(tmp_path / "d"))
    counts = json.loads(d.stdout)["counts"]
    assert counts["records"] == len(example["records"]) and counts["table:record_links"] == 5
    for name in ("records", "sources", "record_entities", "record_links", "record_values", "statements"):
        assert (tmp_path / f"d/in.tables/{name}.csv").is_file()
    for name in ("triples.jsonl", "graph.json", "corpus.jsonl", "qa.jsonl", "derive.json"):
        assert (tmp_path / f"d/in.{name}").is_file()
    assert counts["statements"] == 3 and counts["qa_seeds"] == len(read_jsonl(tmp_path / "d/in.qa.jsonl"))
    a = json.loads(run_bdc(root, "audit", str(src), "--json").stdout)
    assert a["statements"] == example["report"]["argument_structure"]["statements"]


# ------------------------------------------------------------------ catalog-driven consumers

def test_bundle_field_lists_come_from_key_roles(rc):
    docs, ents = document_fields(rc.contract), entity_fields(rc.contract)
    assert {"common.source_title", "common.source_doi", "common.source_journal", "common.crop_name"} <= set(docs)
    assert {"common.gene_names", "common.qtl_names", "common.germplasm_names"} <= set(ents)
    assert "common.source_quote" not in docs and "common.source_page" not in docs


def test_brief_explains_links_and_evidence_chain(root):
    r = run_skill(root, "brief")
    assert r.returncode == 0, r.stderr
    assert "links.evidence" in r.stdout and "agent.evidence_record_ids" in r.stdout
    assert "agent.claim_qualifier_text" in r.stdout and "{{" not in r.stdout


def test_omics_instances_without_id_are_identified_by_content(root, tmp_path):
    inst = json.loads((root / "examples/migration/omics_v2/synthetic_deg_instance.json").read_text())
    del inst["basic_identity"]["record_id"]
    other = copy.deepcopy(inst)
    other["basic_identity"]["data_accession"] = "EXAMPLE-ACC-0002"
    path = tmp_path / "two.json"
    path.write_text(json.dumps([inst, other, inst]), encoding="utf-8")
    migrate_omics_file(path, tmp_path / "out", root=root)
    recs = read_jsonl(tmp_path / "out/two.migrated.jsonl")
    errors = read_jsonl(tmp_path / "out/two.migrated.errors.jsonl")
    assert len({r["common"]["record_id"] for r in recs}) == len(recs) == 2
    assert [(e["code"], e["instance"]) for e in errors] == [("DATASET_RULE", 3)]  # the exact duplicate
