"""Small shared helpers: IO, hashing, semver and nested-record path access."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterator

import yaml

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.\-]+))?$")
MISSING = object()


class ContractError(Exception):
    """Raised when the repository contract cannot be loaded, resolved or trusted."""


def load_yaml(path: Path | str) -> Any:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dumps_json(obj: Any) -> str:
    """Deterministic, human-readable JSON used for every generated artifact."""
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_version(version: str) -> str:
    v = version.strip()
    if v[:1] in ("v", "V"):
        v = v[1:]
    return v


def parse_semver(version: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(normalize_version(version))
    if not m or m.group(4):
        raise ContractError(f"not a release semantic version: {version!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_release_semver(version: str) -> bool:
    try:
        parse_semver(version)
        return True
    except ContractError:
        return False


def split_path(path: str) -> tuple[str, str]:
    group, _, name = path.partition(".")
    if not group or not name:
        raise ValueError(f"field path must be 'group.field': {path!r}")
    return group, name


def get_path(record: dict, path: str, default: Any = MISSING) -> Any:
    group, name = split_path(path)
    g = record.get(group) if isinstance(record, dict) else None
    if isinstance(g, dict) and name in g:
        return g[name]
    return default


def has_path(record: dict, path: str) -> bool:
    return get_path(record, path) is not MISSING


def set_path(record: dict, path: str, value: Any) -> None:
    group, name = split_path(path)
    record.setdefault(group, {})[name] = value


def del_path(record: dict, path: str) -> None:
    group, name = split_path(path)
    g = record.get(group)
    if isinstance(g, dict):
        g.pop(name, None)
        if not g:
            record.pop(group, None)


def iter_fields(record: dict) -> Iterator[tuple[str, Any]]:
    for group, g in record.items():
        if isinstance(g, dict):
            for name, value in g.items():
                yield f"{group}.{name}", value


def iter_strings(value: Any) -> Iterator[str]:
    """Yield every string contained in a (possibly nested) JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from iter_strings(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from iter_strings(v)


def utc_now() -> _dt.datetime:
    """Current UTC time (seconds); honours SOURCE_DATE_EPOCH for reproducible outputs."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return _dt.datetime.fromtimestamp(int(epoch), tz=_dt.timezone.utc)
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0)
