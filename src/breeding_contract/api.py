"""Stable programmatic interface used by the pdf2jsonl Skill and any other consumer.

    resolve_schema(version)                -> ResolvedContract
    load_profile(profile_name, version)    -> resolved profile dict
    load_field_catalog(version)            -> compiled contract dict (fields, rules, vocabularies, ...)
    validate_record(record, version, profile) -> ValidationResult

``version`` accepts ``"latest"``, an explicit release (``"3.1.0"`` or ``"v3.1.0"``) or ``"dev"``
(compile the working tree in memory; marked unreleased and refused for production).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from .compile import compile_contract, resolve_all_profiles
from .paths import repo_root
from .release import load_index, verify_release
from .schema_gen import candidate_schema, profile_schema, record_schema
from .sources import load_sources
from .util import ContractError, get_path, is_release_semver, load_json, normalize_version, parse_semver, sha256_file
from .validate import ValidationResult, Validator

DEV = "dev"
LATEST = "latest"


class ResolvedContract:
    """One resolved contract version with lazy access to its artifacts."""

    def __init__(self, root: Path, version: str, status: str, files: dict[str, Any],
                 release_sha256: str | None, requested: str):
        self.root = root
        self.version = version
        self.status = status  # "released" | "unreleased"
        self.requested = requested
        self.release_sha256 = release_sha256
        self._files = files
        self._validators: dict[str | None, Validator] = {}

    # ----------------------------------------------------------------- artifacts
    def _get(self, rel: str) -> Any:
        if rel not in self._files:
            raise ContractError(f"{self.name} {self.version}: artifact {rel} not found")
        return self._files[rel]

    @property
    def contract(self) -> dict:
        return self._get("contract.json")

    @property
    def name(self) -> str:
        return self._get("contract.json")["name"]

    @property
    def fields(self) -> list[dict]:
        return self.contract["fields"]

    def field(self, path: str) -> dict:
        for f in self.fields:
            if f["path"] == path:
                return f
        raise KeyError(path)

    def record_schema(self) -> dict:
        return self._get("record.schema.json")

    def profile_names(self) -> list[str]:
        return sorted(r.split("/")[1][:-5] for r in self._files
                      if r.startswith("profiles/") and r.count(".") == 1)

    def profile(self, name: str) -> dict:
        if f"profiles/{name}.json" not in self._files:
            raise ContractError(f"profile {name!r} does not exist in {self.name} {self.version} "
                                f"(available: {', '.join(self.profile_names())})")
        return self._get(f"profiles/{name}.json")

    def profile_schema(self, name: str) -> dict:
        return self._get(f"profiles/{name}.schema.json")

    def candidate_schema(self, name: str) -> dict:
        return self._get(f"profiles/{name}.candidate.schema.json")

    def validator(self, profile: str | None = None) -> Validator:
        if profile not in self._validators:
            if profile:
                self._validators[profile] = Validator(self.contract, self.profile(profile),
                                                      schema=self.profile_schema(profile))
            else:
                self._validators[None] = Validator(self.contract, schema=self.record_schema())
        return self._validators[profile]

    def identity(self) -> dict:
        """What production outputs must record about the contract they follow."""
        return {"schema_name": self.name, "schema_version": self.version, "release_status": self.status,
                "requested": self.requested, "release_sha256": self.release_sha256,
                "source_digest": self.contract["source_digest"]}


def available_versions(root: Path | str | None = None) -> list[str]:
    root = repo_root(root)
    index = load_index(root)
    return [r["version"] for r in index["releases"] if r.get("status", "active") == "active"]


def resolve_version(requested: str, root: Path | str | None = None) -> str:
    root = repo_root(root)
    req = (requested or LATEST).strip()
    if req.lower() == LATEST:
        latest = load_index(root).get("latest")
        if not latest:
            raise ContractError("no released contract version exists yet (run `bdc release`)")
        return latest
    if req.lower() == DEV:
        return DEV
    v = normalize_version(req)
    if not is_release_semver(v):
        raise ContractError(f"invalid schema version {requested!r}: use 'latest', 'dev' or MAJOR.MINOR.PATCH")
    known = {r["version"]: r for r in load_index(root)["releases"]}
    if v not in known:
        raise ContractError(f"schema version {v} is not released (available: {', '.join(known) or 'none'})")
    if known[v].get("status", "active") != "active":
        raise ContractError(f"schema version {v} is {known[v]['status']}")
    return v


@lru_cache(maxsize=32)
def _load_release(root_str: str, version: str, verify: bool) -> ResolvedContract:
    root = Path(root_str)
    if verify:
        problems = verify_release(root, version)
        if problems:
            raise ContractError("release integrity check failed:\n  " + "\n  ".join(problems))
    rdir = root / "releases" / version
    meta = load_json(rdir / "RELEASE.json")
    files = {rel: load_json(rdir / rel) for rel in meta["files"]}
    return ResolvedContract(root, version, "released", files, sha256_file(rdir / "RELEASE.json"), version)


def _load_dev(root: Path) -> ResolvedContract:
    src = load_sources(root)
    digest = src.digest()
    index = load_index(root)
    if any(r["version"] == src.version for r in index["releases"]):
        meta = load_json(root / "releases" / src.version / "RELEASE.json")
        if meta["source_digest"] == digest:
            rc = _load_release(str(root), src.version, True)
            return ResolvedContract(root, rc.version, rc.status, rc._files, rc.release_sha256, DEV)
    # Stamp an unreleased version into every artifact so records can never claim a released version.
    dev_version = f"{src.version}-dev.{digest[:8]}"
    contract = compile_contract(src)
    contract["version"] = dev_version
    profiles = resolve_all_profiles(contract, src.profiles)
    files = {"contract.json": contract, "record.schema.json": record_schema(contract)}
    for name, prof in profiles.items():
        files[f"profiles/{name}.json"] = prof
        files[f"profiles/{name}.schema.json"] = profile_schema(contract, prof)
        if prof.get("is_extraction"):
            files[f"profiles/{name}.candidate.schema.json"] = candidate_schema(contract, prof)
    return ResolvedContract(root, dev_version, "unreleased", files, None, DEV)


def resolve_schema(version: str = LATEST, root: Path | str | None = None, verify: bool = True) -> ResolvedContract:
    root = repo_root(root)
    v = resolve_version(version, root)
    if v == DEV:
        return _load_dev(root)
    rc = _load_release(str(root), v, verify)
    if rc.requested != version:
        return ResolvedContract(rc.root, rc.version, rc.status, rc._files, rc.release_sha256, version)
    return rc


def load_profile(profile_name: str, version: str = LATEST, root: Path | str | None = None) -> dict:
    return resolve_schema(version, root).profile(profile_name)


def load_field_catalog(version: str = LATEST, root: Path | str | None = None) -> dict:
    return resolve_schema(version, root).contract


VERSION_FIELD = "common.schema_version"  # contract identity field (catalog: record carries its schema version)


def declared_version(record: Any) -> str | None:
    """The contract version a record declares, or None."""
    v = get_path(record, VERSION_FIELD, None) if isinstance(record, dict) else None
    return v if isinstance(v, str) else None


def validate_record(record: dict, version: str | None = None, profile: str | None = None,
                    root: Path | str | None = None) -> ValidationResult:
    """Validate against ``version`` or, if omitted, the version the record itself declares."""
    if version is None:
        version = declared_version(record)
        if version is None:
            raise ContractError(f"record does not declare {VERSION_FIELD}; pass version=")
    return resolve_schema(version, root).validator(profile).validate(record)


def latest_version_tuple(root: Path | str | None = None) -> tuple[int, int, int]:
    return parse_semver(resolve_version(LATEST, root))
