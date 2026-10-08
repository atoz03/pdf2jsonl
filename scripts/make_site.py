#!/usr/bin/env python3
"""Build the static site (GitHub Pages) from the latest release and the checked-in examples.

    PYTHONPATH=src python scripts/make_site.py [--out _site]

The site is the one place where the repository is shown:

    index.html      contract browser: overview, field catalog (definitions, JSON examples, tags), functions and
                    roles, the PDF -> JSONL walk-through, the downstream outputs built from its records, the
                    importers, record examples, vocabularies, rules
    papers.html     paper dashboard (scripts/make_dashboard.py) over the papers and runs under PAPER_DIRS
    pipeline.html   the pipeline diagram (docs/diagrams/pipeline.html)
    derived/        the files `bdc derive` writes for the example paper, as downloads

Nothing on a page is hand-written data: fields, profiles, vocabularies and rules come from the resolved
release; examples, mappings and migration reports come from the working tree.
"""
from __future__ import annotations

import argparse
import json
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
from breeding_contract.util import load_json, load_yaml  # noqa: E402
from scripts import make_dashboard  # noqa: E402

EX = ROOT / "examples"
PAPER = "synthetic_rice_qtl"
REPO = "https://github.com/atoz03/pdf2jsonl"
# Where the published paper dashboard looks for PDFs and runs. Local run directories (out/, *.work/) are not
# published; `make dashboard` covers those in an untracked local page.
PAPER_DIRS = ("examples", "papers")
FIELD_KEYS = ("path", "group", "type", "availability", "required", "definition_zh", "data_source_zh",
              "downstream_zh", "since", "status", "maturity", "origin", "vocabulary", "ambiguities", "source_ref",
              "constraints", "key_role", "serves", "card", "argument_role", "notes_zh")
# Importers: `bdc migrate <command>` with its mapping, its checked-in example run and what the input looks like.
IMPORTERS = (
    {"command": "legacy", "mapping": "legacy_to_current", "example": "migration/legacy_v1/breeding_jsonl_example",
     "input": "sources/legacy_v1/breeding_jsonl_example.jsonl", "args": "--page-offset 2220",
     "shape": "one paper per line, with nested blocks for entities, relations and evidence"},
    {"command": "omics", "mapping": "omics_to_current", "example": "migration/omics_v2/synthetic_deg_instance",
     "input": "examples/migration/omics_v2/synthetic_deg_instance.json", "args": "",
     "shape": "one filled instance of the multi-omics metadata template per record"},
    {"command": "merged", "mapping": "merged_to_current", "example": "migration/merged_v2/breeding_jsonl_example_v2",
     "input": "sources/merged_v2/breeding_jsonl_example_v2.json", "args": "--page-offset 2220",
     "shape": "one paper per document plus observation, sample, assay and asset arrays joined by explicit IDs"},
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


def contract_data(rc) -> dict:
    c = rc.contract
    vocabs = []
    for name, v in sorted(c["vocabularies"].items()):
        if v.get("vocabulary_type") == "unit_conversion":
            continue
        vocabs.append({"name": name, "title_zh": v.get("title_zh"), "enforcement": v.get("enforcement"),
                       "closure": v.get("closure"), "code_status": v.get("code_status"),
                       "values": [{k: x[k] for k in ("code", "label_zh", "aliases", "cues", "subject_types",
                                                     "object_types") if x.get(k)}
                                  for x in v.get("values", [])]})
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
        "fields": fields, "tags": tag_defs,
        "rules": [{"id": r["id"], "severity": r["severity"], "basis": r["basis"], "kind": r["kind"],
                   "title_zh": r["title_zh"], "fields": rule_paths(r)} for r in c["rules"]],
        "vocabularies": vocabs,
        "ambiguities": c["ambiguities"],
        "profiles": profiles,
    }


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
    files = sorted(str(p.relative_to(out_dir)) for p in (out_dir / "derived").rglob("*") if p.is_file())
    return {
        "file_name": f"{PAPER}.pdf",
        "pages": [p.text for p in doc.pages],
        "candidates": load_json(EX / "papers" / f"{PAPER}.candidates.json"),
        "records": records,
        "errors": jsonl(out / f"{PAPER}.errors.jsonl"),
        "validation": load_json(out / f"{PAPER}.validation.json"),
        "manifest": {k: manifest[k] for k in ("run_id", "contract", "profile", "input", "backend", "counts")},
        "brief": render_brief(rc_demo, profile, "pages.txt", "candidates.json", "candidate.schema.json"),
        "record_links": profile.get("record_links") or {},
        "relation_roles": {k: v for k, v in ((profile.get("roles") or {}).get("semantic") or {}).items()
                           if k.startswith("relation_")},
        "derived": {**derived_data(rc_demo.contract, records), "files": files, "derive_format": report["derive_format"]},
    }


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
            "command": spec["command"], "input": spec["input"], "args": spec["args"], "shape": spec["shape"],
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
            "example_dir": str((EX / spec["example"]).parent.relative_to(ROOT)),
            "sample": next((r for r in records if r["common"]["record_kind"] not in ("input_asset",)), records[0]),
        })
    return out


