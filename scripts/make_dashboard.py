#!/usr/bin/env python3
"""Build the paper dashboard from PDFs and actual pipeline artifacts.

Two uses share this module:

- `scripts/make_site.py` builds it as the "Papers" page of the Pages site, from the checked-in examples, and
  copies the PDFs and run outputs it links to next to the page.
- `make dashboard` writes an untracked `dashboard.html` in the repository root that also covers local run
  directories. Rerun it after adding PDFs or running extraction.

The HTML embeds its data so it works when opened directly, without a web server. Identical PDF bytes are
grouped by SHA-256; runs are never joined just because filenames match. A PDF that a run manifest lists as a
supplement of its input is shown as a part of that paper, not as a paper of its own.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from breeding_contract.api import resolve_schema  # noqa: E402
from breeding_contract.derive import Deriver, counts as derive_counts  # noqa: E402
from breeding_contract.util import load_yaml, sha256_file  # noqa: E402

SKIP_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.pytest_cache', '_site', 'releases', 'dist', 'build'}
# Sidebar links (label, icon, href). The local file points into the repository, the site page into the site.
LOCAL_NAV = (('字段定义', 'table', 'docs/generated/field_definitions.md'), ('下游派生', 'layers', 'docs/downstream.md'),
             ('数据管线', 'flow', 'docs/diagrams/pipeline.html'), ('项目说明', 'book', 'README.md'))
SITE_NAV = (('规范总览', 'home', 'index.html#overview'), ('字段目录', 'table', 'index.html#fields'),
            ('抽取演示', 'file', 'index.html#demo'), ('下游派生', 'layers', 'index.html#downstream'),
            ('存量导入', 'download', 'index.html#importers'), ('数据管线', 'flow', 'pipeline.html'))


def _relative(root, path):
    return path.resolve().relative_to(root.resolve()).as_posix()


def _url(root, path):
    return './' + quote(_relative(root, path), safe='/')


def _inside(root, parent, name):
    if not isinstance(name, str) or not name:
        return None
    path = (parent / name).resolve()
    if not path.is_relative_to(root.resolve()):
        return None
    return path


def _read_json(path, notes):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        notes.append(f'{path.name}: {exc.__class__.__name__}')
        return None


def _read_rows(path, notes):
    if path is None:
        return []
    try:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
    except OSError:
        notes.append(f'{path.name}: 文件缺失或无法读取')
        return []
    rows = []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError('not an object')
            rows.append(value)
        except ValueError:
            notes.append(f'{path.name}:{n}: 无效 JSON 记录')
    return rows


def _paper(key, filename):
    return {'id': key, 'filename': filename, 'title': filename, 'pdf_url': None,
            'pdf_paths': [], 'pages': [], 'page_count': 0, 'size_bytes': 0,
            'synthetic': False, 'runs': [], 'tasks': [], 'notes': [], 'doi': '', 'year': None, 'crop': '',
            'supplements': []}


def _scan(root, scan=None):
    """PDFs, run manifests and prepared tasks under ``root``, or only under its ``scan`` subdirectories."""
    pdfs, manifests, requests = [], [], []
    walks = (w for start in ([root] if not scan else [root / d for d in scan]) for w in os.walk(start, followlinks=False))
    for folder, dirs, files in walks:
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith('.egg-info'))
        for name in sorted(files):
            path = Path(folder) / name
            if not path.resolve().is_relative_to(root.resolve()):
                continue
            if name.lower().endswith('.pdf'):
                pdfs.append(path)
            elif name.endswith('.manifest.json'):
                manifests.append(path)
            elif name == 'request.json' and Path(folder).name.endswith('.work'):
                requests.append(path)
    return pdfs, manifests, requests


def _run(root, path, manifest, contract_cache):
    notes = []
    outputs = manifest.get('outputs') or {}
    files, urls = {}, {}
    for kind, spec in outputs.items():
        name = spec.get('file') if isinstance(spec, dict) else None
        artifact = _inside(root, path.parent, name)
        if artifact is None:
            notes.append(f'{kind}: 非法或超出仓库的输出路径')
            continue
        if not artifact.is_file():
            notes.append(f'{kind}: 输出文件缺失')
            continue
        if spec.get('sha256') and sha256_file(artifact) != spec['sha256']:
            notes.append(f'{kind}: 文件哈希与运行清单不一致')
        files[kind] = artifact
        urls[kind] = _url(root, artifact)
    if 'records' not in files:
        notes.append('记录文件不可用')
    records = _read_rows(files.get('records'), notes)
    errors = _read_rows(files.get('errors'), notes)
    validation = _read_json(files['validation'], notes) if 'validation' in files else None
    if not isinstance(validation, dict):
        validation = {}
    bundle = _read_json(files['bundle'], notes) if 'bundle' in files else None
    declared = (manifest.get('counts') or {}).get('records')
    if isinstance(declared, int) and declared != len(records):
        notes.append(f'清单声明 {declared} 条记录，实际读到 {len(records)} 条')
    review = Counter((r.get('common') or {}).get('review_status', 'unknown') for r in records)
    by_kind = Counter((r.get('common') or {}).get('record_kind', 'unknown') for r in records)
    warnings = [{**issue, 'record_id': row.get('record_id'), 'record_kind': row.get('record_kind')}
                for row in validation.get('records', []) for issue in row.get('warnings', [])]
    audit = validation.get('argument_structure') or {}
    workflow = validation.get('workflow_structure') or {}
    source_parts = validation.get('source_parts') if isinstance(validation.get('source_parts'), dict) else None
    derived = None
    version = (manifest.get('contract') or {}).get('schema_version')
    try:
        if version not in contract_cache:
            contract_cache[version] = resolve_schema(version, root).contract
        views = Deriver(contract_cache[version]).views(records)
        totals = derive_counts(views)
        derived = {**views, 'counts': {'tables': len(views['tables']), 'triples': totals['triples'],
                                       'corpus': totals['corpus_chunks'], 'statements': totals['statements'],
                                       'graph_nodes': totals['graph_nodes'], 'qa': totals['qa_seeds']}}
    except Exception as exc:
        notes.append(f'派生预览不可用: {exc.__class__.__name__}')
    model = (manifest.get('backend') or {}).get('model') or (manifest.get('backend') or {}).get('name', 'unknown')
    name = 'Codex 重新抽取' if model.startswith('Codex') else ('样例候选验证' if model == 'example-agent' else model)
    # Keep the original UTF-8 serialization so downloaded pipeline files retain their manifest hashes.
    raw_outputs = {kind: artifact.read_bytes().decode('utf-8') for kind, artifact in files.items()
                   if kind in {'records', 'errors', 'validation', 'bundle'}}
    raw_outputs['manifest'] = path.read_bytes().decode('utf-8')
    return {'id': hashlib.sha256(_relative(root, path).encode()).hexdigest()[:20],
            'run_id': manifest.get('run_id', path.stem), 'name': name, 'path': _relative(root, path.parent),
            'manifest_url': _url(root, path), 'created_at': manifest.get('created_at', ''),
            'version': version, 'profile': (manifest.get('profile') or {}).get('name', ''), 'model': model,
            'records': records, 'errors': errors, 'warnings': warnings, 'audit': audit, 'workflow': workflow,
            'source_parts': source_parts,
            'counts': {'records': len(records), 'rejected': len(errors), 'pending': review.get('pending_review', 0),
                       'auto_validated': review.get('auto_validated', 0), 'audit_flags': sum((audit.get('flags') or {}).values()),
                       'workflow_flags': sum((workflow.get('flags') or {}).values()),
                       'by_kind': dict(by_kind), 'by_review': dict(review)},
            'manifest': manifest, 'validation': validation, 'bundle': bundle, 'derived': derived,
            'raw_outputs': raw_outputs,
            'urls': urls, 'notes': notes, 'integrity_ok': not notes}


def build_data(root: Path = ROOT, scan=None):
    root = root.resolve()
    pdfs, manifests, requests = _scan(root, scan)
    papers, diagnostics, contract_cache = {}, [], {}
    for path in pdfs:
        try:
            digest = sha256_file(path)
        except OSError:
            diagnostics.append({'path': _relative(root, path), 'message': 'PDF 无法读取'})
            continue
        key = 'sha256:' + digest
        paper = papers.setdefault(key, _paper(key, path.name))
        paper['pdf_paths'].append(_relative(root, path))
        if paper['pdf_url']:
            continue
        paper['pdf_url'] = _url(root, path)
        paper['size_bytes'] = path.stat().st_size
        try:
            from pypdf import PdfReader
            pdf = PdfReader(path)
            paper['pages'] = [{'page': n, 'text': page.extract_text() or ''} for n, page in enumerate(pdf.pages, 1)]
            paper['page_count'] = len(pdf.pages)
            first = paper['pages'][0]['text'] if paper['pages'] else ''
            first_line = next((x.strip() for x in first.splitlines() if x.strip()), path.name)
            paper['title'] = first_line
            paper['synthetic'] = 'synthetic example' in first.lower() or 'synthetic' in path.stem.lower()
        except Exception as exc:
            paper['notes'].append(f'文本预览不可用（{exc.__class__.__name__}），仍可打开原 PDF。')
    completed = set()
    supplements = {}  # key of a supplement file -> (key of the paper it belongs to, its part label)
    for path in manifests:
        notes = []
        manifest = _read_json(path, notes)
        if not isinstance(manifest, dict) or not isinstance(manifest.get('input'), dict):
            diagnostics.append({'path': _relative(root, path), 'message': '运行清单无效：' + '; '.join(notes)})
            continue
        source = manifest['input']
        digest = source.get('sha256', '')
        key = ('sha256:' + digest.lower()) if isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdefABCDEF' for c in digest) else 'manifest:' + _relative(root, path)
        paper = papers.setdefault(key, _paper(key, str(source.get('file_name', path.stem))))
        try:
            run = _run(root, path, manifest, contract_cache)
        except (AttributeError, TypeError, ValueError, OSError) as exc:
            diagnostics.append({'path': _relative(root, path), 'message': f'运行数据无法读取：{exc.__class__.__name__}'})
            continue
        paper['runs'].append(run)
        if not paper['page_count']:
            paper['page_count'] = source.get('page_count') or 0
        for part in source.get('supplements') or []:
            if isinstance(part, dict) and isinstance(part.get('sha256'), str) and isinstance(part.get('part'), str):
                supplements.setdefault('sha256:' + part['sha256'].lower(), (key, part['part']))
        completed.add((path.parent.resolve(), digest))
    for path in requests:
        notes = []
        request = _read_json(path, notes)
        if not isinstance(request, dict):
            continue
        source = request.get('input') or {}
        digest = source.get('sha256')
        if not isinstance(digest, str):
            continue
        destination = Path((request.get('options') or {}).get('out_dir') or path.parent.parent)
        if not destination.is_absolute():
            destination = root / destination
        if (destination.resolve(), digest) in completed:
            continue
        key = 'sha256:' + digest
        paper = papers.setdefault(key, _paper(key, Path(str(source.get('path', '未命名 PDF'))).name))
        paper['tasks'].append({'path': _relative(root, path.parent), 'created_at': request.get('created_at', ''),
                               'version': (request.get('contract') or {}).get('schema_version'),
                               'has_candidates': (path.parent / 'candidates.json').is_file()})
    for part_key, (owner, label) in supplements.items():
        part = papers.get(part_key)
        if part is None or part['runs'] or part['tasks'] or owner not in papers or owner == part_key:
            continue  # the file is not here, or it was also run as a paper of its own: leave it as it is
        papers[owner]['supplements'].append({k: part[k] for k in ('filename', 'pdf_url', 'pdf_paths', 'pages',
                                                                   'page_count', 'size_bytes')} | {'part': label})
        del papers[part_key]
    for paper in papers.values():
        paper['runs'].sort(key=lambda r: (r['created_at'], r['path']), reverse=True)
        if paper['runs']:
            latest = paper['runs'][0]
            metadata = next((r.get('common') for r in latest['records'] if isinstance(r.get('common'), dict)), {})
            if not metadata:
                metadata = {(k.removeprefix('common.')): v for k,v in (latest['validation'].get('document', {}).get('values') or {}).items()}
            paper['title'] = metadata.get('source_title') or paper['title']
            paper['doi'] = metadata.get('source_doi') or ''
            paper['year'] = metadata.get('source_year')
            paper['crop'] = metadata.get('crop_name') or ''
            counts = latest['counts']
            paper['status'] = 'problem' if not latest['integrity_ok'] else ('review' if counts['rejected'] or counts['pending'] or counts['audit_flags'] else 'complete')
        else:
            paper['status'] = 'prepared' if paper['tasks'] else 'unprocessed'
    items = sorted(papers.values(), key=lambda p: ((p['runs'][0]['created_at'] if p['runs'] else ''), p['title']), reverse=True)
    latest_runs = [p['runs'][0] for p in items if p['runs']]
    try:
        current = resolve_schema('latest', root)
        classification = load_yaml(root / 'docs/field_classification.yaml')
        fields = {f['path']: {'definition': f['definition_zh'], 'type': f['type'], 'availability': f['availability'],
                             'tags': [classification['tags'][t]['label_zh'] for t in classification['fields'].get(f['path'], [])]}
                  for f in current.fields}
        version = current.version
    except Exception:
        fields, version = {}, ''
    return {'dashboard_format': 1, 'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'version': version, 'papers': items, 'fields': fields, 'diagnostics': diagnostics,
            'summary': {'papers': len(items), 'processed': len(latest_runs), 'runs': sum(len(p['runs']) for p in items),
                        'records': sum(r['counts']['records'] for r in latest_runs),
                        'pending': sum(r['counts']['pending'] for r in latest_runs)}}


def _linked_files(data):
    """Repository-relative paths of every file the page links to (PDFs, run manifests and outputs)."""
    urls = [p.get('pdf_url') for p in data.get('papers', [])]
    urls += [s.get('pdf_url') for p in data.get('papers', []) for s in p.get('supplements') or []]
    for paper in data.get('papers', []):
        for run in paper['runs']:
            urls += [run.get('manifest_url'), *(run.get('urls') or {}).values()]
    return sorted({unquote(u[2:]) for u in urls if isinstance(u, str) and u.startswith('./')})


def _nav(items):
    return ''.join(f'<a href="{href}" class="side-link"><span data-icon="{icon}"></span>{label}</a>'
                   for label, icon, href in items)


def build(root: Path = ROOT, out: Path | None = None, scan=None, site: bool = False):
    """Write the dashboard. With ``site`` the page is self-contained under its own directory: the files it
    links to are copied next to it and the sidebar points at the other pages of the site."""
    data = build_data(root) if scan is None else build_data(root, scan)
    template = (ROOT / 'site/dashboard.template.html').read_text(encoding='utf-8')
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    # Keep source text inside the JSON script element, including malicious </script> snippets.
    payload = payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    destination = out or root / 'dashboard.html'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if site:
        base = './'
        for rel in _linked_files(data):
            target = destination.parent / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / rel, target)
    else:
        base = quote(os.path.relpath(root.resolve(), destination.parent.resolve()), safe='/') + '/'
    self_href = quote(destination.name) if site else quote(os.path.relpath(destination.resolve(), root.resolve()), safe='/')
    values = {'/*__DASHBOARD_DATA__*/null': payload, '__ROOT_HREF__': base, '__SELF_HREF__': self_href,
              '<!--__NAV__-->': _nav(SITE_NAV if site else LOCAL_NAV),
              '__PIPELINE_SVG_HREF__': 'assets/pipeline.svg' if site else 'docs/diagrams/pipeline.svg',
              '__SNAPSHOT_LABEL__': '示例数据快照' if site else '本地数据快照'}
    result = template
    for key, value in values.items():
        result = result.replace(key, value)
    destination.write_text(result, encoding='utf-8')
    return destination, data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='repository to scan (includes ignored local run directories)')
    parser.add_argument('--out', type=Path, help='HTML output; defaults to an untracked dashboard.html in the repository root')
    parser.add_argument('--scan', action='append', metavar='DIR', help='only scan this subdirectory (repeatable)')
    args = parser.parse_args()
    destination, data = build(args.root, args.out, args.scan)
    print(f'{destination}: {data["summary"]["papers"]} papers, {data["summary"]["runs"]} runs, {data["summary"]["records"]} latest-run records')
