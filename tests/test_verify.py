"""3.5.0: semantic verification by an independent verifier (AMB-040). It moves review fields, never content."""
from __future__ import annotations

import copy
import json

import pytest

from breeding_contract import ContractError, resolve_schema, validate_record
from breeding_contract.runtime_schemas import runtime_errors
from breeding_contract.util import sha256_file
from breeding_contract.verify import VERDICTS, apply_file, apply_verdicts, build_tasks, tasks_file
from pdf2jsonl_skill.pipeline import RunOptions, run

from conftest import HEAT_CANDIDATES, HEAT_PDF, HEAT_SUPPLEMENT, read_jsonl, records_by_ref, run_bdc

REVIEW_PATHS = {"review_status", "qc_failure_codes", "verification_run_id", "record_version", "record_updated_at"}


@pytest.fixture(scope="module")
def rc(root):
    return resolve_schema("latest", root)


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("verify")
    return run(HEAT_PDF, RunOptions(candidates_file=str(HEAT_CANDIDATES), supplements=[str(HEAT_SUPPLEMENT)],
                                    out_dir=str(out), run_id="run_verify"))


@pytest.fixture(scope="module")
def records(result):
    return read_jsonl(result.outputs["records"])


@pytest.fixture(scope="module")
def by_ref(result):
    return records_by_ref(result, HEAT_CANDIDATES)


@pytest.fixture(scope="module")
def tasks(records, rc):
    return build_tasks(records, rc)


def verdicts(tasks, overrides=None, model="verifier-x", only=None):
    rows = [{"task_id": t["task_id"], "verdict": "supported", **(overrides or {}).get(t["task_id"], {})}
            for t in tasks if only is None or t["task_id"] in only]
    return {"verifier": {"method": "model", "model": model}, "verdicts": rows}


def task_of(tasks, record, kind="record", field=None, target=None):
    return next(t for t in tasks if t["record_id"] == record["common"]["record_id"] and t["kind"] == kind
                and (field is None or t["field"] == field)
                and (target is None or t["target"]["record_id"] == target["common"]["record_id"]))


def status(out, record):
    return next(r for r in out if r["common"]["record_id"] == record["common"]["record_id"])["common"]


# ------------------------------------------------------------------ tasks

def test_one_task_per_record_and_per_link(tasks, records, rc):
    by_kind = {k: [t for t in tasks if t["kind"] == k] for k in ("record", "link")}
    assert len(by_kind["record"]) == 19 and len(by_kind["link"]) == 22  # the two asset records state nothing
    assert len({t["task_id"] for t in tasks}) == len(tasks)
    assert tasks == build_tasks(copy.deepcopy(records), rc)  # task IDs are recomputed from the records


def test_a_record_task_holds_only_what_the_model_filled(tasks, by_ref, rc):
    fields = {f["path"]: f for f in rc.contract["fields"]}
    task = task_of(tasks, by_ref["r_ko"])
    assert task["quote"] == by_ref["r_ko"]["common"]["source_quote"] and task["page"] == 2
    paths = [f["path"] for f in task["fields"]]
    assert "common.germplasm_names" in paths and "agent.statement_role" in paths
    assert all(fields[p]["availability"] == "D" for p in paths)
    # document metadata, identifiers, locators and computed links are not statements of the quote
    assert not {"common.source_title", "common.crop_name", "common.record_id", "common.source_page",
                "skills.method_record_ids", "transform.entity_links"} & set(paths)
    assert all(f["definition"] == fields[f["path"]]["definition_zh"] for f in task["fields"])


def test_a_link_task_shows_both_quotes_and_the_claim(tasks, by_ref):
    task = task_of(tasks, by_ref["m_ko"], "link", "agent.tests_record_ids")
    assert task["edge"] == "tests" and task["meaning"]
    assert task["source"]["quote"] == by_ref["m_ko"]["common"]["source_quote"]
    assert task["target"]["record_id"] == by_ref["h_under"]["common"]["record_id"]
    assert task["target"]["quote"] == by_ref["h_under"]["common"]["source_quote"]
    supplement = task_of(tasks, by_ref["r_ko"], "link", "skills.method_record_ids", by_ref["m_heat"])
    assert supplement["target"]["source_part"] == "supplement" and supplement["target"]["page"] == 1


# ------------------------------------------------------------------ apply