def gallery() -> list[dict]:
    items = []
    for p in sorted((EX / "records").glob("*.jsonl")):
        items.append({"source": "curated example", "file": str(p.relative_to(ROOT)), "record": jsonl(p)[0]})
    seen = set()
    sources = [("pdf2jsonl output", EX / "output" / f"{PAPER}.jsonl")]
    sources += [(f"{spec['command']} import", EX / f"{spec['example']}.migrated.jsonl") for spec in IMPORTERS]
    for label, p in sources:
        for r in jsonl(p):
            key = (label, r["common"]["record_kind"])
            if key not in seen:
                seen.add(key)
                items.append({"source": label, "file": str(p.relative_to(ROOT)), "record": r})
    order = list(resolve_schema("latest", ROOT).contract["record_kinds"])
    items.sort(key=lambda x: (order.index(x["record"]["common"]["record_kind"]), x["source"]))
    return items


def versions() -> list[dict]:
    index = load_json(ROOT / "releases/index.json")
    out = []
    for r in index["releases"]:
        if r["version"] not in available_versions(ROOT):
            continue
        rc = resolve_schema(r["version"], ROOT)
        out.append({"version": r["version"], "released_on": r["released_on"], "fields": len(rc.fields),
                    "rules": len(rc.contract["rules"]), "vocabularies": len(rc.contract["vocabularies"]),
                    "profiles": rc.profile_names(), "latest": r["version"] == index["latest"]})
    return out


def pipeline_page() -> str:
    """docs/diagrams/pipeline.html with its way back pointing at the site instead of the README."""
    html = (ROOT / "docs/diagrams/pipeline.html").read_text(encoding="utf-8")
    for old, new in (("'../../README.md'", "'index.html'"), ("'../../README.en.md'", "'index.html'"),
                     ('href="../../README.md"', 'href="index.html"'),
                     ("back:'返回 README'", "back:'返回站点'"), ("back:'Back to README'", "back:'Back to the site'"),
                     (">返回 README<", ">返回站点<")):
        if old not in html:
            raise SystemExit(f"docs/diagrams/pipeline.html no longer contains {old!r}; update scripts/make_site.py")
        html = html.replace(old, new)
    return html


def build(out_dir: Path) -> Path:
    rc = resolve_schema("latest", ROOT)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(out_dir / "derived", ignore_errors=True)
    _, papers = make_dashboard.build(ROOT, out_dir / "papers.html", scan=[d for d in PAPER_DIRS if (ROOT / d).is_dir()],
                                     site=True)
    data = {"contract": contract_data(rc), "demo": demo_data(out_dir), "gallery": gallery(), "versions": versions(),
            "importers": importers(rc.contract), "papers": papers["summary"], "repo": REPO}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = (ROOT / "site/index.template.html").read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/null", payload).replace("__VERSION__", rc.version)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "pipeline.html").write_text(pipeline_page(), encoding="utf-8")
    (out_dir / "assets").mkdir(exist_ok=True)
    for name in ("pipeline.svg", "pipeline.en.svg"):
        shutil.copyfile(ROOT / "docs/diagrams" / name, out_dir / "assets" / name)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    print(build(ap.parse_args().out))
