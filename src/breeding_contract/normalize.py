"""Deterministic normalization of raw values using the repository unit table (vocabularies/units.yaml).

Invariant: normalization only *adds* normalized_* values; it never modifies the raw expression.
Anything that cannot be converted deterministically is left un-normalized with a reason code
(v3 rule 4: 无法换算时不强行标准化).
"""
from __future__ import annotations

import re
import unicodedata

NUM = r"[-+]?\d+(?:\.\d+)?"
_SINGLE = re.compile(rf"^{NUM}$")
_RANGE = re.compile(rf"^({NUM})\s*(?:-|–|—|~|～|to)\s*({NUM})$")
_THOUSANDS = re.compile(r"^[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")


def _clean(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw).strip()
    return s.replace("−", "-")


def parse_raw_value(raw: str) -> dict | None:
    """Parse a raw numeric expression: a single number or a closed range. Anything else -> None."""
    if not isinstance(raw, str):
        return None
    s = _clean(raw)
    if _THOUSANDS.match(s):
        s = s.replace(",", "")
    if _SINGLE.match(s):
        return {"kind": "single", "value": float(s)}
    m = _RANGE.match(s)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo <= hi:
            return {"kind": "range", "min": lo, "max": hi}
    return None


def resolve_unit(raw_unit: str, units: dict) -> tuple[str, str] | None:
    """Return (dimension, unit_code) for an exact unit or alias; None if unknown."""
    u = unicodedata.normalize("NFKC", raw_unit).strip() if raw_unit else ""
    if not u:
        return None
    for dim, spec in units["dimensions"].items():
        if u in spec["units"]:
            return dim, u
    for dim, spec in units["dimensions"].items():
        target = (spec.get("aliases") or {}).get(u)
        if target:
            return dim, target
    # NFKC turns "℃" into "°C" already; try the raw form against aliases too
    raw = raw_unit.strip()
    for dim, spec in units["dimensions"].items():
        target = (spec.get("aliases") or {}).get(raw)
        if target:
            return dim, target
    return None


def _num(x: float):
    x = round(x, 10)
    return int(x) if float(x).is_integer() else x


def normalize_value(raw_value: str | None, raw_unit: str | None, units: dict) -> tuple[dict, str | None]:
    """Return ({value|min,max, unit?}, reason). Empty dict + reason when not normalizable."""
    if raw_value is None:
        return {}, "no_raw_value"
    parsed = parse_raw_value(raw_value)
    if parsed is None:
        return {}, "unparsed_value"
    factor, offset, unit_out = 1.0, 0.0, None
    if raw_unit:
        resolved = resolve_unit(raw_unit, units)
        if resolved is None:
            return {}, "unknown_unit"
        dim, code = resolved
        spec = units["dimensions"][dim]
        conv = spec["units"][code]
        factor, offset, unit_out = conv["factor"], conv.get("offset", 0.0), spec["canonical"]
    out: dict = {}
    if parsed["kind"] == "single":
        out["value"] = _num(parsed["value"] * factor + offset)
    else:
        a, b = parsed["min"] * factor + offset, parsed["max"] * factor + offset
        out["min"], out["max"] = _num(min(a, b)), _num(max(a, b))
    if unit_out:
        out["unit"] = unit_out
    return out, None
