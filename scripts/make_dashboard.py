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

from breeding_contract.api import load_profile, resolve_schema  # noqa: E402
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


# A record-validation warning belongs to one of a few families, so the page can say what class of thing a
# warning is about instead of leaving the reader with a code. `code` is the pipeline code, or RULE_<id>.
WARNING_FAMILIES = (
    ('value', '取值核验', '原文没有逐字写出的字段取值（事实类字段）',
     ('VALUE_', 'DOCUMENT_VALUE_', 'EVIDENCE_PAGE_CORRECTED', 'EVIDENCE_TABLE_NOT_ON_PAGE', 'EVIDENCE_CELL_KEY_NOT_ON_PAGE')),
    ('rule', '填写规则', '契约的跨字段规则（R001..R035）没有通过', ('RULE_',)),
    ('link', '记录链接', '记录引用的其他记录或链接没有解析到', ('CANDIDATE_LINK_', 'UNRESOLVED_LINK', 'LINK_')),
    ('source', '来源完整性', '本次运行缺少论文的某个部分', ('SOURCE_PART_',)),
    ('integrity', '输出完整性', '运行产物自身的问题：文件缺失或哈希不一致', ('OUTPUT_INTEGRITY',)),
)
VALUE_WARNING_CODES = ('VALUE_', 'DOCUMENT_VALUE_')
RULE_SEVERITY = {'error': '错误', 'warning': '提示'}


def _warning_family(code):
    text = str(code or '')
    for key, _, _, prefixes in WARNING_FAMILIES:
        if text.startswith(prefixes):
            return key
    return 'other'


def _summarize_warnings(rows):
    """Group the record warnings of one run, and the rule codes they name, for the page and its filters."""
    groups = {key: {'label': label, 'description': description, 'count': 0,
                    'by_code': Counter(), 'by_field': Counter(), 'records': set()}
              for key, label, description, _ in WARNING_FAMILIES}
    groups['other'] = {'label': '其他提示', 'description': '', 'count': 0,
                       'by_code': Counter(), 'by_field': Counter(), 'records': set()}
    rule_help, rule_severity, value_records = {}, {}, set()
    for row in rows:
        rid = row.get('record_id')
        for issue in row.get('warnings', []):
            code = issue.get('code')
            family = _warning_family(code)
            group = groups[family]
            group['count'] += 1
            group['by_code'][code] += 1
            if issue.get('path'):
                group['by_field'][issue['path']] += 1
            if rid:
                group['records'].add(rid)
            if family == 'value' and rid:
                value_records.add(rid)
            if family == 'rule':
                rule_id = str(code or '').removeprefix('RULE_')
                rule_help[rule_id] = issue.get('message')
                rule_severity[rule_id] = RULE_SEVERITY.get(issue.get('severity'), issue.get('severity'))
    for group in groups.values():
        group['records'] = len(group['records'])
        group['by_code'] = dict(group['by_code'].most_common())
        group['by_field'] = dict(group['by_field'].most_common())
    return {'groups': groups, 'rule_help': rule_help, 'rule_severity': rule_severity,
            'value_warning_records': sorted(value_records)}


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


def _verification(root, records_file, notes):
    """Read the output of `bdc verify apply` for a run, if it is next to the records file.

    `bdc verify` writes <stem>.verification.json and <stem>.verified.jsonl next to the records (or where its
    --out points). The verified records carry the moved review fields (`model_verified`, `VERIFY_*` codes);
    the report carries what a model judged and what it flagged: conflicts between records of the paper, and
    statements the extraction missed. Neither is invented here — a run without a verification pass yields
    empty results and the raw records are shown unchanged."""
    blank = {'report': None, 'records': [], 'report_url': None, 'verified_url': None, 'verified_raw': None}
    if records_file is None:
        return blank
    stem = records_file.name[:-6] if records_file.name.endswith('.jsonl') else records_file.stem
    # `bdc verify apply ... --out review/` writes into a review directory beside the records (docs/review.md);
    # a verifier run without --out writes next to them.
    for folder in (records_file.parent, records_file.parent / 'review'):
        report_path = folder / f'{stem}.verification.json'
        if report_path.is_file():
            break
    else:
        return blank
    report = _read_json(report_path, notes)
    if not isinstance(report, dict) or report.get('verification_format') != 1:
        return blank
    verified_path = folder / f'{stem}.verified.jsonl'
    verified, verified_raw = [], None
    if verified_path.is_file():
        digest = (report.get('output') or {}).get('sha256')
        if digest and sha256_file(verified_path) != digest:
            notes.append('语义校验：已核验记录文件哈希与校验报告不一致')
        verified = _read_rows(verified_path, notes)
        verified_raw = verified_path.read_bytes().decode('utf-8')
    elif (report.get('output') or {}).get('file'):
        notes.append('语义校验：已核验记录文件缺失')
    return {'report': report,
            'records': verified or [],
            'report_url': _url(root, report_path),
            'verified_url': _url(root, verified_path) if verified else None,
            'verified_raw': verified_raw}


