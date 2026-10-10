"""`bdc` — breeding data contract command line."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .util import ContractError, dumps_json


def _print_findings(findings) -> int:
    for f in findings:
        print(f)
    errors = sum(f.level == "error" for f in findings)
    warnings = sum(f.level == "warning" for f in findings)
    print(f"\n{errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


def cmd_check(args) -> int:
    from .check import run_checks
    return _print_findings(run_checks(args.root, strict=args.strict))


def cmd_generate(args) -> int:
    from .docs_gen import generate_docs, write_docs, write_xlsx
    from .sources import load_sources
    src = load_sources(args.root)
    changed = write_docs(src.root, generate_docs(src))
    print("updated: " + (", ".join(changed) if changed else "(nothing)"))
    if args.xlsx:
        out = write_xlsx(src.root, Path(args.xlsx))
        print(f"wrote {out}")
    return 0


def cmd_release(args) -> int:
    from .docs_gen import generate_docs, write_docs
    from .release import release
    from .sources import load_sources
    version, outcome = release(args.root)
    src = load_sources(args.root)
    write_docs(src.root, generate_docs(src))
    print(f"release {version}: {outcome}")
    return 0


def cmd_resolve(args) -> int:
    from .api import resolve_schema
    rc = resolve_schema(args.schema_version, args.root)
    info = rc.identity()
    info["profiles"] = {}
    for name in rc.profile_names():
        p = rc.profile(name)
        info["profiles"][name] = p["counts"]
    if args.profile:
        p = rc.profile(args.profile)
        info["profile"] = {"name": p["name"], "counts": p["counts"], "fill_rules": p.get("fill_rules"),
                           "record_kinds": p.get("model_record_kinds")}
    print(dumps_json(info), end="")
    return 0


def cmd_validate(args) -> int:
    from .api import resolve_schema
    total = bad = 0
    records = []
    for n, line in enumerate(Path(args.file).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        rec = json.loads(line)
        version = args.schema_version or (rec.get("common") or {}).get("schema_version")
        rc = resolve_schema(version or "latest", args.root)
        res = rc.validator(args.profile).validate(rec)
        records.append((rc, rec))
        if res.issues:
            for i in res.issues:
                if i.severity == "error" or args.warnings:
                    print(f"line {n}: {i.severity:7} {i.code:28} {i.path}: {i.message}")
        bad += not res.valid
    if records:
        rc = records[0][0]
        for idx, issue in rc.validator(args.profile).validate_dataset([r for _, r in records]):
            print(f"line {idx + 1}: {issue.severity:7} {issue.code:28} {issue.path}: {issue.message}")
            bad += issue.severity == "error"
    print(f"{total} record(s), {bad} invalid")
    return 1 if bad else 0


def cmd_diff(args) -> int:
    from .api import resolve_schema
    a, b = resolve_schema(args.old, args.root), resolve_schema(args.new, args.root)
    fa = {f["path"]: f for f in a.fields}
    fb = {f["path"]: f for f in b.fields}
    added = [p for p in fb if p not in fa]
    removed = [p for p in fa if p not in fb]
    changed = []
    for p in fa:
        if p in fb:
            keys = [k for k in ("type", "availability", "required", "definition_zh", "vocabulary", "status",
                                "constraints") if fa[p].get(k) != fb[p].get(k)]
            if keys:
                changed.append((p, keys))
    print(f"# {a.name}: {a.version} -> {b.version}")
    print(f"added {len(added)}, removed {len(removed)}, changed {len(changed)}")
    for p in added:
        print(f"+ {p} ({fb[p]['availability']}/{fb[p]['required']}) {fb[p]['definition_zh']}")
    for p in removed:
        print(f"- {p}")
    for p, keys in changed:
        print(f"~ {p}: {', '.join(keys)}")
    return 0


def cmd_migrate(args) -> int:
    if args.source == "legacy":
        from .legacy import migrate_legacy_file
        report = migrate_legacy_file(Path(args.file), Path(args.out), version=args.schema_version,
                                     page_offset=args.page_offset, dataset_id=args.dataset_id,
                                     source_file_sha256=args.source_file_sha256, root=args.root)
    elif args.source == "merged":
        from .merged import migrate_merged_file
        report = migrate_merged_file(Path(args.file), Path(args.out), version=args.schema_version,
                                     page_offset=args.page_offset, dataset_id=args.dataset_id,
                                     source_file_sha256=args.source_file_sha256, root=args.root)
    else:
        from .omics import migrate_omics_file
        report = migrate_omics_file(Path(args.file), Path(args.out), version=args.schema_version,
                                    record_kind=args.record_kind, dataset_id=args.dataset_id, root=args.root)
    print(dumps_json(report), end="")
    return 0


def cmd_bundle(args) -> int:
    from .bundle import bundle_file
    out = bundle_file(Path(args.file), Path(args.out) if args.out else None, legacy_v1=args.legacy_v1,
                      root=args.root)
    print(f"wrote {out}")
    return 0


def _records_contract(path: Path, version: str | None, root):
    from .api import resolve_schema
    records = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    declared = version or next(((r.get("common") or {}).get("schema_version") for r in records
                                if (r.get("common") or {}).get("schema_version")), None)
    return records, resolve_schema(declared or "latest", root)


def cmd_derive(args) -> int:
    from .derive import derive_file
    _, rc = _records_contract(Path(args.file), args.schema_version, args.root)
    report = derive_file(Path(args.file), Path(args.out), rc)
    print(dumps_json(report), end="")
    return 0


def cmd_audit(args) -> int:
    from .argument import argument_audit
    records, rc = _records_contract(Path(args.file), args.schema_version, args.root)
    audit = argument_audit(records, rc.contract)
    from .workflow import workflow_audit
    workflow = workflow_audit(records, rc.contract)
    if args.json:
        print(dumps_json({**audit, **({"workflow": workflow} if workflow is not None else {})}), end="")
        return 0
    print(f"{audit['statements']} statement(s); links {audit['links']['total']} "
          f"({audit['links']['unresolved']} unresolved) — {audit['basis']}")
    print("element      own  chain")
    for e, c in audit["coverage"].items():
        print(f"{e:12} {c['own']:4} {c['chain']:6}")
    for code, n in audit["flags"].items():
        print(f"flag {code}: {n} — {audit['flag_help'][code]}")
    if workflow is not None:
        print("workflow     " + "  ".join(f"{k}={v}" for k, v in workflow["stages"].items()))
        print("edges        " + ("  ".join(f"{k}={v}" for k, v in workflow["edges_by_type"].items()) or "(none)"))
        for code, n in workflow["flags"].items():
            print(f"flag {code}: {n} — {workflow['flag_help'][code]}")
    return 0


def cmd_verify(args) -> int:
    from .verify import apply_file, tasks_file
    _, rc = _records_contract(Path(args.file), args.schema_version, args.root)
    if args.action == "tasks":
        report = tasks_file(Path(args.file), Path(args.out), rc)
    else:
        if not args.verdicts:
            raise ContractError("bdc verify apply needs the verdicts file: bdc verify apply RECORDS VERDICTS --out DIR")
        report = apply_file(Path(args.file), Path(args.verdicts), Path(args.out), rc, run_id=args.run_id,
                            manifest=args.manifest)
        report = {k: report[k] for k in ("run_id", "verifier", "independent_of_extractor", "counts", "output")}
    print(dumps_json(report), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bdc", description="Breeding data contract tooling")
    ap.add_argument("--root", help="repository root (default: auto-detect / $BREEDING_CONTRACT_HOME)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="run repository consistency checks (CI)")
    p.add_argument("--strict", action="store_true", help="treat an unreleased VERSION as an error")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("generate", help="regenerate docs/generated (field reference, dictionary, rules, vocabularies) from the catalog")
    p.add_argument("--xlsx", metavar="PATH", help="also write an Excel field dictionary (needs openpyxl)")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("release", help="freeze the working-tree contract as releases/<VERSION>")
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("resolve", help="resolve a schema version and print its identity")
    p.add_argument("--schema-version", default="latest")
    p.add_argument("--profile")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("validate", help="validate a JSONL file")
    p.add_argument("file")
    p.add_argument("--schema-version", help="override the version declared by each record")
    p.add_argument("--profile")
    p.add_argument("--warnings", action="store_true", help="also print warnings")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("diff", help="field-level diff between two contract versions")
    p.add_argument("old")
    p.add_argument("new")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("migrate", help="convert legacy/merged documents or omics template instances to atomic records")
    p.add_argument("source", choices=["legacy", "omics", "merged"])
    p.add_argument("file")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--schema-version", default="latest")
    p.add_argument("--page-offset", type=int,
                   help="legacy/merged: physical PDF page = source page - OFFSET (use 0 for physical source pages)")
    p.add_argument("--source-file-sha256", help="legacy/merged: SHA-256 of the source PDF")
    p.add_argument("--record-kind", help="omics only: record kind when the instance has no valid record_type")
    p.add_argument("--dataset-id")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("bundle", help="derive a document_bundle view from atomic records")
    p.add_argument("file")
    p.add_argument("--out")
    p.add_argument("--legacy-v1", action="store_true", help="also project into the legacy v1 document shape")
    p.set_defaults(func=cmd_bundle)

    p = sub.add_parser("derive", help="derive relational tables, statements, KG triples, a property graph, an evidence corpus and QA seeds from records")
    p.add_argument("file")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--schema-version", help="contract version (default: the version the records declare)")
    p.set_defaults(func=cmd_derive)

    p = sub.add_parser("audit", help="evidence-chain audit (Toulmin/Flavell elements, after TRACE) and "
                                     "research-workflow structure")
    p.add_argument("file")
    p.add_argument("--schema-version", help="contract version (default: the version the records declare)")
    p.add_argument("--json", action="store_true", help="print the full audit as JSON")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("verify", help="semantic verification by an independent verifier: write the tasks, then "
                                      "apply its verdicts to the review fields")
    p.add_argument("action", choices=["tasks", "apply"])
    p.add_argument("file", help="records (JSONL)")
    p.add_argument("verdicts", nargs="?", help="apply: the verifier's verdicts file")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--schema-version", help="contract version (default: the version the records declare)")
    p.add_argument("--run-id", help="apply: verification run ID (default: generated)")
    p.add_argument("--manifest", help="apply: the extraction run's manifest; a verifier that is the extraction "
                                      "model promotes nothing")
    p.set_defaults(func=cmd_verify)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ContractError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
