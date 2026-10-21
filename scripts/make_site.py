#!/usr/bin/env python3
"""Build the static site (GitHub Pages) from the latest release and the checked-in examples.

    PYTHONPATH=src python scripts/make_site.py [--out _site]

The site is the one place where the repository is shown. Its pages share one shell (site/kit/) and are read in
this order, each linking to the next:

    index.html      home: what the project does, shown on a real sentence of the example paper
    pipeline.html   the pipeline, stage by stage, with the numbers of the example run
    demo.html       walk-through: the synthetic paper from PDF to JSONL (candidates, checks, repairs, rejection,
                    evidence chain, brief, manifest)
    outputs.html    what `bdc derive` builds from the same records: statements, graph, research workflow, corpus,
                    QA seeds, tables, and the derived files under derived/
    papers.html     paper dashboard (scripts/make_dashboard.py) over the papers and runs under PAPER_DIRS
    importers.html  the three importers: mapping coverage, example runs, issue registers
    fields.html     field catalog: definitions, JSON examples, roles, functions, tags
    contract.html   functions and key roles, availability, record kinds with examples, vocabularies, rules,
                    ambiguities, releases

Nothing on a page is hand-written data: fields, profiles, vocabularies and rules come from the resolved
release; examples, mappings and migration reports come from the working tree.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src", ROOT / "skills/pdf2jsonl/scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from breeding_contract.api import available_versions, resolve_schema  # noqa: E402
from breeding_contract.derive import Deriver, counts as derive_counts, derive_file  # noqa: E402
from breeding_contract.functions import source_functions  # noqa: E402
from breeding_contract.schema_gen import rule_paths  # noqa: E402
from breeding_contract.util import load_json, load_yaml, sha256_file  # noqa: E402
from scripts import make_dashboard, site_shell  # noqa: E402

EX = ROOT / "examples"
PAPER = "synthetic_rice_qtl"
# The example whose records state their research workflow (contract 3.5.0), after semantic verification.
WORKFLOW_PAPER = "synthetic_rice_heat"
REPO = "https://github.com/atoz03/pdf2jsonl"
# Where the published paper dashboard looks for PDFs and runs. Local run directories (out/, *.work/) are not
# published; `make dashboard` covers those in an untracked local page.
PAPER_DIRS = ("examples", "papers")
FIELD_KEYS = ("path", "group", "type", "availability", "required", "definition_zh", "data_source_zh",
              "downstream_zh", "since", "status", "maturity", "origin", "vocabulary", "ambiguities", "source_ref",
              "constraints", "key_role", "serves", "card", "argument_role", "notes_zh")
# What the contract page needs of every field to count roles, functions, cards and evidence-chain elements, and to
# list the fields bound to a vocabulary.
SLIM_KEYS = ("path", "group", "availability", "required", "maturity", "key_role", "serves", "card", "argument_role", "vocabulary")
# Importers: `bdc migrate <command>` with its mapping, its checked-in example run and what the input looks like.
IMPORTERS = (
    {"command": "legacy", "mapping": "legacy_to_current", "example": "migration/legacy_v1/breeding_jsonl_example",
     "input": "sources/legacy_v1/breeding_jsonl_example.jsonl", "args": "--page-offset 2220",
     "shape": ("一篇论文一行，实体、关系与证据嵌套在块中", "one paper per line, with nested blocks for entities, relations and evidence")},
    {"command": "omics", "mapping": "omics_to_current", "example": "migration/omics_v2/synthetic_deg_instance",
     "input": "examples/migration/omics_v2/synthetic_deg_instance.json", "args": "",
     "shape": ("每条记录一份多组学元数据模板的填写实例", "one filled instance of the multi-omics metadata template per record")},
    {"command": "merged", "mapping": "merged_to_current", "example": "migration/merged_v2/breeding_jsonl_example_v2",
     "input": "sources/merged_v2/breeding_jsonl_example_v2.json", "args": "--page-offset 2220",
     "shape": ("一篇论文一个文档，加上观测、样本、测定和资产数组，按显式 ID 关联",
               "one paper per document plus observation, sample, assay and asset arrays joined by explicit IDs")},
)
TABLE_PREVIEW_ROWS = 6


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def field_docs(contract: dict) -> tuple[dict, dict, dict]:
    """Documentation examples and tags per field (docs/field_examples.yaml, docs/field_classification.yaml).

    `bdc check` guarantees full coverage for the working-tree contract; the site only shows what exists for
    the fields of the release it renders."""
    examples = load_yaml(ROOT / "docs/field_examples.yaml") or {}
    examples = {**examples, "common.schema_name": contract["name"], "common.schema_version": contract["version"]}
    classification = load_yaml(ROOT / "docs/field_classification.yaml") or {}
    return examples, classification.get("fields") or {}, classification.get("tags") or {}


def site_meta(rc) -> dict:
    """What every page's shell shows: contract name and version, the repository, the field groups."""
    c = rc.contract
    return {"name": c["name"], "version": rc.version, "title_zh": c["title_zh"], "repo": REPO, "groups": list(c["groups"])}


