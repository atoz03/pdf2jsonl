#!/usr/bin/env python3
"""Generate the local, cartoon breeding-themed SVG artwork used by both READMEs."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
INK = '#355448'
GREEN = '#16745f'
FONT = '"PingFang SC", "Microsoft YaHei", "Segoe UI", Arial, sans-serif'


def text(x, y, value, size=20, color=INK, weight=500, extra=''):
    return f'<text x="{x}" y="{y}" font-family="{escape(FONT, quote=True)}" font-size="{size}" font-weight="{weight}" fill="{color}" {extra}>{escape(value)}</text>'


def hero(english=False):
    title = 'Breeding papers, traceable data' if english else '育种论文，长成可追溯的数据'
    labels = ['Atomic records', 'Evidence first', 'Ready to reuse'] if english else ['一条事实一行', '每个结论有出处', '可复用的数据']
    main = ['Breeding papers,', 'traceable data.'] if english else ['育种论文，', '长成可追溯的数据。']
    sub = 'PDF → evidence checks → JSONL' if english else 'PDF → 证据核验 → JSONL'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="390" viewBox="0 0 1280 390" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title>
<desc id="desc">Cartoon rice panicles, a sprouting PDF paper, a DNA helix and a JSONL data card illustrate the breeding literature pipeline.</desc>
<rect x="2" y="2" width="1276" height="386" rx="30" fill="#fff9e9" stroke="#e8e4ce" stroke-width="2"/>
<path d="M3 301C51 239 143 263 195 295S269 365 358 388H30Q2 387 2 358Z" fill="#eaf2d7"/>
<path d="M1075 2C1080 49 1122 83 1174 87S1250 114 1278 169V32Q1278 2 1249 2Z" fill="#edf2d9"/>
<path d="M944 387c61-63 92-22 144-59s117-34 190-5v34q0 31-31 31Z" fill="#ecf2dc"/>
<g stroke="{INK}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
  <!-- Rice panicle: the breeding theme, not a generic technology mascot. -->
  <path d="M58 345q18-79 26-178" fill="none" stroke="#7b9560"/>
  <path d="M80 236Q43 218 39 177q40 13 41 59Z" fill="#97b677" stroke="#6c915d"/>
  <path d="M70 280q38-15 44-46-40 11-44 46Z" fill="#b5c98b" stroke="#6c915d"/>
  <path d="M84 171q-8-43 20-67" fill="none" stroke="#a99756"/>
  <g fill="#e7bd5e" stroke="#b3964b" stroke-width="2.2">
    <ellipse cx="94" cy="113" rx="8" ry="15" transform="rotate(25 94 113)"/>
    <ellipse cx="79" cy="128" rx="8" ry="15" transform="rotate(-25 79 128)"/>
    <ellipse cx="100" cy="139" rx="8" ry="15" transform="rotate(34 100 139)"/>
    <ellipse cx="77" cy="156" rx="8" ry="15" transform="rotate(-27 77 156)"/>
    <ellipse cx="96" cy="170" rx="8" ry="15" transform="rotate(32 96 170)"/>
    <ellipse cx="75" cy="184" rx="8" ry="15" transform="rotate(-25 75 184)"/>
  </g>
  <!-- Friendly paper with a seedling bookmark. -->
  <g transform="rotate(-7 204 210)">
    <rect x="134" y="102" width="144" height="220" rx="14" fill="#cfddbb" stroke="none"/>
    <path d="M145 87h91l35 37v175q0 13-13 13H143q-13 0-13-13V102q0-15 15-15Z" fill="#ffffff"/>
    <path d="M236 88v32q0 7 7 7h27" fill="#e4ecf5"/>
    <path d="M153 151h67M153 163h42" stroke="#a6b9af" stroke-width="5"/>
    <rect x="151" y="183" width="98" height="27" rx="7" fill="#edf4e7" stroke="none"/>
    <circle cx="175" cy="242" r="4" fill="{INK}" stroke="none"/>
    <circle cx="222" cy="242" r="4" fill="{INK}" stroke="none"/>
    <path d="M188 254q11 13 23 0" fill="none"/>
    <ellipse cx="158" cy="251" rx="9" ry="5" fill="#f0b5a0" stroke="none"/>
    <ellipse cx="239" cy="251" rx="9" ry="5" fill="#f0b5a0" stroke="none"/>
    <path d="M173 313v14m47-14v14M163 328h14m39 0h14" fill="none"/>
    <path d="M202 88V60" fill="none" stroke="#688957"/>
    <path d="M202 70q-30 1-32-23 29-1 32 23Z" fill="#94b97a" stroke="#688957"/>
    <path d="M202 76q28-3 30-24-28 1-30 24Z" fill="#b6d295" stroke="#688957"/>
  </g>
  <!-- The output card and a small linked-record trail. -->
  <path d="M895 265q43 3 78-33" fill="none" stroke="#9daf98" stroke-dasharray="4 9"/>
  <path d="m958 232 17-2-5 17" fill="none" stroke="#9daf98"/>
  <g transform="rotate(5 1104 224)">
    <rect x="998" y="153" width="193" height="147" rx="17" fill="#d5e4d6" stroke="none"/>
    <rect x="988" y="140" width="193" height="147" rx="17" fill="#f6fbff"/>
    <path d="M989 177h191" stroke="#bacfdf" stroke-width="2"/>
    <circle cx="1009" cy="160" r="4" fill="#e5bf61" stroke="none"/><circle cx="1024" cy="160" r="4" fill="#a9c68c" stroke="none"/>
    <path d="M1012 198h68m-68 14h92m-92 14h56" stroke="#9eb8ca" stroke-width="4"/>
    <circle cx="1124" cy="230" r="3.5" fill="{INK}" stroke="none"/><circle cx="1150" cy="230" r="3.5" fill="{INK}" stroke="none"/>
    <path d="M1130 242q7 8 14 0" fill="none"/>
    <path d="M1030 288v17m84-17v17M1022 307h12m76 0h13" fill="none"/>
  </g>
  <circle cx="1191" cy="148" r="22" fill="#9dc49f"/>
  <path d="m1182 148 6 7 12-15" fill="none" stroke="#315e46" stroke-width="4"/>
  <!-- DNA hint and small botanical details. -->
  <g transform="translate(1026 34) rotate(14)">
    <path d="M0 0c60 26-23 67 35 92M35 0c-60 26 23 67-35 92" fill="none" stroke="#86a7c4" stroke-width="4"/>
    <path d="M3 7h29M8 21h17M8 70h17M3 85h29" stroke="#c8a778" stroke-width="3"/>
    <path d="M13 35h11M12 54h12" stroke="#93b182"/>
  </g>
  <path d="M1213 319q15-6 17-25-18 2-17 25Z" fill="#a1bd7f" stroke="#76915d"/>
  <path d="M1210 339q-18-12-18-26 22 3 18 26Z" fill="#bfd294" stroke="#76915d"/>
  <path d="M1210 350q1-20 4-33" fill="none" stroke="#76915d"/>
</g>
'''
    svg += text(155,206,'PDF',16,GREEN,700,extra='transform="rotate(-7 155 206)"')
    svg += text(1080,168,'JSONL',15,GREEN,700,extra='transform="rotate(5 1080 168)"')
    svg += text(326,72,'PDF2JSONL  /  BREEDING DATA',14,GREEN,700,extra='letter-spacing="1.8"')
    svg += text(324,139,main[0],42,INK,760)
    svg += text(324,191,main[1],42,INK,760)
    svg += text(326,233,sub,21,'#7d8b77',500)
    widths = [155,165,160]
    x=326
    for label,width in zip(labels,widths):
        svg += f'<rect x="{x}" y="271" width="{width}" height="35" rx="17" fill="#edf3e0" stroke="#d6e1c7"/>'
        svg += text(x+width/2,294,label,15,'#597455',600,extra='text-anchor="middle"')
        x += width+10
    svg += text(326,345,'A little paper. A growing knowledge garden.' if english else '从原文出发，让每一条数据都能回到证据。',16,'#9b9d83',500)
    svg += '</svg>\n'
    return svg


def icon(body, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80" role="img" aria-label="{title}">
<rect x="2" y="2" width="76" height="76" rx="23" fill="#fbf5e5"/>
<g stroke="{INK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>\n'''


def assets():
    return {
        'readme-hero.svg': hero(),
        'readme-hero.en.svg': hero(True),
        'icons/paper.svg':icon('''<path d="M23 13h24l13 13v39H21V16q0-3 2-3Z" fill="#fff"/><path d="M47 14v13h12" fill="#dce9ef"/><path d="M29 34h19M29 42h13" stroke="#8fae9d"/><circle cx="31" cy="53" r="1.8" fill="#355448" stroke="none"/><circle cx="47" cy="53" r="1.8" fill="#355448" stroke="none"/><path d="M35 58q5 5 10 0" fill="none"/><path d="M63 43q11 1 10 12-11-1-10-12Z" fill="#a8c889" stroke="#75966c"/>''','论文看板'),
        'icons/fields.svg':icon('''<path d="M40 54V28" fill="none"/><path d="M40 40Q17 39 16 21q23-1 24 19Z" fill="#a9c88a"/><path d="M40 32Q60 34 65 15q-23-1-25 17Z" fill="#7fac82"/><path d="M40 52v8M23 65v-9h34v9" fill="none"/><circle cx="23" cy="65" r="6" fill="#dfbb65"/><circle cx="40" cy="65" r="6" fill="#fff"/><circle cx="57" cy="65" r="6" fill="#b0c6dc"/>''','字段定义'),
        'icons/pipeline.svg':icon('''<path d="M26 24h28v31H25" fill="none" stroke-dasharray="3 5"/><rect x="10" y="12" width="26" height="24" rx="8" fill="#fff"/><rect x="46" y="42" width="24" height="24" rx="8" fill="#bfd8b9"/><rect x="10" y="44" width="24" height="22" rx="8" fill="#d4e3ef"/><path d="m52 20 5 4-5 4M38 51l-5 4 5 4" fill="none"/><path d="M18 21h10M18 27h7M53 51l4 5 6-7" fill="none"/><path d="M21 56v-5m0 5q-7-1-7-7 8 0 7 7Z" fill="#9bb77c"/>''','数据管线'),
        'icons/extract.svg':icon('''<path d="M29 13h23M32 13v19L17 57q-6 11 9 11h31q14 0 8-11L49 32V13" fill="#f7fcff"/><path d="M24 47h34l8 14q1 7-10 7H26q-13 0-9-9Z" fill="#c5dfba" stroke="none"/><path d="M32 13v19L17 57q-6 11 9 11h31q14 0 8-11L49 32V13" fill="none"/><path d="M41 58V42m0 8q-12 0-14-10 13 0 14 10Zm0-5q12 0 14-11-14 0-14 11Z" fill="#8eb879" stroke-width="2"/><circle cx="56" cy="20" r="4" fill="#e8bf68" stroke="none"/><circle cx="63" cy="10" r="3" fill="#aac8dd" stroke="none"/>''','开始抽取'),
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    stale=[]
    for name,svg in assets().items():
        path=ASSETS/name
        value='<?xml version="1.0" encoding="UTF-8"?>\n<!-- Generated by scripts/make_readme_art.py. -->\n'+svg
        if path.exists() and path.read_text(encoding='utf-8')==value:
            continue
        stale.append(name)
        if not args.check:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(value,encoding='utf-8')
    if args.check and stale:
        print('README art is stale; run make readme-art: '+', '.join(stale),file=sys.stderr)
        return 1
    print('README art: '+(', '.join(stale)+' updated' if stale else 'up to date'))
    return 0


if __name__=='__main__':
    sys.exit(main())
