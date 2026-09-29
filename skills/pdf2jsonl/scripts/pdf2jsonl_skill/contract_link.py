"""Link the Skill to the contract repository it lives in.

The Skill never carries field definitions. It imports the repository's ``breeding_contract`` package and
resolves releases from ``releases/``. Resolution order for the repository root:
``$BREEDING_CONTRACT_HOME`` → the repository containing this file (symlinks are followed, so
``~/.claude/skills/pdf2jsonl -> <repo>/skills/pdf2jsonl`` works).
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    env = os.environ.get("BREEDING_CONTRACT_HOME")
    candidates = [Path(env).expanduser().resolve()] if env else []
    candidates.append(Path(__file__).resolve().parents[4])
    for c in candidates:
        if (c / "field_catalog/field_catalog.yaml").is_file() and (c / "releases").is_dir():
            return c
    raise RuntimeError("pdf2jsonl: cannot find the contract repository; set BREEDING_CONTRACT_HOME")


def ensure_contract_importable() -> Path:
    root = repo_root()
    os.environ.setdefault("BREEDING_CONTRACT_HOME", str(root))
    try:
        import breeding_contract  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(root / "src"))
    return root


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
