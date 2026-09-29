"""Locate the contract repository on disk."""
from __future__ import annotations

import os
from pathlib import Path

from .util import ContractError

ENV_HOME = "BREEDING_CONTRACT_HOME"
CATALOG_REL = Path("field_catalog/field_catalog.yaml")


def _is_root(p: Path) -> bool:
    return (p / CATALOG_REL).is_file() and (p / "VERSION").is_file()


def repo_root(start: Path | str | None = None) -> Path:
    """Return the repository root.

    Resolution order: explicit ``start`` (or any parent of it), ``$BREEDING_CONTRACT_HOME``,
    then the parents of this module (editable installs / in-repo use).
    """
    candidates: list[Path] = []
    if start is not None:
        candidates.append(Path(start).resolve())
    env = os.environ.get(ENV_HOME)
    if env:
        candidates.append(Path(env).expanduser().resolve())
    candidates.append(Path(__file__).resolve())
    for c in candidates:
        for p in [c, *c.parents]:
            if _is_root(p):
                return p
    raise ContractError(
        "cannot locate the contract repository (field_catalog/field_catalog.yaml + VERSION); "
        f"set ${ENV_HOME} to the repository root")
