"""Repository consistency checks (run by CI via `bdc check --strict`).

Guarantees that field definitions, generated schemas, releases, profiles, examples, mappings and the
pdf2jsonl Skill never drift apart.
"""
from __future__ import annotations

import importlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .compile import compile_contract, field_index, resolve_all_profiles
from .docs_gen import generate_docs
from .release import build_artifacts, changelog_date, load_index, verify_release
from .sources import Sources, load_sources, meta_validate
from .util import ContractError, load_json, load_yaml, parse_semver

SKILL_DIR = Path("skills/pdf2jsonl")


@dataclass
class Finding:
    level: str  # "error" | "warning" | "info"
    check: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} [{self.check}] {self.message}"


def _amb_ids(contract_like: dict) -> set[str]:
    return {a["id"] for a in contract_like["ambiguities"]}


def check_catalog(src: Sources) -> list[Finding]:
    out: list[Finding] = []
    cat = src.catalog
    err = lambda m: out.append(Finding("error", "catalog", m))  # noqa: E731
    amb = _amb_ids(cat)
    seen: set[str] = set()
    paths = [f["path"] for f in cat["fields"]]
    for f in cat["fields"]:
        p = f["path"]
        if p in seen:
            err(f"duplicate field path {p}")
        seen.add(p)
        group = p.split(".")[0]
        if group not in cat["groups"]:
            err(f"{p}: unknown group {group}")
        if f["type"] not in cat["types"]:
            err(f"{p}: unknown type {f['type']}")
        v = f.get("vocabulary")
        if v:
            voc = src.vocabularies.get(v)
            if voc is None:
                err(f"{p}: unknown vocabulary {v}")
            elif voc.get("vocabulary_type") == "unit_conversion":
                err(f"{p}: vocabulary {v} is a unit table, not a code list")
            elif voc.get("applies_to") == "values" and f["type"] != "object_string":
                err(f"{p}: vocabulary {v} applies to map values but field type is {f['type']}")
        for a in f.get("ambiguities") or []:
            if a not in amb:
                err(f"{p}: unknown ambiguity {a}")
        try:
            if parse_semver(f["since"]) > parse_semver(src.version):
                err(f"{p}: since {f['since']} is newer than VERSION {src.version}")
        except ContractError as e:
            err(f"{p}: {e}")
        if f["status"] == "deprecated":
            if "deprecated_in" not in f:
                err(f"{p}: deprecated field needs deprecated_in")
            if f.get("replaced_by") and f["replaced_by"] not in paths:
                err(f"{p}: replaced_by {f['replaced_by']} does not exist")
            if f["required"] == "Y":
                err(f"{p}: a deprecated field cannot be required (Y)")
    for tname, t in cat["types"].items():
        for fp in (t.get("item") or {}).get("from_fields") or []:
            if fp not in seen:
                err(f"type {tname}: item field {fp} does not exist")
        for a in t.get("ambiguities") or []:
            if a not in amb:
                err(f"type {tname}: unknown ambiguity {a}")
    kinds = {v["code"] for v in (src.vocabularies.get("record_kind") or {}).get("values", [])}
    rule_ids = set()
    from .schema_gen import rule_paths
    for r in cat["rules"]:
        if r["id"] in rule_ids:
            err(f"duplicate rule id {r['id']}")
        rule_ids.add(r["id"])
        for p in rule_paths(r):
            if p not in seen:
                err(f"rule {r['id']}: unknown field {p}")
        for a in r.get("ambiguities") or []:
            if a not in amb:
                err(f"rule {r['id']}: unknown ambiguity {a}")
        if r["basis"] == "inferred" and r["severity"] != "warning":
            err(f"rule {r['id']}: inferred rules must be warnings (policy: never enforce inferred semantics)")

        def walk(c: dict) -> None:
            for sub in c.get("all", []) + c.get("any", []):
                walk(sub)
            if c.get("field") == "common.record_kind":
                for k in c.get("in", [c.get("equals")]):
                    if kinds and k not in kinds:
                        err(f"rule {r['id']}: unknown record kind {k}")
        if r.get("when"):
            walk(r["when"])
    for a in cat["contract"].get("ambiguities") or []:
        if a not in amb:
            err(f"contract: unknown ambiguity {a}")
    ids = [a["id"] for a in cat["ambiguities"]]
    if len(ids) != len(set(ids)):
        err("duplicate ambiguity ids")
    for name, voc in src.vocabularies.items():
        for a in voc.get("ambiguities") or []:
            if a not in amb:
                err(f"vocabulary {name}: unknown ambiguity {a}")
        codes = [v["code"] for v in voc.get("values", [])]
        if len(codes) != len(set(codes)):
            err(f"vocabulary {name}: duplicate codes")
        if voc.get("enforcement") == "error" and voc.get("code_status") == "proposed":
            err(f"vocabulary {name}: proposed codes cannot be enforced as error")
    for name, prof in src.profiles.items():
        for a in prof.get("ambiguities") or []:
            if a not in amb:
                err(f"profile {name}: unknown ambiguity {a}")
    return out