def field_index(contract: dict) -> dict:
    """Field path -> [definition, availability, type]: enough to link and explain a key wherever JSON is shown."""
    return {f["path"]: [f["definition_zh"], f["availability"], f["type"]] for f in contract["fields"]}


def vocabularies(contract: dict) -> list[dict]:
    out = []
    for name, v in sorted(contract["vocabularies"].items()):
        if v.get("vocabulary_type") == "unit_conversion":
            continue
        out.append({"name": name, "title_zh": v.get("title_zh"), "enforcement": v.get("enforcement"),
                    "closure": v.get("closure"), "code_status": v.get("code_status"),
                    "values": [{k: x[k] for k in ("code", "label_zh", "aliases", "cues", "subject_types",
                                                  "object_types") if x.get(k)}
                               for x in v.get("values", [])]})
    return out


def rules(contract: dict) -> list[dict]:
    return [{"id": r["id"], "severity": r["severity"], "basis": r["basis"], "kind": r["kind"],
             "title_zh": r["title_zh"], "fields": rule_paths(r)} for r in contract["rules"]]


def contract_data(rc) -> dict:
    """The field catalog page: every field with its documentation, and what a field's detail links to."""
    c = rc.contract
    profiles = {}
    for name in rc.profile_names():
        p = rc.profile(name)
        profiles[name] = {"title_zh": p.get("title_zh"), "description_zh": p.get("description_zh"),
                          "extends_chain": p.get("extends_chain"),
                          "roles": {f["path"]: f["role"] for f in p["fields"]}}
    examples, tags, tag_defs = field_docs(c)
    fields = []
    for f in c["fields"]:
        row = {k: f[k] for k in FIELD_KEYS if f.get(k) not in (None, [], {})}
        row["serves_src"] = source_functions(c, f)
        if f["path"] in examples:
            row["example"] = examples[f["path"]]
        if tags.get(f["path"]):
            row["tags"] = tags[f["path"]]
        fields.append(row)
    return {
        "name": c["name"], "version": rc.version, "title_zh": c["title_zh"], "baseline_zh": c.get("baseline_zh"),
        "codes": c["codes"], "groups": c["groups"], "record_kinds": c["record_kinds"], "types": c.get("types") or {},
        "fields": fields, "tags": tag_defs, "rules": rules(c), "vocabularies": vocabularies(c),
        "ambiguities": [{k: a.get(k) for k in ("id", "status", "title_zh")} for a in c["ambiguities"]],
        "profiles": profiles,
    }


def reference_data(rc) -> dict:
    """The contract page: codes, groups, record kinds, vocabularies, rules and ambiguities in full, and a slim
    view of the fields to count roles, functions, cards and evidence-chain elements."""
    c = rc.contract
    _, tags, _ = field_docs(c)
    slim = []
    for f in c["fields"]:
        row = {k: f[k] for k in SLIM_KEYS if f.get(k) not in (None, [], {})}
        row["serves_src"] = source_functions(c, f)
        if tags.get(f["path"]):
            row["tags"] = tags[f["path"]]
        slim.append(row)
    profiles = {name: {"title_zh": rc.profile(name).get("title_zh"), "description_zh": rc.profile(name).get("description_zh"),
                       "fields": len(rc.profile(name)["fields"])} for name in rc.profile_names()}
    return {"name": c["name"], "version": rc.version, "title_zh": c["title_zh"], "baseline_zh": c.get("baseline_zh"),
            "codes": c["codes"], "groups": c["groups"], "record_kinds": c["record_kinds"], "fields": slim,
            "rules": rules(c), "vocabularies": vocabularies(c), "ambiguities": c["ambiguities"], "profiles": profiles}


