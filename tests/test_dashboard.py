"""Paper indexing: content identity, real artifact state, safe paths and portable HTML."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

from pypdf import PdfWriter

from scripts import make_dashboard as dashboard
from breeding_contract import resolve_schema


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def test_same_content_is_one_paper_but_same_filename_is_not(root, tmp_path):
    original=root/'examples/papers/synthetic_rice_qtl.pdf'
    for name in ['a/paper.pdf','b/copy.pdf']:
        path=tmp_path/name
        path.parent.mkdir(parents=True)
        shutil.copyfile(original,path)
    other=tmp_path/'c/paper.pdf'
    other.parent.mkdir()
    writer=PdfWriter();writer.add_blank_page(width=100,height=100)
    with other.open('wb') as handle: writer.write(handle)
    data=dashboard.build_data(tmp_path)
    assert data['summary']['papers']==2
    assert sorted(len(p['pdf_paths']) for p in data['papers'])==[1,2]
    assert all(p['status']=='unprocessed' for p in data['papers'])
    assert data['summary']['processed']==data['summary']['records']==0


def sample_run(root,tmp_path):
    folder=tmp_path/'runs/current';folder.mkdir(parents=True)
    records=[json.loads((root/'examples/records/phenotype_observation.jsonl').read_text())]
    records[0]['common']['review_status']='auto_validated'
    artifacts={'records':('paper.jsonl',''.join(json.dumps(r)+'\n' for r in records)),
               'errors':('paper.errors.jsonl',''),
               'validation':('paper.validation.json',json.dumps({'report_format':1,'records':[],'argument_structure':{'flags':{}}}))}
    manifest={'run_id':'test-run','created_at':'2026-10-06T12:00:00Z',
              'input':{'file_name':'paper.pdf','sha256':'a'*64},
              'contract':{'schema_version':'3.3.0'},'profile':{'name':'pdf_extraction'},
              'counts':{'records':1},'outputs':{}}
    for kind,(name,text) in artifacts.items():
        path=folder/name;path.write_text(text)
        manifest['outputs'][kind]={'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    path=folder/'paper.manifest.json';write_json(path,manifest)
    return path,manifest,{'3.3.0':resolve_schema('3.3.0',root).contract}


def test_run_counts_and_exports_come_from_real_artifacts(root,tmp_path):
    path,manifest,contracts=sample_run(root,tmp_path)
    run=dashboard._run(tmp_path,path,manifest,contracts)
    assert run['counts']['records']==1 and run['counts']['pending']==0
    assert run['integrity_ok'] and run['derived']['counts']['tables']==6
    assert len(run['derived']['tables']['records'])==1
    for kind in ['records','errors','validation']:
        assert hashlib.sha256(run['raw_outputs'][kind].encode()).hexdigest()==manifest['outputs'][kind]['sha256']
    (path.parent/'paper.jsonl').unlink()
    broken=dashboard._run(tmp_path,path,manifest,contracts)
    assert broken['counts']['records']==0 and not broken['integrity_ok']
    assert any('记录文件不可用' in n for n in broken['notes'])


def test_tampered_output_and_escaping_path_are_flagged(root,tmp_path):
    path,manifest,contracts=sample_run(root,tmp_path)
    (path.parent/'paper.errors.jsonl').write_text('{}\n')
    manifest['outputs']['bundle']={'file':'../../../../outside.json'}
    run=dashboard._run(tmp_path,path,manifest,contracts)
    assert not run['integrity_ok']
    assert any('哈希' in n for n in run['notes'])
    assert any('超出仓库' in n for n in run['notes'])
    assert 'bundle' not in run['urls']


def test_pending_task_does_not_appear_as_completed(root,tmp_path):
    paper=tmp_path/'papers/sample.pdf';paper.parent.mkdir()
    shutil.copyfile(root/'examples/papers/synthetic_rice_qtl.pdf',paper)
    digest=hashlib.sha256(paper.read_bytes()).hexdigest()
    write_json(tmp_path/'out/sample.work/request.json',{
        'input':{'path':str(paper),'sha256':digest},'contract':{'schema_version':'3.3.0'},
        'options':{'out_dir':str(tmp_path/'out')},'created_at':'2026-10-06T12:00:00Z'})
    data=dashboard.build_data(tmp_path)
    [entry]=data['papers']
    assert entry['status']=='prepared' and len(entry['tasks'])==1
    assert data['summary']['processed']==0 and not entry['runs']


def test_unmatched_input_hash_does_not_attach_to_same_filename(root,tmp_path,monkeypatch):
    original_resolve=resolve_schema
    monkeypatch.setattr(dashboard,'resolve_schema',lambda version,ignored:original_resolve(version,root))
    path,manifest,_=sample_run(root,tmp_path)
    shutil.copyfile(root/'examples/papers/synthetic_rice_qtl.pdf',tmp_path/'paper.pdf')
    data=dashboard.build_data(tmp_path)
    assert len(data['papers'])==2
    imported=next(p for p in data['papers'] if p['runs'])
    assert imported['pdf_url'] is None
    assert next(p for p in data['papers'] if p['pdf_url'])['status']=='unprocessed'


def test_embedded_json_cannot_close_script_and_custom_location_has_correct_base(tmp_path,monkeypatch):
    hostile='</script><script>window.injected=true</script>'
    data={'title':hostile}
    monkeypatch.setattr(dashboard,'build_data',lambda root:data)
    path,_=dashboard.build(tmp_path,out=tmp_path/'nested/dashboard.html')
    text=path.read_text()
    assert hostile not in text
    payload=json.loads(re.search(r'<script id="site-data" type="application/json">(.*?)</script>',text,re.S).group(1))
    assert payload['title']==hostile
    # the local page links into the repository: no site pages beside it, only the repository's own documents
    assert payload['shell']['mode']=='local' and payload['shell']['self']=='nested/dashboard.html'
    assert all((Path(dashboard.ROOT)/href).is_file() for _,_,href in payload['shell']['links'])
    assert '<base href="../">' in text
    assert dashboard._url(tmp_path,tmp_path/'javascript:evil.pdf')=='./javascript%3Aevil.pdf'


def test_supplement_listed_by_a_run_is_a_part_not_a_paper(root, tmp_path):
    for name in ('synthetic_rice_heat.pdf','synthetic_rice_heat.supplement.pdf'):
        shutil.copyfile(root/'examples/papers'/name,tmp_path/name)
    assert len(dashboard.build_data(tmp_path)['papers'])==2  # no run says that the two files belong together
    out=tmp_path/'out';out.mkdir()
    for path in (root/'examples/output').glob('synthetic_rice_heat.*'):
        shutil.copyfile(path,out/path.name)
    data=dashboard.build_data(tmp_path)
    [paper]=data['papers']
    assert paper['filename']=='synthetic_rice_heat.pdf' and paper['runs'][0]['integrity_ok']
    [part]=paper['supplements']
    assert part['part']=='supplement' and part['pdf_url']=='./synthetic_rice_heat.supplement.pdf' and part['page_count']==2
    assert paper['runs'][0]['source_parts']['complete'] is True
    assert './synthetic_rice_heat.supplement.pdf' in ['./'+x for x in dashboard._linked_files(data)]


def verified_run(root, tmp_path):
    """The checked-in example run plus the `bdc verify apply` outputs placed beside its records."""
    out = tmp_path/'out'; out.mkdir()
    for path in (root/'examples/output').glob('synthetic_rice_heat.*'):
        shutil.copyfile(path, out/path.name)
    for path in (root/'examples/output/review').glob('synthetic_rice_heat.*'):
        shutil.copyfile(path, out/path.name)
    return out


def test_verification_report_and_verified_records_are_ingested(root, tmp_path):
    out = verified_run(root, tmp_path)
    [paper] = dashboard.build_data(tmp_path)['papers']
    [run] = paper['runs']
    report = json.loads((out/'synthetic_rice_heat.verification.json').read_text())
    assert run['verification']['run_id'] == report['run_id']
    assert run['verification_url'] == './out/synthetic_rice_heat.verification.json'
    assert run['verified_url'] == './out/synthetic_rice_heat.verified.jsonl'
    # the review statuses shown come from the verified records, not the pre-verification ones
    assert run['counts']['by_review'] == report['counts']['review_status_after']
    assert run['counts']['model_verified'] == report['counts']['review_status_after']['model_verified']
    assert any((r.get('common') or {}).get('review_status') == 'model_verified' for r in run['records'])
    assert run['raw_outputs']['verified'] == (out/'synthetic_rice_heat.verified.jsonl').read_text()
    linked = ['./'+x for x in dashboard._linked_files(dashboard.build_data(tmp_path))]
    assert './out/synthetic_rice_heat.verification.json' in linked
    assert './out/synthetic_rice_heat.verified.jsonl' in linked


def test_run_without_verification_reports_none(root, tmp_path):
    path, manifest, contracts = sample_run(root, tmp_path)
    run = dashboard._run(tmp_path, path, manifest, contracts)
    assert run['verification'] is None and run['verified_url'] is None
    assert run['counts']['model_verified'] == 0


def test_warnings_are_grouped_into_families_with_their_fields(root, tmp_path):
    path, manifest, contracts = sample_run(root, tmp_path)
    folder = path.parent
    (folder / 'paper.validation.json').write_text(json.dumps({
        'report_format': 1, 'argument_structure': {'flags': {}},
        'records': [{'record_id': 'rec_1', 'warnings': [
            {'code': 'VALUE_NOT_IN_SOURCE', 'severity': 'warning', 'path': 'common.gene_names',
             'message': 'common.gene_names 的取值未在证据页（±1）逐字出现'},
            {'code': 'VALUE_NOT_ON_EVIDENCE_PAGE', 'severity': 'warning', 'path': 'agent.p_value',
             'message': 'agent.p_value 的取值未在证据页（±1）逐字出现'},
        ]}, {'record_id': 'rec_2', 'warnings': [
            {'code': 'RULE_R007', 'severity': 'warning', 'path': 'common.record_kind',
             'message': '表型/环境单值观测应含一个测量值'}]}]}))
    manifest['outputs']['validation']['sha256'] = hashlib.sha256((folder / 'paper.validation.json').read_bytes()).hexdigest()
    run = dashboard._run(tmp_path, path, manifest, contracts)
    value = run['warning_summary']['groups']['value']
    assert value['count'] == 2 and value['records'] == 1
    assert list(value['by_field']) == ['common.gene_names', 'agent.p_value']
    rule = run['warning_summary']['groups']['rule']
    assert rule['count'] == 1 and run['rule_help']['R007'].startswith('表型/环境单值观测')
    assert run['rule_severity']['R007'] == '提示'
    assert sorted(run['value_warning_records']) == ['rec_1']
    assert run['counts']['value_flags'] == 2 and run['counts']['value_records'] == 1


def test_presence_policy_says_whether_the_run_checked_every_field(root, tmp_path):
    path, manifest, contracts = sample_run(root, tmp_path)  # 3.3.0: no value_presence_roles
    old = dashboard._run(tmp_path, path, manifest, contracts)
    assert old['presence_policy'] == {'selective': False, 'roles': None, 'checked': []}
    manifest['contract']['schema_version'] = '3.5.1'
    new = dashboard._run(tmp_path, path, manifest, contracts)
    assert new['presence_policy']['selective']
    assert 'entity_mention' in new['presence_policy']['roles'] and 'assertion' not in new['presence_policy']['roles']
    assert new['presence_policy']['checked']  # rendered key_role labels, not raw codes


def test_example_run_carries_warning_groups_and_the_page_offers_a_filter(root):
    data = dashboard.build_data(root)
    paper = next(p for p in data['papers'] if p['filename'] == 'synthetic_rice_qtl.pdf')
    run = paper['runs'][0]
    assert run['warning_summary']['groups']['rule']['count'] >= 1
    assert run['warning_summary']['groups']['rule']['by_code'].get('RULE_R018')
    template = (root / 'site/pages/papers.html').read_text(encoding='utf-8')
    assert '校验提示' in template  # the record filter the page renders when a run has warnings
    assert dashboard.WARNING_FAMILIES[0][1] == '取值核验'  # the value family label the page shows


def test_the_page_has_a_relations_tab_that_surfaces_the_nature(root):
    """The causal/associational line the contract draws must reach the page, not only the derived rows."""
    data = dashboard.build_data(root)
    paper = next(p for p in data['papers'] if p['filename'] == 'synthetic_rice_qtl.pdf')
    run = paper['runs'][0]
    statements = run['derived']['tables']['statements']
    assert statements and any(s.get('relation_nature') for s in statements)  # the tab lists these rows
    page = (root / 'site/pages/papers.html').read_text(encoding='utf-8')
    assert '["relations", "关系", "Relations"' in page and 'function relationsHTML(' in page
    assert all(f'{code}: ["{zh}"' in page for code, zh in (('causal', '因果'), ('associational', '相关'), ('unknown', '未知')))


def test_every_list_that_can_run_long_pages_on_its_own_key(root):
    """A tab that lists many rows pages instead of growing the page; each list keeps its own page, so paging
    one list (say the warnings under 校验与审计) never moves another."""
    import re
    page = (root / 'site/pages/papers.html').read_text(encoding='utf-8')
    keys = re.findall(r'\bpage[dr]\("([a-z]+)"', page)
    assert len(keys) == len(set(keys)), 'two lists share a page key'
    # records, relations, workflow nodes, findings, conflicts, omissions, rejections, warnings, audit, workflow
    # structure, run history
    assert set(keys) >= {'rec', 'rel', 'wfn', 'find', 'conf', 'omit', 'err', 'warn', 'aud', 'wf', 'hist'}
    # the pager windows the list on the page of its own key
    assert re.search(r'function paged\(key, items, size\) \{[^}]*st\.pages\[key\]', page)


def test_verification_in_a_review_subdirectory_is_found(root, tmp_path):
    # `bdc verify apply ... --out review/` is the documented invocation (docs/review.md).
    out = tmp_path/'out'; out.mkdir()
    for path in (root/'examples/output').glob('synthetic_rice_heat.*'):
        shutil.copyfile(path, out/path.name)
    review = out/'review'; review.mkdir()
    for path in (root/'examples/output/review').glob('synthetic_rice_heat.*'):
        shutil.copyfile(path, review/path.name)
    [run] = dashboard.build_data(tmp_path)['papers'][0]['runs']
    assert run['verification'] is not None
    assert run['verification_url'] == './out/review/synthetic_rice_heat.verification.json'
    assert run['counts']['model_verified'] == 17


def test_tampered_verified_records_are_flagged(root, tmp_path):
    out = verified_run(root, tmp_path)
    (out/'synthetic_rice_heat.verified.jsonl').write_text('{}\n')
    [run] = dashboard.build_data(tmp_path)['papers'][0]['runs']
    assert any('语义校验' in n and '哈希' in n for n in run['notes'])
    assert not run['integrity_ok']