def check_profiles(src: Sources) -> list[Finding]:
    out: list[Finding] = []
    try:
        contract = compile_contract(src)
        profiles = resolve_all_profiles(contract, src.profiles)
    except ContractError as e:
        return [Finding("error", "profiles", str(e))]
    vocab = contract["vocabularies"]
    for name, p in profiles.items():
        if not p.get("is_extraction"):
            continue
        for f in p["fields"]:
            if f["role"] == "extract" and f["availability"] in ("G", "F"):
                out.append(Finding("error", "profiles",
                                   f"{name}: {f['path']} ({f['availability']}) exposed for model extraction"))
            if f["role"] == "extract" and f["availability"] == "I":
                out.append(Finding("warning", "profiles",
                                   f"{name}: interpretive field {f['path']} (I) exposed for model extraction"))
            if f["role"] == "generated" and f["availability"] == "F":
                out.append(Finding("error", "profiles", f"{name}: future-source field {f['path']} marked generated"))
        spec = (p.get("system_fields") or {}).get("common.review_status")
        if spec and spec["rule"] == "validation_outcome":
            codes = {v["code"] for v in vocab["review_status"]["values"]}
            for k, code in (spec.get("params") or {}).items():
                if code not in codes:
                    out.append(Finding("error", "profiles", f"{name}: review_status param {k}={code} not in vocabulary"))
    return out


def check_version_and_changelog(src: Sources) -> list[Finding]:
    out: list[Finding] = []
    if not changelog_date(src.changelog, src.version):
        out.append(Finding("error", "version", f"CHANGELOG.md lacks '## [{src.version}] - YYYY-MM-DD'"))
    index = load_index(src.root)
    released = [r["version"] for r in index["releases"]]
    if released:
        latest = max(released, key=parse_semver)
        if parse_semver(src.version) < parse_semver(latest):
            out.append(Finding("error", "version", f"VERSION {src.version} is older than latest release {latest}"))
    return out


def check_releases(src: Sources, strict: bool, for_release: bool) -> list[Finding]:
    out: list[Finding] = []
    root = src.root
    index = load_index(root)
    listed = {r["version"] for r in index["releases"]}
    rdirs = {p.name for p in (root / "releases").iterdir() if p.is_dir()} if (root / "releases").exists() else set()
    for v in sorted(rdirs - listed):
        out.append(Finding("error", "releases", f"releases/{v} exists but is not in index.json"))
    for v in sorted(listed):
        for prob in verify_release(root, v):
            out.append(Finding("error", "releases", prob))
    if listed:
        expect = max((r["version"] for r in index["releases"] if r.get("status", "active") == "active"),
                     key=parse_semver)
        if index.get("latest") != expect:
            out.append(Finding("error", "releases", f"index latest={index.get('latest')} but newest active is {expect}"))
    if for_release:
        return out
    digest = src.digest()
    if src.version in listed:
        meta = load_json(root / "releases" / src.version / "RELEASE.json")
        if meta["source_digest"] != digest:
            out.append(Finding("error", "freshness",
                               f"contract sources changed after release {src.version}; releases are immutable — "
                               "bump VERSION, add a CHANGELOG entry and run `bdc release`"))
        else:
            fresh = build_artifacts(src)
            rdir = root / "releases" / src.version
            for rel, data in fresh.items():
                if not (rdir / rel).exists() or (rdir / rel).read_bytes() != data:
                    out.append(Finding("error", "freshness",
                                       f"releases/{src.version}/{rel} differs from regeneration (generator drift)"))
    else:
        out.append(Finding("error" if strict else "warning", "freshness",
                           f"VERSION {src.version} is not released yet; run `bdc release` "
                           "(the Skill keeps using the previous release until then)"))
    return out


