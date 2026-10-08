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
    payload=re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>',text,re.S).group(1)
    assert json.loads(payload)==data
    assert '<base href="../">' in text
    assert dashboard._url(tmp_path,tmp_path/'javascript:evil.pdf')=='./javascript%3Aevil.pdf'
