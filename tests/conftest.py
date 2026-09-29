from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills/pdf2jsonl/scripts"
for p in (ROOT / "src", SKILL_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

EXAMPLE_PDF = ROOT / "examples/papers/synthetic_rice_qtl.pdf"
EXAMPLE_CANDIDATES = ROOT / "examples/papers/synthetic_rice_qtl.candidates.json"
LEGACY_EXAMPLE = ROOT / "sources/legacy_v1/breeding_jsonl_example.jsonl"
LEGACY_PAGE_OFFSET = 2220  # journal pages 2221-2235 -> physical PDF pages 1-15
IGNORE = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.work", "dist", "build", "*.egg-info",
                                "archives", ".git")


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    """A throwaway copy of the repository for tests that edit contract sources or cut releases."""
    dst = tmp_path / "repo"
    shutil.copytree(ROOT, dst, ignore=IGNORE, symlinks=True)
    return dst


@pytest.fixture()
def epoch(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1790000000")


def run_skill(repo: Path, *args: str, env: dict | None = None, check: bool = False) -> subprocess.CompletedProcess:
    """Run the Skill launcher of ``repo`` (the real repo or a copy) with this interpreter."""
    e = {**os.environ, "BDC_PYTHON": sys.executable, "BREEDING_CONTRACT_HOME": str(repo),
         "SOURCE_DATE_EPOCH": "1790000000", **(env or {})}
    e.pop("PDF2JSONL_BACKEND", None)
    e.pop("PYTHONPATH", None)
    return subprocess.run([str(repo / "skills/pdf2jsonl/scripts/pdf2jsonl"), *args], capture_output=True, text=True,
                          env=e, check=check)


def run_bdc(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    e = {**os.environ, "PYTHONPATH": str(repo / "src"), "BREEDING_CONTRACT_HOME": str(repo),
         "SOURCE_DATE_EPOCH": "1790000000"}
    return subprocess.run([sys.executable, "-m", "breeding_contract.cli", "--root", str(repo), *args],
                          capture_output=True, text=True, env=e, check=check, cwd=repo)


def read_jsonl(path: Path) -> list[dict]:
    import json
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