def check_semver(src: Sources) -> list[Finding]:
    """Declared version bumps must be at least as large as the change set requires (docs/versioning.md)."""
    from .compat import LEVELS, declared_bump, required_bump
    out: list[Finding] = []
    root = src.root
    index = load_index(root)
    versions = sorted((r["version"] for r in index["releases"]), key=parse_semver)

    def load(v: str) -> tuple[dict, dict]:
        rdir = root / "releases" / v
        profiles = {p.name.split(".")[0]: None for p in (rdir / "profiles").glob("*.json")}
        return load_json(rdir / "contract.json"), profiles

    pairs = [(a, b, *load(a), *load(b)) for a, b in zip(versions, versions[1:])]
    if versions and src.version not in versions and parse_semver(src.version) > parse_semver(versions[-1]):
        try:
            contract = compile_contract(src)
            pairs.append((versions[-1], src.version, *load(versions[-1]), contract, dict.fromkeys(src.profiles)))
        except ContractError:
            pass
    for a, b, ca, pa, cb, pb in pairs:
        need, reasons = required_bump(ca, cb, pa, pb)
        have = declared_bump(a, b)
        if LEVELS.index(have) < LEVELS.index(need):
            detail = "; ".join(m for lvl, m in reasons if lvl == need)[:600]
            out.append(Finding("error", "semver", f"{a} -> {b} is a {have} bump but the changes require {need}: {detail}"))
    return out


def check_docs(src: Sources) -> list[Finding]:
    out = []
    for rel, text in generate_docs(src).items():
        p = src.root / "docs/generated" / rel
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            out.append(Finding("error", "docs", f"docs/generated/{rel} is stale; run `bdc generate`"))
    return out


def load_invalid_case(root: Path, case: dict) -> dict:
    """Materialise an examples/invalid/cases.yaml case into a record (inline `record`, or `base` + set/unset)."""
    from .util import del_path, set_path
    if "record" in case:
        return case["record"]
    lines = [ln for ln in (root / case["base"]).read_text(encoding="utf-8").splitlines() if ln.strip()]
    rec = json.loads(lines[case.get("line", 1) - 1])
    for path, value in (case.get("set") or {}).items():
        set_path(rec, path, value)
    for path in case.get("unset") or []:
        del_path(rec, path)
    return rec


ENVELOPES = (("*.manifest.json", "manifest"), ("*.validation.json", "validation_report"),
             ("*.bundle.json", "document_bundle"), ("*.migration.json", "migration_report"))