def test_supported_records_are_promoted_and_nothing_else_changes(tasks, records, rc):
    out, report = apply_verdicts(records, verdicts(tasks), rc, "ver_t", extraction_model="example-agent")
    assert report["independent_of_extractor"] is True
    assert report["counts"]["promoted"] == 19 and report["counts"]["no_tasks"] == 2
    assert report["counts"]["review_status_after"] == {"model_verified": 19, "pending_review": 2}
    assert report["findings"] == []
    for before, after in zip(records, out):
        assert validate_record(after).valid
        if before["common"]["record_kind"] == "asset_manifest":
            assert after == before  # nothing to judge: untouched
            continue
        c = after["common"]
        assert c["review_status"] == "model_verified" and c["verification_run_id"] == "ver_t"
        assert c["record_version"] == before["common"]["record_version"] + 1
        assert c["record_id"] == before["common"]["record_id"]
        changed = {g + "." + k for g in after for k in after[g] if after[g][k] != before.get(g, {}).get(k)}
        assert {p.split(".")[1] for p in changed} <= REVIEW_PATHS and all(p.startswith("common.") for p in changed)
        assert {g: [k for k in before[g] if k not in after[g]] for g in before} == {g: [] for g in before}
    assert records[2]["common"]["review_status"] == "auto_validated"  # the input list is not edited


def test_unsupported_value_sends_the_record_back(tasks, records, by_ref, rc):
    t = task_of(tasks, by_ref["r_ko"])
    doc = verdicts(tasks, {t["task_id"]: {"verdict": "not_supported", "unsupported_fields": ["common.germplasm_names"],
                                         "reason": "SL14 is not in this sentence."}})
    out, report = apply_verdicts(records, doc, rc, "ver_t")
    c = status(out, by_ref["r_ko"])
    assert c["review_status"] == "pending_review" and c["qc_failure_codes"] == ["VERIFY_FIELD_NOT_SUPPORTED"]
    assert c["germplasm_names"] == ["SL14"]  # the verifier judges; it does not repair
    assert report["independent_of_extractor"] is None  # no manifest: the extraction model is unknown
    [finding] = report["findings"]
    assert finding == {"task_id": t["task_id"], "record_id": c["record_id"], "kind": "record",
                       "verdict": "not_supported", "unsupported_fields": ["common.germplasm_names"],
                       "reason": "SL14 is not in this sentence."}
    assert report["counts"]["demoted"] == 1 and report["counts"]["promoted"] == 18


def test_a_doubted_link_is_charged_to_the_record_that_makes_it(tasks, records, by_ref, rc):
    link = task_of(tasks, by_ref["m_ko"], "link", "agent.prerequisite_record_ids")
    wrong = task_of(tasks, by_ref["c_up"], "link", "agent.evidence_record_ids", by_ref["r_luc"])
    doc = verdicts(tasks, {link["task_id"]: {"verdict": "uncertain", "reason": "order is not dependency"},
                           wrong["task_id"]: {"verdict": "not_supported", "reason": "an interaction is not an order"}})
    out, report = apply_verdicts(records, doc, rc, "ver_t")
    assert status(out, by_ref["m_ko"])["qc_failure_codes"] == ["VERIFY_UNCERTAIN"]
    assert status(out, by_ref["c_up"])["qc_failure_codes"] == ["VERIFY_LINK_NOT_SUPPORTED"]
    assert status(out, by_ref["a_map"])["review_status"] == "model_verified"   # the target is not blamed
    assert status(out, by_ref["r_luc"])["review_status"] == "model_verified"
    assert {f["target_record_id"] for f in report["findings"]} == \
        {by_ref["a_map"]["common"]["record_id"], by_ref["r_luc"]["common"]["record_id"]}
    kept = next(r for r in out if r["common"]["record_id"] == by_ref["m_ko"]["common"]["record_id"])
    assert kept["agent"]["prerequisite_record_ids"] == by_ref["m_ko"]["agent"]["prerequisite_record_ids"]  # kept


def test_the_extractor_cannot_verify_itself(tasks, records, by_ref, rc):
    t = task_of(tasks, by_ref["r_ko"])
    doc = verdicts(tasks, {t["task_id"]: {"verdict": "not_supported", "reason": "x"}}, model="example-agent")
    out, report = apply_verdicts(records, doc, rc, "ver_t", extraction_model="example-agent")
    assert report["independent_of_extractor"] is False
    assert report["counts"]["promoted"] == 0 and report["counts"]["withheld_same_model"] == 18
    assert "model_verified" not in report["counts"]["review_status_after"]
    assert status(out, by_ref["r_ko"])["review_status"] == "pending_review"  # an objection still counts


