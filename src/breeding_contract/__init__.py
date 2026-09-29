"""breeding_contract — the data contract for atomic breeding-literature JSONL records.

The repository owns the contract (field_catalog/field_catalog.yaml + vocabularies + profiles);
this package compiles, releases, resolves and validates it. Public API:

    resolve_schema(version="latest")          -> ResolvedContract
    load_profile(profile_name, version)       -> dict
    load_field_catalog(version)               -> dict
    validate_record(record, version, profile) -> ValidationResult
"""
GENERATOR_VERSION = "1.0.0"

from .api import (  # noqa: E402
    ResolvedContract,
    available_versions,
    declared_version,
    load_field_catalog,
    load_profile,
    resolve_schema,
    resolve_version,
    validate_record,
)
from .util import ContractError  # noqa: E402
from .validate import ValidationResult, Validator  # noqa: E402

__all__ = [
    "GENERATOR_VERSION", "ContractError", "ResolvedContract", "ValidationResult", "Validator",
    "available_versions", "declared_version", "load_field_catalog", "load_profile", "resolve_schema", "resolve_version",
    "validate_record",
]
