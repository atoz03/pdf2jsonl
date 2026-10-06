#!/usr/bin/env python3
"""Export the native SVG diagram embedded in pipeline.html, in Chinese and English.

No browser or third-party package is required. HTML is the editable source; both
README images are standalone vectors with text, shapes, paths and embedded styles.
Run `make diagram` after edits, or `python3 scripts/export_pipeline_diagram.py --check`.
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/diagrams/pipeline.html"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def render_diagrams() -> dict[Path, str]:
    html = SOURCE.read_text(encoding="utf-8")
    match = re.search(r'<svg\b[^>]*\bid="pipeline-diagram"[^>]*>.*?</svg>', html, re.DOTALL)
    if match is None:
        raise ValueError("pipeline.html must contain <svg id=\"pipeline-diagram\">")
    source = ET.fromstring(match.group())
    forbidden = {"script", "foreignObject", "image"}
    for node in source.iter():
        if node.tag.rsplit("}", 1)[-1] in forbidden:
            raise ValueError(f"README diagram must use native vectors, found {node.tag}")
        if any(key.startswith("on") or key.endswith("href") for key in node.attrib):
            raise ValueError("README SVG must be self-contained and script-free")
    outputs = {}
    for locale, filename in (("zh-CN", "pipeline.svg"), ("en", "pipeline.en.svg")):
        svg = copy.deepcopy(source)
        svg.set("lang", locale)
        for node in svg.iter():
            english = node.attrib.pop("data-en", None)
            if locale == "en" and english is not None:
                node.text = english
            for key in list(node.attrib):
                if key.startswith("data-") or key == "tabindex":
                    del node.attrib[key]
        ET.indent(svg, space="  ")
        outputs[SOURCE.with_name(filename)] = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- Generated from pipeline.html by scripts/export_pipeline_diagram.py. -->\n'
            + ET.tostring(svg, encoding="unicode") + "\n"
        )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed SVGs differ from the HTML source")
    args = parser.parse_args()
    try:
        outputs = render_diagrams()
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"diagram error: {exc}", file=sys.stderr)
        return 1
    stale = []
    for path, content in outputs.items():
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        stale.append(path.relative_to(ROOT))
        if not args.check:
            path.write_text(content, encoding="utf-8")
    if args.check and stale:
        print("stale diagrams: " + ", ".join(map(str, stale)) + "; run make diagram", file=sys.stderr)
        return 1
    print("diagrams: " + (", ".join(map(str, stale)) + " updated" if stale else "up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