def derived_data(contract: dict, records: list[dict]) -> dict:
    """Function 3 on the demo output: every view `bdc derive` builds, with tables cut to a preview."""
    views = Deriver(contract).views(records)
    tables = {}
    for name, rows in views["tables"].items():
        cols: list[str] = []
        for r in rows:
            cols += [k for k in r if k not in cols]
        tables[name] = {"columns": cols, "rows": rows[:TABLE_PREVIEW_ROWS], "total": len(rows)}
    triples = views["triples"]
    return {
        "counts": derive_counts(views),
        "tables": tables,
        "record_links": views["tables"]["record_links"],
        "statements": Deriver(contract).statements(records),
        "graph": views["graph"],
        "corpus": views["corpus"],
        "qa": views["qa"],
        # one triple per predicate that points at an entity or a record: the edges a reader can check by eye
        "entity_triples": list({t["p"]: t for t in reversed(triples) if t["o_kind"] == "iri" and "statement" not in t
                                and str(t["o"]).startswith(("ent:", "rec:")) and t["s"].startswith("rec:")}.values())[::-1],
    }


def demo_data(out_dir: Path) -> dict:
    """The example run of pdf2jsonl: parsed pages, candidates, records, rejections, report, brief, and the views
    `bdc derive` built from its records (also written to out_dir/derived/ as downloads)."""
    from pdf2jsonl_skill.brief import render_brief
    from pdf2jsonl_skill.pdf_parse import parse_document
    from pdf2jsonl_skill.pipeline import resolve_contract

    out = EX / "output"
    manifest = load_json(out / f"{PAPER}.manifest.json")
    version = manifest["contract"]["schema_version"]
    doc = parse_document(EX / "papers" / f"{PAPER}.pdf")
    rc_demo, profile = resolve_contract(version, "pdf_extraction", False)
    records = jsonl(out / f"{PAPER}.jsonl")
    report = derive_file(out / f"{PAPER}.jsonl", out_dir / "derived", rc_demo)
    files = sorted(p.relative_to(out_dir).as_posix() for p in (out_dir / "derived").rglob("*") if p.is_file())
    # the run's input and output files, published next to the page that walks through them
    run_files = [EX / "papers" / f"{PAPER}{x}" for x in (".pdf", ".candidates.json")]
    run_files += [out / f"{PAPER}{x}" for x in (".jsonl", ".errors.jsonl", ".validation.json", ".manifest.json")]
    for p in run_files:
        (out_dir / p.relative_to(ROOT)).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out_dir / p.relative_to(ROOT))
    return {
        "file_name": f"{PAPER}.pdf",
        "files": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size} for p in run_files],
        "pages": [p.text for p in doc.pages],
        "candidates": load_json(EX / "papers" / f"{PAPER}.candidates.json"),
        "records": records,
        "errors": jsonl(out / f"{PAPER}.errors.jsonl"),
        "validation": load_json(out / f"{PAPER}.validation.json"),
        "manifest": {k: manifest[k] for k in ("run_id", "created_at", "contract", "profile", "input", "backend", "counts")},
        "brief": render_brief(rc_demo, profile, "pages.txt", "candidates.json", "candidate.schema.json"),
        "record_links": profile.get("record_links") or {},
        "relation_roles": {k: v for k, v in ((profile.get("roles") or {}).get("semantic") or {}).items()
                           if k.startswith("relation_")},
        "derived": {**derived_data(rc_demo.contract, records), "files": files, "derive_format": report["derive_format"]},
    }


def workflow_data() -> dict | None:
    """The research workflow of the example paper that states one, from its verified records, and where the
    paper dashboard shows it."""
    review = EX / "output/review" / f"{WORKFLOW_PAPER}.verified.jsonl"
    pdf = EX / "papers" / f"{WORKFLOW_PAPER}.pdf"
    if not review.is_file():
        return None
    records = jsonl(review)
    version = records[0]["common"]["schema_version"]
    workflow = Deriver(resolve_schema(version, ROOT).contract).views(records).get("workflow")
    if not workflow or not workflow.get("nodes"):
        return None
    ids = {n["id"] for n in workflow["nodes"]}
    return {"workflow": workflow, "paper_id": "sha256:" + sha256_file(pdf) if pdf.is_file() else None,
            "title": records[0]["common"].get("source_title"), "file_name": pdf.name,
            "records": [r for r in records if r["common"]["record_id"] in ids]}


