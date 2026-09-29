"""Build, freeze and verify contract releases under releases/<version>/.

A release is an immutable snapshot of generated, machine-consumed artifacts:

    releases/<version>/contract.json                     compiled catalog (fields, rules, vocabularies, ...)
    releases/<version>/record.schema.json                JSON Schema for every record of this version
    releases/<version>/profiles/<name>.json              resolved profile
    releases/<version>/profiles/<name>.schema.json       record schema restricted to the profile
    releases/<version>/profiles/<name>.candidate.schema.json   extraction-backend output format
    releases/<version>/RELEASE.json                      metadata + sha256 of every file above

releases/index.json lists releases and the ``latest`` pointer. Consumers (the pdf2jsonl Skill) load
only from here and verify checksums before use.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import GENERATOR_VERSION
from .compile import compile_contract, resolve_all_profiles
from .schema_gen import candidate_schema, profile_schema, record_schema
from .sources import Sources, load_sources
from .util import ContractError, dumps_json, load_json, parse_semver, sha256_bytes, sha256_file

INDEX_REL = Path("releases/index.json")


def changelog_date(changelog: str, version: str) -> str | None:
    m = re.search(rf"^## \[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})\s*$", changelog, re.M)
    return m.group(1) if m else None


def build_artifacts(src: Sources) -> dict[str, bytes]:
    """All generated release files as {relative path: bytes} (deterministic)."""
    contract = compile_contract(src)
    profiles = resolve_all_profiles(contract, src.profiles)
    files: dict[str, str] = {
        "contract.json": dumps_json(contract),
        "record.schema.json": dumps_json(record_schema(contract)),
    }
    for name, prof in profiles.items():
        files[f"profiles/{name}.json"] = dumps_json(prof)
        files[f"profiles/{name}.schema.json"] = dumps_json(profile_schema(contract, prof))
        if prof.get("is_extraction"):
            files[f"profiles/{name}.candidate.schema.json"] = dumps_json(candidate_schema(contract, prof))
    return {k: v.encode("utf-8") for k, v in sorted(files.items())}


def release_metadata(src: Sources, artifacts: dict[str, bytes], date: str) -> dict:
    return {
        "release_format": 1,
        "contract": src.catalog["contract"]["name"],
        "version": src.version,
        "released_on": date,
        "generator_version": GENERATOR_VERSION,
        "source_digest": src.digest(),
        "files": {rel: sha256_bytes(data) for rel, data in artifacts.items()},
    }


def load_index(root: Path) -> dict:
    p = root / INDEX_REL
    if not p.exists():
        return {"index_format": 1, "contract": None, "latest": None, "releases": []}
    return load_json(p)


def write_index(root: Path, index: dict) -> None:
    index["releases"].sort(key=lambda r: parse_semver(r["version"]))
    active = [r["version"] for r in index["releases"] if r.get("status", "active") == "active"]
    index["latest"] = active[-1] if active else None
    (root / INDEX_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / INDEX_REL).write_text(dumps_json(index), encoding="utf-8")


def release(root: Path | str | None = None, check: bool = True) -> tuple[str, str]:
    """Freeze the working-tree contract as releases/<VERSION>. Returns (version, outcome)."""
    src = load_sources(root)
    root = src.root
    if check:
        from .check import run_checks
        problems = [f for f in run_checks(root, for_release=True) if f.level == "error"]
        if problems:
            raise ContractError("refusing to release; `bdc check` errors:\n" +
                                "\n".join(f"  [{f.check}] {f.message}" for f in problems))
    date = changelog_date(src.changelog, src.version)
    if not date:
        raise ContractError(f"CHANGELOG.md has no '## [{src.version}] - YYYY-MM-DD' entry")
    artifacts = build_artifacts(src)
    meta = release_metadata(src, artifacts, date)
    rdir = root / "releases" / src.version
    index = load_index(root)
    existing = next((r for r in index["releases"] if r["version"] == src.version), None)
    if existing:
        old = load_json(rdir / "RELEASE.json")
        if old["files"] == meta["files"] and old["source_digest"] == meta["source_digest"]:
            return src.version, "unchanged"
        raise ContractError(
            f"release {src.version} already exists with different content; releases are immutable — "
            "bump VERSION (and CHANGELOG) instead")
    for rel, data in artifacts.items():
        p = rdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    meta_bytes = dumps_json(meta).encode("utf-8")
    (rdir / "RELEASE.json").write_bytes(meta_bytes)
    index["contract"] = meta["contract"]
    index["releases"].append({"version": src.version, "released_on": date, "status": "active",
                              "release_sha256": sha256_bytes(meta_bytes)})
    write_index(root, index)
    return src.version, "created"


def verify_release(root: Path, version: str) -> list[str]:
    """Return integrity problems for one release (empty list = trustworthy)."""
    problems = []
    rdir = root / "releases" / version
    meta_path = rdir / "RELEASE.json"
    if not meta_path.exists():
        return [f"releases/{version}/RELEASE.json missing"]
    index = load_index(root)
    entry = next((r for r in index["releases"] if r["version"] == version), None)
    if entry is None:
        problems.append(f"release {version} not listed in releases/index.json")
    elif entry.get("release_sha256") != sha256_file(meta_path):
        problems.append(f"releases/{version}/RELEASE.json does not match its index checksum (tampered?)")
    meta = load_json(meta_path)
    for rel, digest in meta["files"].items():
        p = rdir / rel
        if not p.exists():
            problems.append(f"releases/{version}/{rel} missing")
        elif sha256_file(p) != digest:
            problems.append(f"releases/{version}/{rel} checksum mismatch (released files are immutable)")
    listed = set(meta["files"]) | {"RELEASE.json"}
    for p in rdir.rglob("*"):
        if p.is_file() and p.relative_to(rdir).as_posix() not in listed:
            problems.append(f"releases/{version}/{p.relative_to(rdir).as_posix()} is not part of the release")
    return problems