def test_partial_coverage_promotes_nothing(tasks, records, by_ref, rc):
    answered = {task_of(tasks, by_ref["r_ko"])["task_id"]}  # its four link tasks are left open
    out, report = apply_verdicts(records, verdicts(tasks, only=answered), rc, "ver_t")
    assert status(out, by_ref["r_ko"])["review_status"] == "auto_validated"
    assert report["counts"]["partially_verified"] == 1 and report["counts"]["unverified"] == 18
    assert status(out, by_ref["bg"]) == by_ref["bg"]["common"]  # unanswered: not even a new version


def test_expert_decisions_are_never_overwritten(tasks, records, by_ref, rc):
    edited = copy.deepcopy(records)
    approved = next(r for r in edited if r["common"]["record_id"] == by_ref["r_ko"]["common"]["record_id"])
    approved["common"]["review_status"] = "expert_approved"
    rejected = next(r for r in edited if r["common"]["record_id"] == by_ref["bg"]["common"]["record_id"])
    rejected["common"]["review_status"] = "rejected"
    t = task_of(tasks, by_ref["r_ko"])
    out, report = apply_verdicts(edited, verdicts(tasks, {t["task_id"]: {"verdict": "not_supported", "reason": "x"}}),
                                 rc, "ver_t")
    assert status(out, by_ref["r_ko"]) == approved["common"] and status(out, by_ref["bg"]) == rejected["common"]
    assert report["counts"]["skipped_expert_reviewed"] == 2 and report["findings"] == []
    assert report["counts"]["review_status_after"]["expert_approved"] == 1
    assert report["counts"]["review_status_after"]["rejected"] == 1


def test_a_later_run_does_not_clear_an_earlier_objection(tasks, records, by_ref, rc):
    t = task_of(tasks, by_ref["r_ko"])
    first, _ = apply_verdicts(records, verdicts(tasks, {t["task_id"]: {"verdict": "uncertain", "reason": "x"}}),
                              rc, "ver_1")
    again = build_tasks(first, rc)
    assert [x["task_id"] for x in again] == [x["task_id"] for x in tasks]  # review fields are not part of a task
    second, report = apply_verdicts(first, verdicts(again, model="verifier-y"), rc, "ver_2")
    c = status(second, by_ref["r_ko"])
    assert c["review_status"] == "pending_review" and c["qc_failure_codes"] == ["VERIFY_UNCERTAIN"]
    assert c["verification_run_id"] == "ver_2" and report["counts"]["confirmed_pending"] == 1
    # a new objection replaces the codes of the earlier run
    third, _ = apply_verdicts(first, verdicts(again, {t["task_id"]: {"verdict": "not_supported", "reason": "y"}}),
                              rc, "ver_3")
    assert status(third, by_ref["r_ko"])["qc_failure_codes"] == ["VERIFY_FIELD_NOT_SUPPORTED"]
    # and a verified record can still be sent back
    promoted, _ = apply_verdicts(records, verdicts(tasks), rc, "ver_4")
    back, _ = apply_verdicts(promoted, verdicts(tasks, {t["task_id"]: {"verdict": "not_supported", "reason": "z"}}),
                             rc, "ver_5")
    assert status(back, by_ref["r_ko"])["review_status"] == "pending_review"


def test_conflicts_and_omissions_are_reported_not_written(tasks, records, by_ref, rc):
    pair = [by_ref["r_sl14"]["common"]["record_id"], by_ref["m_heat"]["common"]["record_id"]]
    doc = {**verdicts(tasks),
           "conflicts": [{"record_ids": pair, "reason": "12 h against 14 h"},
                         {"record_ids": [pair[0], "rec_" + "f" * 32], "reason": "unknown record"},
                         {"record_ids": [pair[0]], "reason": "needs two"}],
           "omissions": [{"page": 2, "source_part": "supplement", "quote": "WY 21.3 %", "note": "control"}]}
    out, report = apply_verdicts(records, doc, rc, "ver_t")
    assert report["conflict_candidates"] == [{"record_ids": pair, "reason": "12 h against 14 h"}]
    assert report["omission_candidates"] == doc["omissions"]
    assert len(out) == len(records)
    assert not any("conflict_record_ids" in r["common"] for r in out)  # a conflict is a reviewer's decision