def importers(contract: dict) -> list[dict]:
    """The three importers side by side: what each source is, how its leaves map, what its example run gave."""
    origins = (contract.get("codes") or {}).get("origin") or {}
    out = []
    for spec in IMPORTERS:
        mapping = load_yaml(ROOT / "mappings" / f"{spec['mapping']}.yaml")
        report = load_json(EX / f"{spec['example']}.migration.json")
        records = jsonl(EX / f"{spec['example']}.migrated.jsonl")
        errors = jsonl(EX / f"{spec['example']}.migrated.errors.jsonl")
        source = mapping["source"]
        out.append({
            "command": spec["command"], "input": spec["input"], "args": spec["args"],
            "shape_zh": spec["shape"][0], "shape_en": spec["shape"][1],
            "origin": source["id"], "version": source.get("version"),
            "title_zh": source.get("title_zh") or (origins.get(source["id"]) or {}).get("label_zh") or source["id"],
            "mapping_file": f"mappings/{spec['mapping']}.yaml", "mapping_title_zh": mapping.get("title_zh"),
            "source_file": source.get("file"), "principles_zh": mapping.get("principles_zh") or [],
            "status": dict(Counter(e["status"] for e in mapping["entries"])), "leaves": len(mapping["entries"]),
            "targets": len({e["target"] for e in mapping["entries"] if isinstance(e.get("target"), str)}),
            "issues": [{k: i.get(k) for k in ("id", "title_zh", "finding_zh", "resolution_zh") if i.get(k)}
                       for i in mapping.get("issues") or []],
            "fields_added": sum(1 for f in contract["fields"] if (f.get("origin") or [None])[0] == source["id"]),
            "fields_shared": sum(1 for f in contract["fields"] if source["id"] in (f.get("origin") or [])),
            "counts": report["counts"], "contract_version": report["contract"]["schema_version"],
            "by_kind": dict(Counter(r["common"]["record_kind"] for r in records)),
            "rejected_by_code": dict(Counter(e.get("code", "?") for e in errors)),
            "example_dir": (EX / spec["example"]).parent.relative_to(ROOT).as_posix(),
            "sample": next((r for r in records if r["common"]["record_kind"] not in ("input_asset",)), records[0]),
        })
    return out


def gallery() -> list[dict]:
    """One valid record per record kind and way in: curated examples, pdf2jsonl output and each importer."""
    items = []
    for p in sorted((EX / "records").glob("*.jsonl")):
        items.append({"source": "curated", "file": p.relative_to(ROOT).as_posix(), "record": jsonl(p)[0]})
    seen = set()
    sources = [("pdf2jsonl", EX / "output" / f"{PAPER}.jsonl")]
    sources += [(spec["command"], EX / f"{spec['example']}.migrated.jsonl") for spec in IMPORTERS]
    for label, p in sources:
        for r in jsonl(p):
            key = (label, r["common"]["record_kind"])
            if key not in seen:
                seen.add(key)
                items.append({"source": label, "file": p.relative_to(ROOT).as_posix(), "record": r})
    order = list(resolve_schema("latest", ROOT).contract["record_kinds"])
    items.sort(key=lambda x: (order.index(x["record"]["common"]["record_kind"]), x["source"]))
    return items


