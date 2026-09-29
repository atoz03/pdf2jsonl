"""Load the editable contract sources (catalog, vocabularies, profiles, VERSION) from the working tree."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

from .paths import CATALOG_REL, repo_root
from .util import ContractError, canonical_json, load_json, load_yaml, normalize_version, parse_semver, sha256_text


@dataclass
class Sources:
    root: Path
    version: str
    catalog: dict
    vocabularies: dict[str, dict] = field(default_factory=dict)
    profiles: dict[str, dict] = field(default_factory=dict)
    changelog: str = ""

    def digest(self) -> str:
        """Content hash of everything that defines the contract (not docs, not code)."""
        payload = {"version": self.version, "catalog": self.catalog,
                   "vocabularies": self.vocabularies, "profiles": self.profiles}
        return sha256_text(canonical_json(payload))


def load_sources(root: Path | str | None = None) -> Sources:
    root = repo_root(root)
    version = normalize_version((root / "VERSION").read_text(encoding="utf-8").strip())
    parse_semver(version)
    catalog = load_yaml(root / CATALOG_REL)
    vocabularies = {}
    for p in sorted((root / "vocabularies").glob("*.yaml")):
        doc = load_yaml(p)
        if doc.get("name") != p.stem:
            raise ContractError(f"vocabulary file {p.name} declares name {doc.get('name')!r}")
        vocabularies[p.stem] = doc
    profiles = {}
    for p in sorted((root / "profiles").glob("*.yaml")):
        doc = load_yaml(p)
        if doc.get("name") != p.stem:
            raise ContractError(f"profile file {p.name} declares name {doc.get('name')!r}")
        profiles[p.stem] = doc
    changelog_path = root / "CHANGELOG.md"
    changelog = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
    return Sources(root=root, version=version, catalog=catalog, vocabularies=vocabularies,
                   profiles=profiles, changelog=changelog)


META = {
    "catalog": "field_catalog.meta.schema.json",
    "vocabulary": "vocabulary.meta.schema.json",
    "profile": "profile.meta.schema.json",
    "mapping": "mapping.meta.schema.json",
}


def meta_schema(root: Path, kind: str) -> dict:
    return load_json(root / "schemas/meta" / META[kind])


def meta_validate(src: Sources) -> list[str]:
    """Validate file formats against schemas/meta. Returns human-readable problems."""
    problems: list[str] = []

    def run(kind: str, doc: dict, label: str) -> None:
        v = jsonschema.Draft202012Validator(meta_schema(src.root, kind))
        for e in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path)):
            loc = "/".join(str(x) for x in e.absolute_path) or "<root>"
            problems.append(f"{label}: {loc}: {e.message[:300]}")

    run("catalog", src.catalog, "field_catalog.yaml")
    for name, doc in src.vocabularies.items():
        run("vocabulary", doc, f"vocabularies/{name}.yaml")
    for name, doc in src.profiles.items():
        run("profile", doc, f"profiles/{name}.yaml")
    return problems