def test_invalid_input_is_refused(tasks, records, rc, root):
    with pytest.raises(ContractError, match="verdict must be one of"):
        apply_verdicts(records, {"verifier": {"model": "v"}, "verdicts": [{"task_id": tasks[0]["task_id"],
                                                                         "verdict": "fine"}]}, rc, "ver_t")
    with pytest.raises(ContractError, match="verifier.model"):
        apply_verdicts(records, {"verifier": {"method": "model"}, "verdicts": []}, rc, "ver_t")
    with pytest.raises(ContractError, match="expert review"):
        apply_verdicts(records, {"verifier": {"method": "expert", "model": "a person"}, "verdicts": []}, rc, "ver_t")
    with pytest.raises(ContractError, match="has no common.verification_run_id"):
        apply_verdicts(records, verdicts(tasks), resolve_schema("3.4.0", root), "ver_t")
    out, report = apply_verdicts(records, {"verifier": {"model": "v"},
                                           "verdicts": [{"task_id": "vt_unknown", "verdict": "supported"}]}, rc, "ver_t")
    assert report["unknown_task_ids"] == ["vt_unknown"] and out == records
    assert VERDICTS == ("supported", "not_supported", "uncertain")


# ------------------------------------------------------------------ files and CLI

def test_files_round_trip_and_match_the_runtime_schema(result, tmp_path, rc, epoch):
    records_file = result.outputs["records"]
    summary = tasks_file(records_file, tmp_path, rc)
    assert summary["tasks"] == 41 and summary["by_kind"] == {"link": 22, "record": 19}
    stem = records_file.name[:-6]
    doc = json.loads((tmp_path / f"{stem}.verify.tasks.json").read_text())
    assert doc["input"]["sha256"] == sha256_file(records_file) and "not the extractor" in doc["instructions"]
    template = json.loads((tmp_path / f"{stem}.verify.verdicts.template.json").read_text())
    assert template["input_sha256"] == doc["input"]["sha256"] and len(template["verdicts"]) == 2
    answer = tmp_path / "verdicts.json"
    answer.write_text(json.dumps({**verdicts(doc["tasks"]), "input_sha256": doc["input"]["sha256"]}))
    report = apply_file(records_file, answer, tmp_path, rc, manifest=result.outputs["manifest"])
    assert not runtime_errors("verification_report", report)
    assert report["independent_of_extractor"] is True and report["run_id"].startswith("ver_")
    verified = tmp_path / f"{stem}.verified.jsonl"
    assert report["output"] == {"file": verified.name, "sha256": sha256_file(verified)}
    assert json.loads((tmp_path / f"{stem}.verification.json").read_text()) == report
    assert all(validate_record(r).valid for r in read_jsonl(verified))
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({**verdicts(doc["tasks"]), "input_sha256": "0" * 64}))
    with pytest.raises(ContractError, match="another version"):
        apply_file(records_file, stale, tmp_path, rc)


def test_cli_and_checked_in_example(root, tmp_path):
    review = root / "examples/output/review"
    report = json.loads((review / "synthetic_rice_heat.verification.json").read_text())
    assert not runtime_errors("verification_report", report)
    assert report["counts"]["promoted"] == 17 and report["counts"]["demoted"] == 2
    assert {f["verdict"] for f in report["findings"]} == {"not_supported", "uncertain"}
    assert len(report["conflict_candidates"]) == 1 and len(report["omission_candidates"]) == 1
    run_bdc(root, "verify", "tasks", str(root / "examples/output/synthetic_rice_heat.jsonl"), "--out", str(tmp_path))
    assert (tmp_path / "synthetic_rice_heat.verify.tasks.json").read_bytes() == \
        (review / "synthetic_rice_heat.verify.tasks.json").read_bytes()
    run_bdc(root, "verify", "apply", str(root / "examples/output/synthetic_rice_heat.jsonl"),
            str(review / "synthetic_rice_heat.verify.verdicts.json"), "--out", str(tmp_path),
            "--run-id", "ver_example_heat", "--manifest", str(root / "examples/output/synthetic_rice_heat.manifest.json"))
    assert (tmp_path / "synthetic_rice_heat.verified.jsonl").read_bytes() == \
        (review / "synthetic_rice_heat.verified.jsonl").read_bytes()
    verified = read_jsonl(review / "synthetic_rice_heat.verified.jsonl")
    assert {r["common"]["review_status"] for r in verified} == {"model_verified", "pending_review"}


def test_review_status_ladder_is_in_the_vocabulary(rc):
    codes = [v["code"] for v in rc.contract["vocabularies"]["review_status"]["values"]]
    assert codes.index("auto_validated") < codes.index("model_verified") < codes.index("expert_approved")
    evidence = {v["code"] for v in rc.contract["vocabularies"]["relation_evidence_type"]["values"]}
    assert {"genetic_interaction", "localization_imaging", "biochemical_assay", "pharmacological_perturbation"} <= evidence
    assert "source_part_unavailable" in {v["code"] for v in rc.contract["vocabularies"]["missing_reason"]["values"]}
