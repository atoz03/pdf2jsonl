"""Assemble one page of the site: its template under site/pages/, the shared kit under site/kit/ and its data.

Every page is a single self-contained HTML file. The template marks three places:

    <!--__HEAD__-->   kit stylesheet, icon and the early theme/language switch (no flash of the wrong theme)
    <!--__DATA__-->   <script id="site-data" type="application/json"> with the page's data
    <!--__KIT__-->    kit script: header, footer, language and theme, shared helpers (global K)

`scripts/make_site.py` renders every page of the Pages site; `scripts/make_dashboard.py` renders the paper
dashboard with the same shell, for the site or as an untracked local page.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "site/kit"
PAGES = ROOT / "site/pages"

# Set before first paint: the stored or system theme, and the stored language.
BOOT = ("(function(){var d=document.documentElement;try{var t=localStorage.getItem('pdf2jsonl.theme');"
        "if(t!=='dark'&&t!=='light')t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';"
        "d.dataset.theme=t;d.lang=localStorage.getItem('pdf2jsonl.lang')==='en'?'en':'zh-CN'}"
        "catch(e){d.dataset.theme='light'}})();")
ICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36"><rect width="36" height="36" rx="10" fill="#0f2a24"/>'
        '<path d="M12.5 30.5c3.4-6.6 5.6-13.4 6.6-22.5" stroke="#8fd0aa" stroke-width="1.8" fill="none" stroke-linecap="round"/>'
        '<g fill="#e8b852"><ellipse cx="20.6" cy="8.6" rx="2.1" ry="3.6" transform="rotate(30 20.6 8.6)"/>'
        '<ellipse cx="16.3" cy="12.2" rx="2.1" ry="3.6" transform="rotate(-32 16.3 12.2)"/>'
        '<ellipse cx="21.6" cy="14.6" rx="2.1" ry="3.6" transform="rotate(34 21.6 14.6)"/>'
        '<ellipse cx="15.7" cy="18.2" rx="2" ry="3.4" transform="rotate(-30 15.7 18.2)"/>'
        '<ellipse cx="20.4" cy="20.6" rx="2" ry="3.3" transform="rotate(36 20.4 20.6)"/></g></svg>')


def payload(data) -> str:
    """JSON for a <script type="application/json"> element: nothing in it can close the element."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render(name: str, data: dict, *, base: str | None = None) -> str:
    """The HTML of page `name` with `data` embedded; `base` adds <base href> (the dashboard's file links)."""
    template = (PAGES / f"{name}.html").read_text(encoding="utf-8")
    css = (KIT / "kit.css").read_text(encoding="utf-8")
    js = (KIT / "kit.js").read_text(encoding="utf-8")
    head = (f'<link rel="icon" href="data:image/svg+xml,{quote(ICON)}">\n'
            + (f'<base href="{base}">\n' if base is not None else "")
            + f"<script>{BOOT}</script>\n<style>\n{css}</style>")
    values = {"<!--__HEAD__-->": head,
              "<!--__DATA__-->": f'<script id="site-data" type="application/json">{payload(data)}</script>',
              "<!--__KIT__-->": f"<script>\n{js}</script>"}
    for key, value in values.items():
        if template.count(key) != 1:
            raise ValueError(f"site/pages/{name}.html must contain {key} exactly once")
        template = template.replace(key, value)
    return template
