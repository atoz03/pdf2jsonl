#!/usr/bin/env python3
"""Build the repository-root paper dashboard from PDFs and actual pipeline artifacts.

The HTML embeds its data so it works when opened directly, without a web server.
Rerun `make dashboard` after adding PDFs or running extraction. Identical PDF bytes
are grouped by SHA-256; runs are never joined just because filenames match.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from breeding_contract.api import resolve_schema  # noqa: E402
from breeding_contract.derive import Deriver  # noqa: E402
from breeding_contract.util import load_yaml, sha256_file  # noqa: E402

SKIP_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.pytest_cache', '_site', 'releases', 'dist', 'build'}


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
            'synthetic': False, 'runs': [], 'tasks': [], 'notes': [], 'doi': '', 'year': None, 'crop': ''}


def _scan(root):
    pdfs, manifests, requests = [], [], []
    for folder, dirs, files in os.walk(root, followlinks=False):
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
    derived = None
    version = (manifest.get('contract') or {}).get('schema_version')
    try:
        if version not in contract_cache:
            contract_cache[version] = resolve_schema(version, root).contract
        deriver = Deriver(contract_cache[version])
        tables, triples, corpus = deriver.tables(records), deriver.triples(records), deriver.corpus(records)
        derived = {'tables': tables, 'triples': triples, 'corpus': corpus,
                   'counts': {'tables': len(tables), 'triples': len(triples), 'corpus': len(corpus)}}
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
            'records': records, 'errors': errors, 'warnings': warnings, 'audit': audit,
            'counts': {'records': len(records), 'rejected': len(errors), 'pending': review.get('pending_review', 0),
                       'auto_validated': review.get('auto_validated', 0), 'audit_flags': sum((audit.get('flags') or {}).values()),
                       'by_kind': dict(by_kind), 'by_review': dict(review)},
            'manifest': manifest, 'validation': validation, 'bundle': bundle, 'derived': derived,
            'raw_outputs': raw_outputs,
            'urls': urls, 'notes': notes, 'integrity_ok': not notes}


def build_data(root: Path = ROOT):
    root = root.resolve()
    pdfs, manifests, requests = _scan(root)
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


def build(root: Path = ROOT, out: Path | None = None):
    data = build_data(root)
    template = (ROOT / 'site/dashboard.template.html').read_text(encoding='utf-8')
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    # Keep source text inside the JSON script element, including malicious </script> snippets.
    payload = payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    destination = out or root / 'dashboard.html'
    base = quote(os.path.relpath(root.resolve(), destination.parent.resolve()), safe='/') + '/'
    result = template.replace('/*__DASHBOARD_DATA__*/null', payload).replace('__ROOT_HREF__', base)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result, encoding='utf-8')
    return destination, data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='repository to scan (includes ignored local run directories)')
    parser.add_argument('--out', type=Path, help='HTML output; defaults to repository-root dashboard.html')
    args = parser.parse_args()
    destination, data = build(args.root, args.out)
    print(f'{destination}: {data["summary"]["papers"]} papers, {data["summary"]["runs"]} runs, {data["summary"]["records"]} latest-run records')