def _presence_policy(version, profile, contract_cache, root):
    """What the run's own profile checked for verbatim value presence.

    From 3.5.1 a profile may scope that check with `evidence_policy.value_presence_roles`: only fields whose
    `key_role` is listed there are checked, because a field the paper states in its own words (assertion,
    method_spec, condition …) is a paraphrase and never appears verbatim. A run whose profile has no such key
    checks every field, which is why its value warnings are not comparable with a later run's (docs/review.md).
    """
    key = ('presence', version, profile)
    if key not in contract_cache:
        roles, known = None, {}
        try:
            policy = (load_profile(profile, version, root).get('evidence_policy') or {}) if profile else {}
            if policy.get('value_presence_roles'):
                roles = list(policy['value_presence_roles'])
            for code, spec in (resolve_schema(version, root).contract.get('codes', {}).get('key_role') or {}).items():
                known[code] = spec.get('label_zh') or code
        except Exception:
            roles, known = None, {}
        contract_cache[key] = {'selective': roles is not None, 'roles': roles,
                               'checked': [known.get(r, r) for r in roles or []]}
    return contract_cache[key]


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
    verification = _verification(root, files.get('records'), notes)
    if verification['records']:
        records = verification['records']
    review = Counter((r.get('common') or {}).get('review_status', 'unknown') for r in records)
    by_kind = Counter((r.get('common') or {}).get('record_kind', 'unknown') for r in records)
    warnings = [{**issue, 'record_id': row.get('record_id'), 'record_kind': row.get('record_kind')}
                for row in validation.get('records', []) for issue in row.get('warnings', [])]
    warning_summary = _summarize_warnings(validation.get('records', []))
    audit = validation.get('argument_structure') or {}
    workflow = validation.get('workflow_structure') or {}
    source_parts = validation.get('source_parts') if isinstance(validation.get('source_parts'), dict) else None
    derived = None
    version = (manifest.get('contract') or {}).get('schema_version')
    record_profile = (manifest.get('profile') or {}).get('name', '')
    selective = _presence_policy(version, record_profile, contract_cache, root)
    try:
        if version not in contract_cache:
            contract_cache[version] = resolve_schema(version, root).contract
        views = Deriver(contract_cache[version]).views(records)
        totals = derive_counts(views)
        derived = {**views, 'counts': {'tables': len(views['tables']), 'triples': totals['triples'],
                                       'corpus': totals['corpus_chunks'], 'statements': totals['statements'],
                                       'graph_nodes': totals['graph_nodes'], 'qa': totals['qa_seeds'],
                                       'workflow_nodes': totals.get('workflow_nodes', 0),
                                       'workflow_edges': totals.get('workflow_edges', 0)}}
    except Exception as exc:
        notes.append(f'派生预览不可用: {exc.__class__.__name__}')
    model = (manifest.get('backend') or {}).get('model') or (manifest.get('backend') or {}).get('name', 'unknown')
    name = 'Codex 重新抽取' if model.startswith('Codex') else ('样例候选验证' if model == 'example-agent' else model)
    # Keep the original UTF-8 serialization so downloaded pipeline files retain their manifest hashes.
    raw_outputs = {kind: artifact.read_bytes().decode('utf-8') for kind, artifact in files.items()
                   if kind in {'records', 'errors', 'validation', 'bundle'}}
    raw_outputs['manifest'] = path.read_bytes().decode('utf-8')
    if verification['verified_raw']:
        raw_outputs['verified'] = verification['verified_raw']
    return {'id': hashlib.sha256(_relative(root, path).encode()).hexdigest()[:20],
            'run_id': manifest.get('run_id', path.stem), 'name': name, 'path': _relative(root, path.parent),
            'manifest_url': _url(root, path), 'created_at': manifest.get('created_at', ''),
            'version': version, 'profile': (manifest.get('profile') or {}).get('name', ''), 'model': model,
            'records': records, 'errors': errors, 'warnings': warnings, 'audit': audit, 'workflow': workflow,
            'warning_summary': warning_summary, 'rule_help': warning_summary['rule_help'],
            'rule_severity': warning_summary['rule_severity'],
            'value_warning_records': warning_summary['value_warning_records'],
            'presence_policy': selective,
            'source_parts': source_parts,
            'verification': verification['report'], 'verification_url': verification['report_url'],
            'verified_url': verification['verified_url'],
            'counts': {'records': len(records), 'rejected': len(errors), 'pending': review.get('pending_review', 0),
                       'auto_validated': review.get('auto_validated', 0), 'audit_flags': sum((audit.get('flags') or {}).values()),
                       'workflow_flags': sum((workflow.get('flags') or {}).values()),
                       'value_flags': warning_summary['groups']['value']['count'],
                       'value_records': warning_summary['groups']['value']['records'],
                       'model_verified': review.get('model_verified', 0),
                       'expert_approved': review.get('expert_approved', 0) + review.get('rejected', 0),
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
    verified = [r for r in latest_runs if r['verification']]
    reviewed = [r for r in verified if r['counts']['model_verified'] or r['counts']['expert_approved']]
    value_flagged = sum(r['counts'].get('value_records', 0) for r in latest_runs)
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
                        'pending': sum(r['counts']['pending'] for r in latest_runs),
                        'value_flags': sum(r['counts'].get('value_flags', 0) for r in latest_runs),
                        'value_records': value_flagged,
                        'selective_presence': sum(1 for r in latest_runs if r['presence_policy']['selective']),
                        'verified': len(verified), 'reviewed': len(reviewed)}}


def _linked_files(data):
    """Repository-relative paths of every file the page links to (PDFs, run manifests and outputs, the
    verification report and the verified records)."""
    urls = [p.get('pdf_url') for p in data.get('papers', [])]
    urls += [s.get('pdf_url') for p in data.get('papers', []) for s in p.get('supplements') or []]
    for paper in data.get('papers', []):
        for run in paper['runs']:
            urls += [run.get('manifest_url'), run.get('verification_url'), run.get('verified_url'),
                     *(run.get('urls') or {}).values()]
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
