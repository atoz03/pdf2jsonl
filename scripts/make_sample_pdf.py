#!/usr/bin/env python3
"""Write a minimal text-layer PDF from a form-feed separated .txt (one page per \\f block).

Used to build the synthetic example paper (examples/papers/) without third-party PDF writers.
ASCII text only; Helvetica 10pt; long lines are wrapped at 95 characters.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(pages: list[str]) -> bytes:
    objs: list[bytes] = []
    n_pages = len(pages)
    # 1 catalog, 2 pages, 3 font, then (page, content) pairs
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, text in enumerate(pages):
        lines: list[str] = []
        for raw in text.strip("\n").splitlines():
            lines.extend(textwrap.wrap(raw, 95) or [""])
        ops = ["BT", "/F1 10 Tf", "12 TL", "56 800 Td"]
        for ln in lines:
            ops.append(f"({_esc(ln)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for k, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{k} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def main(argv: list[str]) -> int:
    src, dst = Path(argv[1]), Path(argv[2])
    pages = src.read_text(encoding="ascii").split("\f")
    dst.write_bytes(build_pdf([p for p in pages if p.strip()]))
    print(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
