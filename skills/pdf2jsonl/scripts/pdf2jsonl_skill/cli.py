"""pdf2jsonl command line.

    pdf2jsonl paper.pdf --profile pdf_extraction --schema-version latest [--backend agent|candidates|mock|mod:fn]
    pdf2jsonl prepare  paper.pdf [--work-dir W]      # agent mode, step 1: brief + pages + candidate schema
    pdf2jsonl finalize W                             # agent mode, step 2: verify, validate, write outputs
    pdf2jsonl resolve  --schema-version latest --profile pdf_extraction
    pdf2jsonl brief    --schema-version latest --profile pdf_extraction
    pdf2jsonl validate out/paper.jsonl [--schema-version X] [--profile P]
    pdf2jsonl bundle   out/paper.jsonl [-o paper.bundle.json] [--legacy-v1]

Default backend is ``agent`` (or $PDF2JSONL_BACKEND): the first invocation prepares a work directory for the
agent and exits with status 3; after the agent has written ``candidates.json`` the same command finalizes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import PIPELINE_VERSION
from .pipeline import PipelineError, RunOptions, default_work_dir, finalize, prepare, resolve_contract, run

SUBCOMMANDS = {"run", "prepare", "finalize", "resolve", "brief", "validate", "bundle"}
AWAITING_AGENT = 3


def _contract_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile", default="pdf_extraction", help="extraction profile (default: pdf_extraction)")
    p.add_argument("--schema-version", default="latest",
                   help="contract version: latest | MAJOR.MINOR.PATCH | dev (default: latest; the resolved "
                        "version is written into every record and the manifest)")
    p.add_argument("--allow-unreleased", action="store_true",
                   help="permit --schema-version dev (development only; outputs are marked unreleased)")


def _run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", type=Path, help="paper.pdf (or .txt / .pages.jsonl text layer)")
    _contract_args(p)
    p.add_argument("--text-layer", type=Path, help="pre-extracted pages (.pages.jsonl/.txt) for the given PDF")
    p.add_argument("--out-dir", type=Path, help="output directory (default: next to the input)")
    p.add_argument("--dataset-id")
    p.add_argument("--dataset-version")
    p.add_argument("--source-asset-id")
    p.add_argument("--asset-uri", help="persistent URI of the PDF asset (no local paths)")
    p.add_argument("--run-id")


def _opts(a: argparse.Namespace, **kw) -> RunOptions:
    return RunOptions(profile=a.profile, schema_version=a.schema_version,
                      out_dir=str(a.out_dir) if getattr(a, "out_dir", None) else None,
                      text_layer=str(a.text_layer) if getattr(a, "text_layer", None) else None,
                      dataset_id=getattr(a, "dataset_id", None), dataset_version=getattr(a, "dataset_version", None),
                      source_asset_id=getattr(a, "source_asset_id", None), asset_uri=getattr(a, "asset_uri", None),
                      run_id=getattr(a, "run_id", None), allow_unreleased=a.allow_unreleased,
                      bundle=getattr(a, "bundle", False), **kw)


def _summary(result, fail_on_reject: bool) -> int:
    c = result.counts
    m = result.manifest
    print(f"contract  {m['contract']['schema_name']} {m['contract']['schema_version']} "
          f"({m['contract']['release_status']}, requested {m['contract']['requested']})")
    print(f"profile   {m['profile']['name']}   backend {m['backend']['name']} ({m['backend']['extraction_method']})")
    print(f"records   {c['records']} accepted  {c['rejected']} rejected  of {c['candidates']} candidates "
          f"({c['pages']} pages)")
    if c["by_review_status"]:
        print("review    " + "  ".join(f"{k}={v}" for k, v in c["by_review_status"].items()))
    if c["rejected_by_code"]:
        print("rejected  " + "  ".join(f"{k}={v}" for k, v in c["rejected_by_code"].items()))
    for k, p in result.outputs.items():
        print(f"{k:<9} {p}")
    return 2 if fail_on_reject and c["rejected"] else 0


def cmd_run(a) -> int:
    backend = a.backend or ("candidates" if a.candidates else os.environ.get("PDF2JSONL_BACKEND", "agent"))
    if backend == "agent":
        work = a.work_dir or default_work_dir(a.input, _opts(a))
        req, cand = work / "request.json", work / "candidates.json"
        if req.is_file() and cand.is_file():
            pinned = json.loads(req.read_text(encoding="utf-8"))
            if pinned["profile"] != a.profile:
                raise PipelineError(f"{work} was prepared for profile {pinned['profile']}, not {a.profile}")
            return _summary(finalize(work, _opts(a), requested_version=a.schema_version), a.fail_on_reject)
        work = prepare(a.input, _opts(a), work)
        _agent_instructions(work)
        return AWAITING_AGENT
    result = run(a.input, _opts(a, backend=backend, candidates_file=str(a.candidates) if a.candidates else None))
    return _summary(result, a.fail_on_reject)


def _agent_instructions(work: Path) -> None:
    print(f"prepared  {work}")
    print(f"  1. read  {work / 'brief.md'} and {work / 'pages.txt'}")
    print(f"  2. write {work / 'candidates.json'} (schema: {work / 'candidate.schema.json'})")
    print(f"  3. run   the same command again, or: pdf2jsonl finalize {work}")


def cmd_prepare(a) -> int:
    work = prepare(a.input, _opts(a), a.work_dir)
    _agent_instructions(work)
    return 0


def cmd_finalize(a) -> int:
    o = RunOptions(out_dir=str(a.out_dir) if a.out_dir else None, run_id=a.run_id, bundle=a.bundle)
    return _summary(finalize(a.work_dir, o), a.fail_on_reject)


def cmd_resolve(a) -> int:
    rc, profile = resolve_contract(a.schema_version, a.profile, a.allow_unreleased)
    out = {**rc.identity(), "profile": profile["name"], "extends_chain": profile["extends_chain"],
           "counts": profile["counts"], "record_kinds": profile.get("model_record_kinds"),
           "fill_rules": profile["fill_rules"], "pipeline_version": PIPELINE_VERSION}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_brief(a) -> int:
    from .brief import render_brief
    rc, profile = resolve_contract(a.schema_version, a.profile, a.allow_unreleased)
    sys.stdout.write(render_brief(rc, profile, "pages.txt", "candidates.json", "candidate.schema.json"))
    return 0


def cmd_validate(a) -> int:
    from breeding_contract import declared_version, resolve_schema, validate_record
    records, bad_json = [], 0
    for n, line in enumerate(a.file.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append((n, json.loads(line)))
        except json.JSONDecodeError as e:
            print(f"line {n}: invalid JSON: {e}")
            bad_json += 1
    errors = warnings = 0
    versions = set()
    for n, rec in records:
        version = a.schema_version or declared_version(rec)
        versions.add(version)
        try:
            res = validate_record(rec, version, a.profile)
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"line {n}: {e}")
            errors += 1
            continue
        for i in res.issues:
            if i.severity == "error" or a.verbose:
                print(f"line {n}: [{i.severity}] {i.code} {i.path}: {i.message}")
        errors += len(res.errors)
        warnings += len(res.warnings)
    if len(versions) == 1 and None not in versions:
        v = versions.pop()
        dataset = resolve_schema(v).validator(a.profile).validate_dataset([r for _, r in records])
        for idx, i in dataset:
            print(f"line {records[idx][0]}: [{i.severity}] {i.code} {i.path}: {i.message}")
            errors += i.severity == "error"
    print(f"{len(records)} records, {errors + bad_json} errors, {warnings} warnings")
    return 1 if errors or bad_json else 0


def cmd_bundle(a) -> int:
    from breeding_contract.bundle import bundle_file
    out = bundle_file(a.file, a.output, legacy_v1=a.legacy_v1)
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pdf2jsonl", description="PDF -> atomic JSONL under a versioned data contract")
    ap.add_argument("--version", action="version", version=f"pdf2jsonl {PIPELINE_VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="extract (default subcommand)")
    _run_args(p)
    p.add_argument("--backend", help="agent (default) | candidates | mock | module:callable")
    p.add_argument("--candidates", type=Path, help="candidates.json (implies --backend candidates)")
    p.add_argument("--work-dir", type=Path, help="agent work directory (default: <out-dir>/<stem>.work)")
    p.add_argument("--bundle", action="store_true", help="also write <stem>.bundle.json (document_bundle view)")
    p.add_argument("--fail-on-reject", action="store_true", help="exit 2 when any candidate was rejected")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("prepare", help="agent mode: write brief, pages, candidate schema, request")
    _run_args(p)
    p.add_argument("--work-dir", type=Path)
    p.set_defaults(fn=cmd_prepare)

    p = sub.add_parser("finalize", help="agent mode: turn candidates.json into validated outputs")
    p.add_argument("work_dir", type=Path)
    p.add_argument("--out-dir", type=Path)
    p.add_argument("--run-id")
    p.add_argument("--bundle", action="store_true")
    p.add_argument("--fail-on-reject", action="store_true")
    p.set_defaults(fn=cmd_finalize)

    p = sub.add_parser("resolve", help="show the resolved contract version and profile")
    _contract_args(p)
    p.set_defaults(fn=cmd_resolve)

    p = sub.add_parser("brief", help="print the extraction brief for a version/profile")
    _contract_args(p)
    p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("validate", help="validate a JSONL file against the version each record declares")
    p.add_argument("file", type=Path)
    p.add_argument("--schema-version", help="override the declared version")
    p.add_argument("--profile")
    p.add_argument("-v", "--verbose", action="store_true", help="also print warnings")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("bundle", help="derive the document_bundle view from records")
    p.add_argument("file", type=Path)
    p.add_argument("-o", "--output", type=Path)
    p.add_argument("--legacy-v1", action="store_true", help="emit the legacy v1 document layout instead")
    p.set_defaults(fn=cmd_bundle)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "run")
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except PipelineError as e:
        print(f"pdf2jsonl: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