def release_notes() -> dict:
    """Version -> the opening paragraph of its CHANGELOG.md entry (or its first bullet), as plain text."""
    notes, version, lines = {}, None, []
    for line in [*(ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines(), "## [end]"]:
        m = re.match(r"## \[([^\]]+)\]", line)
        if m:
            if version:
                paras = "\n".join(lines).strip().split("\n\n")
                text = next((p for p in paras if not p.lstrip().startswith("#")), "")
                if not text:
                    text = next((x[2:] for x in lines if x.startswith("- ")), "")
                notes[version] = re.sub(r"\s+", " ", re.sub(r"[`*]", "", text)).strip()
            version, lines = m.group(1), []
        elif version:
            lines.append(line)
    return notes


def versions() -> list[dict]:
    index = load_json(ROOT / "releases/index.json")
    notes = release_notes()
    out = []
    for r in index["releases"]:
        if r["version"] not in available_versions(ROOT):
            continue
        rc = resolve_schema(r["version"], ROOT)
        out.append({"version": r["version"], "released_on": r["released_on"], "fields": len(rc.fields),
                    "rules": len(rc.contract["rules"]), "vocabularies": len(rc.contract["vocabularies"]),
                    "profiles": rc.profile_names(), "latest": r["version"] == index["latest"],
                    "note": notes.get(r["version"], "")})
    return out


def run_numbers(demo: dict) -> dict:
    """The example run in numbers, as the home and pipeline pages tell it."""
    v = demo["validation"]
    audit = v.get("argument_structure") or {}
    return {"pages": len(demo["pages"]), "candidates": v["counts"]["candidates"], "records": v["counts"]["records"],
            "rejected": v["counts"]["rejected"], "repairs": len(v["repairs"]),
            "auto_validated": v["counts"]["by_review_status"].get("auto_validated", 0),
            "pending": v["counts"]["by_review_status"].get("pending_review", 0),
            "system": sum(1 for r in v["records"] if r.get("candidate_index") is None),
            "links": (audit.get("links") or {}).get("total", 0), "statements": audit.get("statements", 0),
            "fields": demo["manifest"]["profile"].get("field_count"), "fill_rules": len(demo["manifest"]["profile"].get("fill_rules") or [])}


def gate_data(demo: dict) -> dict:
    """What each gate of the pipeline caught, for the pipeline page: the example run's repairs, rejections,
    warnings and audit flags, and the semantic verification of the workflow example."""
    v = demo["validation"]
    audit = v.get("argument_structure") or {}
    ver = load_json(EX / "output/review" / f"{WORKFLOW_PAPER}.verification.json")
    status = {r["common"]["record_id"]: r["common"].get("review_status") for r in demo["records"]}
    return {"paper_id": "sha256:" + demo["manifest"]["input"]["sha256"],
            "candidates": [c.get("record_kind") for c in demo["candidates"]["candidates"]],
            "records": [{"id": r["record_id"], "ci": r.get("candidate_index"), "kind": r["record_kind"],
                         "status": status.get(r["record_id"]), "warnings": [w["code"] for w in r.get("warnings") or []]}
                        for r in v["records"]],
            "repairs": v["repairs"], "rejected": v["rejected"],
            "warnings": [{"code": w["code"], "message": w["message"], "record_kind": r["record_kind"]}
                         for r in v["records"] for w in r.get("warnings") or []],
            "flags": audit.get("flags") or {}, "flag_help": audit.get("flag_help") or {},
            "links": audit.get("links") or {}, "by_kind": v["counts"]["by_record_kind"],
            "verification": {"paper": WORKFLOW_PAPER, "paper_id": "sha256:" + sha256_file(EX / "papers" / f"{WORKFLOW_PAPER}.pdf"),
                             "verifier": ver["verifier"], "counts": ver["counts"],
                             "independent": ver["independent_of_extractor"],
                             "conflicts": len(ver["conflict_candidates"]), "omissions": len(ver["omission_candidates"])}}


def hero_data(demo: dict) -> dict:
    """The sentence the home page follows from the paper into every output: the first statement of the example."""
    x = demo["derived"]
    st = x["statements"][0]
    record = next(r for r in demo["records"] if r["common"]["record_id"] == st["record_id"])
    # the page as a reader sees it: the header lines, then sections whose wrapped lines are joined again
    lines = [x.strip() for x in demo["pages"][st["source_page"] - 1].splitlines() if x.strip()]
    head, blocks = lines[:4], []
    for line in lines[4:]:
        if re.fullmatch(r"[A-Z][a-z]+(?: and [A-Z][a-z]+)?", line):
            blocks.append({"h": line, "text": ""})
        elif blocks:
            blocks[-1]["text"] = (blocks[-1]["text"] + " " + line).strip()
    return {"statement": st, "title": record["common"].get("source_title"), "page": st["source_page"],
            "section": record["common"].get("source_section"), "head": head, "blocks": blocks,
            "record": {"common": {k: record["common"][k] for k in ("record_kind", "source_page", "source_quote", "review_status") if k in record["common"]},
                       "agent": {k: v for k, v in (record.get("agent") or {}).items() if k == "pve_percent"},
                       "transform": {k: record["transform"][k] for k in ("subject_mention", "predicate_code", "object_mention") if k in record["transform"]}},
            "qa": next((q for q in x["qa"] if st["record_id"] in q["qa_support_ids"] and q["qa_slot"] == "subject"), x["qa"][0]),
            "chunk": next((c for c in x["corpus"] if st["record_id"] in c["chunk_support_ids"]), None),
            "rejected": demo["errors"][0] if demo["errors"] else None}


def build(out_dir: Path) -> Path:
    rc = resolve_schema("latest", ROOT)
    c = rc.contract
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(out_dir / "derived", ignore_errors=True)
    meta = site_meta(rc)
    _, papers = make_dashboard.build(ROOT, out_dir / "papers.html", scan=[d for d in PAPER_DIRS if (ROOT / d).is_dir()],
                                     site=meta)
    demo = demo_data(out_dir)
    derived = demo.pop("derived")
    run = run_numbers(demo)
    imps = importers(c)
    vers = versions()
    fields = field_index(c)
    stats = {"fields": len(c["fields"]), "verified": sum(1 for f in c["fields"] if f.get("maturity") == "verified"),
             "groups": {g: sum(1 for f in c["fields"] if f["group"] == g) for g in c["groups"]},
             "record_kinds": len(c["record_kinds"]), "vocabularies": len(vocabularies(c)),
             "rules": len(c["rules"]), "rules_error": sum(1 for r in c["rules"] if r["severity"] == "error"),
             "ambiguities": len(c["ambiguities"]), "releases": len(vers), "key_roles": len((c["codes"].get("key_role") or {})),
             "profiles": len(rc.profile_names()), "importers": len(imps)}
    importer_summary = [{"command": i["command"], "leaves": i["leaves"], "records": i["counts"]["records"]} for i in imps]
    pages = {
        "index": {"site": meta, "stats": stats, "run": run, "hero": hero_data({**demo, "derived": derived}),
                  "derived": derived["counts"], "papers": papers["summary"], "importers": importer_summary,
                  "functions": {k: {"label_zh": v.get("label_zh"), "label_en": v.get("label_en"),
                                    "fields": sum(1 for f in c["fields"] if k in (f.get("serves") or []))}
                                for k, v in (c["codes"].get("function") or {}).items()}},
        "pipeline": {"site": meta, "stats": stats, "run": run, "derived": derived["counts"], "papers": papers["summary"],
                     "importers": importer_summary, "tables": len(derived["tables"]), "gates": gate_data(demo)},
        "demo": {"site": meta, "fields": fields, "demo": {**demo, "statements": derived["statements"], "corpus": derived["corpus"]},
                 "run": run, "argument_roles": c["codes"].get("argument_role") or {}},
        "outputs": {"site": meta, "fields": fields, "derived": derived, "records": demo["records"],
                    "candidates": demo["candidates"]["candidates"], "validation_records": demo["validation"]["records"],
                    "relation_roles": demo["relation_roles"], "workflow": workflow_data(),
                    "rules": [r for r in rules(c) if r["id"] in ("R033", "R034")],
                    "hook_condition_fields": sum(1 for f in c["fields"] if f.get("key_role") in ("condition", "context_key"))},
        "importers": {"site": meta, "fields": fields, "importers": imps, "origins": c["codes"].get("origin") or {}},
        "fields": {"site": meta, "contract": contract_data(rc)},
        "contract": {"site": meta, "fields": fields, "contract": reference_data(rc), "gallery": gallery(), "versions": vers,
                     "stats": stats},
    }
    for name, data in pages.items():
        (out_dir / f"{name}.html").write_text(site_shell.render(name, data), encoding="utf-8")
    (out_dir / "assets").mkdir(exist_ok=True)
    for name in ("pipeline.svg", "pipeline.en.svg"):
        shutil.copyfile(ROOT / "docs/diagrams" / name, out_dir / "assets" / name)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    print(build(ap.parse_args().out))
