"""Extraction backends produce a *candidates document* (see profiles/<name>.candidate.schema.json):

    {"extraction": {...}, "document": {<path>: value}, "candidates": [{record_kind, fields, evidence}, ...]}

Backends:
  candidates        read a candidates.json written by an agent (Claude Code) following the generated brief
  mock              deterministic rule-based extractor for tests and smoke runs (extraction_method: rule)
  module:callable   plugin: ``callable(doc, profile, rc, options) -> dict`` (e.g. an LLM API client you own);
                    optional attributes ``extraction_method`` and ``model`` on the callable
Backends never write records: the pipeline verifies evidence, assembles, normalizes and validates.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class Backend:
    name: str
    extraction_method: str
    fn: Callable[..., dict]
    model: str | None = None

    def extract(self, doc, profile: dict, rc, options: dict) -> dict:
        raw = self.fn(doc, profile, rc, options)
        ext = raw.get("extraction") if isinstance(raw, dict) else None
        if isinstance(ext, dict):
            self.model = ext.get("model") or self.model
            if ext.get("method"):
                self.extraction_method = ext["method"]
        return raw

    def info(self) -> dict:
        d = {"name": self.name, "extraction_method": self.extraction_method}
        if self.model:
            d["model"] = self.model
        return d


def _candidates_file(doc, profile, rc, options) -> dict:
    path = options.get("candidates_file")
    if not path:
        raise ValueError("backend 'candidates' needs --candidates FILE")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_backend(spec: str) -> Backend:
    if spec == "candidates":
        return Backend("candidates", "model", _candidates_file)
    if spec == "mock":
        from .mock import extract
        return Backend("mock", "rule", extract, model=None)
    if ":" in spec:
        mod_name, _, attr = spec.partition(":")
        fn: Any = getattr(importlib.import_module(mod_name), attr)
        return Backend(spec, getattr(fn, "extraction_method", "model"), fn, getattr(fn, "model", None))
    raise ValueError(f"unknown backend {spec!r} (use candidates, mock or module:callable)")