def check_examples(root: Path) -> list[Finding]:
    from .api import declared_version, resolve_schema
    from .runtime_schemas import runtime_errors
    out: list[Finding] = []
    err = lambda m: out.append(Finding("error", "examples", m))  # noqa: E731
    ex = root / "examples"
    record_files = sorted(ex.glob("records/*.jsonl")) + sorted(ex.glob("output/*.jsonl")) + \
        sorted(ex.glob("migration/*/*.migrated.jsonl"))
    for path in record_files:
        if path.name.endswith(".errors.jsonl"):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            rec = json.loads(line)
            try:
                res = resolve_schema(declared_version(rec), root).validator().validate(rec)
            except ContractError as e:
                err(f"{path.relative_to(root)}:{n}: {e}")
                continue
            for i in res.errors:
                err(f"{path.relative_to(root)}:{n}: {i.code} {i.path} {i.message}")
    # runtime envelopes (manifest, validation report, errors, bundles, migration reports)
    for pattern, kind in ENVELOPES:
        for path in sorted(ex.rglob(pattern)):
            for m in runtime_errors(kind, load_json(path), root):
                err(f"{path.relative_to(root)}: {m}")
    for path in sorted(ex.rglob("*.errors.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                for m in runtime_errors("error_record", json.loads(line), root):
                    err(f"{path.relative_to(root)}:{n}: {m}")
    for path in sorted(ex.rglob("*.legacy_v1.json")):
        for d in load_json(path)["documents"]:
            if not d["valid_against_legacy_schema"]:
                err(f"{path.relative_to(root)}: legacy projection invalid: {d['legacy_schema_errors'][:3]}")
    cases_path = ex / "invalid/cases.yaml"
    if cases_path.exists():
        for case in load_yaml(cases_path)["cases"]:
            rc = resolve_schema(case["version"], root)
            res = rc.validator(case.get("profile")).validate(load_invalid_case(root, case))
            codes = {i.code for i in res.errors}
            missing = [c for c in case["expect"] if c not in codes]
            if missing or not codes:
                err(f"invalid case {case['id']}: expected {case['expect']}, got {sorted(codes)}")
    return out


def _load_skill(root: Path):
    scripts = str(root / SKILL_DIR / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    pkg = importlib.import_module("pdf2jsonl_skill")
    rules = importlib.import_module("pdf2jsonl_skill.fill_rules")
    brief = importlib.import_module("pdf2jsonl_skill.brief")
    return pkg, rules, brief


def check_skill(root: Path, src: Sources) -> list[Finding]:
    out: list[Finding] = []
    err = lambda m: out.append(Finding("error", "skill", m))  # noqa: E731
    skill_md = root / SKILL_DIR / "SKILL.md"
    if not skill_md.exists():
        return [Finding("error", "skill", "skills/pdf2jsonl/SKILL.md missing")]
    try:
        pkg, rules, brief = _load_skill(root)
    except Exception as e:  # pragma: no cover - surfaced as a finding
        return [Finding("error", "skill", f"cannot import skill package: {e!r}")]
    implemented = set(rules.IMPLEMENTED_RULES)
    index = load_index(root)
    targets = [(r["version"], load_json(root / "releases" / r["version"] / "contract.json"))
               for r in index["releases"] if r.get("status", "active") == "active"]
    for version, contract in targets:
        major = parse_semver(version)[0]
        if contract["name"] != pkg.SUPPORTED_CONTRACT or major not in pkg.SUPPORTED_MAJORS:
            if version == index.get("latest"):
                err(f"latest release {contract['name']} {version} is outside the Skill's supported range "
                    f"({pkg.SUPPORTED_CONTRACT} majors {pkg.SUPPORTED_MAJORS}) — update the Skill")
            continue
        pdir = root / "releases" / version / "profiles"
        for pf in sorted(pdir.glob("*.json")):
            if pf.name.count(".") != 1:
                continue
            prof = load_json(pf)
            missing = set(prof.get("fill_rules") or []) - implemented
            if missing:
                err(f"{version}/{prof['name']}: fill rules not implemented by the Skill: {sorted(missing)}")
    # working tree (unreleased) profiles must also be supported before they can be released
    try:
        dev = resolve_all_profiles(compile_contract(src), src.profiles)
        for name, prof in dev.items():
            missing = set(prof.get("fill_rules") or []) - implemented
            if missing:
                err(f"working-tree profile {name}: fill rules not implemented by the Skill: {sorted(missing)}")
    except ContractError:
        pass
    # SKILL.md and prompts must not duplicate the catalog: no field paths, no pinned contract versions
    groups = sorted(src.catalog["groups"])
    path_re = re.compile(r"\b(?:" + "|".join(groups) + r")\.[a-z][a-z0-9_]+\b")
    versions = [r["version"] for r in index["releases"]] + [src.version]
    texts = [skill_md] + sorted((root / SKILL_DIR / "prompts").glob("*"))
    for t in texts:
        text = t.read_text(encoding="utf-8")
        hits = sorted(set(path_re.findall(text)))
        if hits:
            err(f"{t.relative_to(root)} hard-codes field paths {hits[:8]}; reference profile roles instead")
        for v in versions:
            if re.search(rf"(?<![\d.]){re.escape(v)}(?!\d|\.\d)", text):
                err(f"{t.relative_to(root)} pins contract version {v}; versions must be resolved at runtime")
        for ph in re.findall(r"\{\{\s*([a-z_]+)\s*\}\}", text):
            if ph not in brief.PLACEHOLDERS:
                err(f"{t.relative_to(root)} uses unknown placeholder {{{{{ph}}}}}")
    # Skill code resolves fields through profile roles and rules; a quoted field path is a hard-coded definition
    literal_re = re.compile(r"[\"'](?:" + "|".join(groups) + r")\.[a-z][a-z0-9_]+[\"']")
    for py in sorted((root / SKILL_DIR / "scripts").rglob("*.py")):
        hits = sorted(set(literal_re.findall(py.read_text(encoding="utf-8"))))
        if hits:
            err(f"{py.relative_to(root)} hard-codes field paths {hits[:8]}; use profile roles/fill rules")
    return out


def check_mappings(root: Path) -> list[Finding]:
    from .mappings import check_all_mappings
    return [Finding(level, "mappings", msg) for level, msg in check_all_mappings(root)]


def run_checks(root: Path | str | None = None, strict: bool = False, for_release: bool = False) -> list[Finding]:
    src = load_sources(root)
    findings = [Finding("error", "meta", m) for m in meta_validate(src)]
    if findings:
        return findings
    findings += check_catalog(src)
    if any(f.level == "error" for f in findings):
        return findings
    findings += check_profiles(src)
    findings += check_version_and_changelog(src)
    findings += check_releases(src, strict, for_release)
    findings += check_semver(src)
    findings += check_skill(src.root, src)
    findings += check_mappings(src.root)
    if not for_release:
        findings += check_docs(src)
        findings += check_examples(src.root)
    return findings


def field_paths(src: Sources) -> list[str]:
    return list(field_index(compile_contract(src)))
