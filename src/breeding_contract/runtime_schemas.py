"""JSON Schemas for pdf2jsonl / bdc runtime outputs (schemas/runtime/*.schema.json).

Records themselves are validated by the release record schema; these schemas cover the envelopes around them:
manifest, validation report, error records, document_bundle view, migration report and verification report.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from .paths import repo_root
from .util import load_json

RUNTIME_SCHEMAS = {
    "manifest": "manifest.schema.json",
    "validation_report": "validation_report.schema.json",
    "error_record": "error_record.schema.json",
    "document_bundle": "document_bundle.schema.json",
    "migration_report": "migration_report.schema.json",
    "verification_report": "verification_report.schema.json",
}
_BASE = "https://breeding-contract.local/schemas/runtime/"


@lru_cache(maxsize=None)
def _validators(root: str) -> dict[str, jsonschema.Draft202012Validator]:
    sdir = Path(root) / "schemas/runtime"
    resources = [(_BASE + p.name, Resource.from_contents(load_json(p))) for p in sorted(sdir.glob("*.schema.json"))]
    registry = Registry().with_resources(resources)
    return {kind: jsonschema.Draft202012Validator(load_json(sdir / name), registry=registry)
            for kind, name in RUNTIME_SCHEMAS.items()}


def runtime_errors(kind: str, obj, root: Path | str | None = None) -> list[str]:
    """Validation messages for ``obj`` against the runtime schema ``kind`` (empty list = valid)."""
    v = _validators(str(repo_root(root)))[kind]
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:300]}"
            for e in sorted(v.iter_errors(obj), key=lambda e: list(map(str, e.absolute_path)))]
