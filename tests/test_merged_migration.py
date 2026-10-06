"""merged v2 imports must preserve evidence, context boundaries and every source leaf."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from breeding_contract import ContractError, resolve_schema, validate_record
from breeding_contract.legacy import _concrete, _leaves, _norm
from breeding_contract.mappings import TRANSFER_STATUSES, coverage_summary, match_entry
from breeding_contract.merged import migrate_merged_file
from breeding_contract.runtime_schemas import runtime_errors
from breeding_contract.util import load_json, load_yaml
from conftest import read_jsonl, run_bdc


@pytest.fixture
def source(root):
    return load_json(root / 'sources/merged_v2/breeding_jsonl_example_v2.json')


def migrate(tmp_path, value, **kwargs):
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    result = migrate_merged_file(path, tmp_path / 'out', **kwargs)
    return {'records':read_jsonl(Path(result['outputs']['records'])),
            'errors':read_jsonl(Path(result['outputs']['errors'])),
            'residue':load_json(result['outputs']['residue']),
            'report':load_json(result['outputs']['report'])}


def observations(result):
    return {r['common']['source_record_id']:r for r in result['records']
            if result['report']['record_sources'][r['common']['record_id']]['source_path'].startswith('observations[')}


def issue_codes(result):
    return {i['code'] for e in result['errors'] for i in e.get('issues', [])}


def test_archive_example_and_mapping(root, source):
    schema=load_json(root/'sources/merged_v2/breeding_jsonl_schema_v2.json')
    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema).is_valid(source)
    template=load_json(root/'sources/merged_v2/breeding_jsonl_template_v2.json')
    assert not Draft202012Validator(schema).is_valid(template)
    coverage=coverage_summary(root, load_yaml(root/'mappings/merged_to_current.yaml'))
    assert coverage['leaves']==1022 and 'uncovered' not in coverage['by_status']


def test_example_import_has_valid_atomic_records_and_full_accounting(root, tmp_path, source):
    result=migrate(tmp_path,source,page_offset=2220)
    assert len(result['records'])==18 and len(result['errors'])==14
    assert all(validate_record(r).valid for r in result['records'])
    assert all(r['common']['review_status']=='pending_review' for r in result['records'])
    assert all('MERGED_MIGRATED' in r['common']['qc_failure_codes'] for r in result['records'])
    assert not runtime_errors('migration_report',result['report'])
    assert all(not runtime_errors('error_record',e) for e in result['errors'])
    consumed={r['path'] for r in result['report']['consumed_paths']}
    residue={r['path'] for r in result['residue']['unconsumed']}
    mapping=load_yaml(root/'mappings/merged_to_current.yaml')
    for path,_ in _leaves(source):
        assert _concrete(path) in consumed|residue, path
        if _concrete(path) in consumed:
            entry=match_entry(mapping['entries'],_norm(path))
            assert entry and entry['status'] in TRANSFER_STATUSES|{'control'}, path
    # Input-only agent state, transform artifacts and incomplete hashes remain recoverable.
    assert any(p.startswith('transform.') for p in residue)
    assert 'provenance.integrity.source_file_hash' in residue
    assert any(r['path'].endswith('text_snippet') and isinstance(r['value'], str) and '...' in r['value']
               for r in result['residue']['unconsumed'])
    assert 'assets[2].related_dataset_id' in residue
    assert all(r['common']['dataset_id']==source['doc_meta']['dataset_id'] for r in result['records'])


def test_sample_assay_and_evidence_are_explicit(tmp_path,source):
    result=migrate(tmp_path,source,page_offset=2220)
    obs=observations(result)
    assert len(obs)==4
    common=obs['obs:ric:trs01']['common']
    assert common['biological_replicate_id']=='bio-rep-1'
    assert common['technical_replicate_id']=='tech-1'
    assert common['sampling_time']=='2022-08-15T14:30:00+08:00'
    assert common['observation_time']=='2022-09-01T04:00:00Z'
    assert common['source_page']==10
    assert 'source_table_figure' not in common  # p24 is a paragraph, not a table.
    assert common['gene_ids']==['LOC_Os03g0229400']
    assert obs['obs:ric:trs01']['omics']['instrument_model']=='NovaSeq 6000'
    assert obs['obs:ric:trs01']['agent']['confidence_interval']=='[1.42, 2.24]'
    assert 'technical_replicate_id' not in obs['obs:ric:gt01']['common']
    assert 'sample_name' not in obs['obs:ric:ph01']['common']
    assert obs['obs:ric:ph01']['common']['source_locator'].endswith('table=tbl2;row=93-11;col=PH_E1')


def test_no_offset_does_not_assume_physical_pages(tmp_path,source):
    result=migrate(tmp_path,source)
    assert not observations(result)
    assert all(r['common']['record_kind']=='asset_manifest' for r in result['records'])


def test_truncated_checksums_are_rejected_without_repair(tmp_path,source):
    result=migrate(tmp_path,source,page_offset=2220)
    assets=[e for e in result['errors'] if e.get('source_path','').startswith('assets[')]
    assert len(assets)==2
    assert all(any(i['path']=='common.asset_sha256' for i in e['issues']) for e in assets)
    assert {e['record']['common']['asset_sha256'] for e in assets}=={'f6e0ba80c14e...','7c3d...'}


@pytest.mark.parametrize('mutation,expected',[
    ('duplicate_sample','MERGED_REFERENCE_AMBIGUOUS'),
    ('assay_membership','MERGED_SAMPLE_ASSAY_MISMATCH'),
    ('conflicting_measurement','MERGED_FIELD_CONFLICT'),
    ('conflicting_context','MERGED_FIELD_CONFLICT'),
])
def test_ambiguous_contexts_are_rejected(tmp_path,source,mutation,expected):
    if mutation=='duplicate_sample':
        source['breed_entities']['omics_samples'].append(copy.deepcopy(source['breed_entities']['omics_samples'][0]))
    elif mutation=='assay_membership':
        source['breed_entities']['omics_experiments'][0]['sample_ids']=['some-other-sample']
    elif mutation=='conflicting_measurement':
        source['observations'][3]['measurement']={'name':'log2FC','value':99}
    else:
        source['breed_entities']['omics_samples'][0]['material_ref']='different-material'
    result=migrate(tmp_path,source,page_offset=2220)
    assert expected in issue_codes(result)
    assert 'obs:ric:trs01' not in observations(result)


@pytest.mark.parametrize('change',['naive_timestamp','invalid_probability','reversed_interval','wrong_dosage'])
def test_stricter_target_constraints_still_apply(tmp_path,source,change):
    if change=='naive_timestamp': source['observations'][3]['observation_time']='2022-09-01T12:00:00'
    if change=='invalid_probability': source['observations'][3]['statistic']['p_value']=1.5
    if change=='reversed_interval': source['observations'][3]['statistic']['confidence_interval']=[2.24,1.42]
    if change=='wrong_dosage': source['observations'][1]['genotype']['dosage']=3
    result=migrate(tmp_path,source,page_offset=2220)
    identifier='obs:ric:gt01' if change=='wrong_dosage' else 'obs:ric:trs01'
    assert identifier not in observations(result)
    assert result['errors']


def test_unknown_and_multivalued_omics_leaves_stay_in_residue(tmp_path,source):
    feature=source['observations'][3]['omics_feature']
    feature['go_term']=['GO:0009733','GO:0009651']
    feature['unrecognized_metric']=123
    feature['other_assay']={'raw_count':999}
    result=migrate(tmp_path,source,page_offset=2220)
    record=observations(result)['obs:ric:trs01']
    assert 'go_term' not in record['omics']
    residual={r['path']:r['value'] for r in result['residue']['unconsumed']}
    assert residual['observations[3].omics_feature.go_term']==feature['go_term']
    assert residual['observations[3].omics_feature.unrecognized_metric']==123
    assert residual['observations[3].omics_feature.other_assay.raw_count']==999
    assert record['omics']['raw_count']==584


def test_ids_survive_observation_reordering(tmp_path,source):
    first=migrate(tmp_path,source,page_offset=2220)
    source['observations'].reverse()
    second=migrate(tmp_path,source,page_offset=2220)
    ids=lambda x:{k:r['common']['record_id'] for k,r in observations(x).items()}
    assert ids(first)==ids(second)


def test_unit_row_resolves_parent_in_either_order(tmp_path,source):
    unit={'record_id':'unit-001','schema_version':'v2.0.0','record_kind':'observation',
          'record_parent_id':source['record_id'],'observations':[source['observations'][3]]}
    source['observations']=[]
    first=migrate(tmp_path,[unit,source],page_offset=2220)
    second=migrate(tmp_path,[source,unit],page_offset=2220)
    for result in [first,second]:
        record=observations(result)['obs:ric:trs01']
        assert record['common']['biological_replicate_id']=='bio-rep-1'
        meta=result['report']['record_sources'][record['common']['record_id']]
        assert meta['source_parent_id']==source['record_id']
        assert meta['source_document_id']=='unit-001'
    assert set(observations(first))==set(observations(second))


def test_unit_without_parent_is_preserved_and_rejected(tmp_path,source):
    unit={'record_id':'unit-001','schema_version':'v2.0.0','record_kind':'observation',
          'record_parent_id':'missing-parent','observations':[source['observations'][3]]}
    result=migrate(tmp_path,unit,page_offset=2220)
    assert not result['records'] and 'MERGED_PARENT_UNRESOLVED' in issue_codes(result)
    assert result['residue']['unconsumed'][0]['value']==unit
    assert all(not runtime_errors('error_record',e) for e in result['errors'])


def test_unit_cannot_mix_different_papers(tmp_path, source):
    unit={'record_id':'unit-001','schema_version':'v2.0.0','record_kind':'observation',
          'record_parent_id':source['record_id'],'observations':[source['observations'][3]],
          'doc_meta':copy.deepcopy(source['doc_meta'])}
    unit['doc_meta']['doi']='10.0000/different-paper'
    source['observations']=[]
    result=migrate(tmp_path,[source,unit],page_offset=2220)
    assert not observations(result)
    assert 'MERGED_PARENT_SOURCE_CONFLICT' in issue_codes(result)


def test_invalid_json_and_older_target_version_fail_cleanly(tmp_path, root):
    path=tmp_path/'bad.json'
    path.write_text('{"value":NaN}', encoding='utf-8')
    with pytest.raises(ContractError, match='invalid merged JSON'):
        migrate_merged_file(path,tmp_path/'out')
    with pytest.raises(ContractError, match='>= 3.3.0'):
        migrate_merged_file(root/'sources/merged_v2/breeding_jsonl_example_v2.json',tmp_path/'out',version='3.2.0')


def test_duplicate_records_do_not_overwrite_original_lineage(tmp_path,source):
    result=migrate(tmp_path,[source,source],page_offset=2220)
    assert len(result['records'])==18
    assert all(s['input_line']==1 for s in result['report']['record_sources'].values())
    assert any(e['stage']=='dataset' for e in result['errors'])


def test_source_errors_are_auditable_and_cli_accepts_jsonl(root,tmp_path,source):
    source['schema_version']='v1.0.0'
    result=migrate(tmp_path,source,page_offset=2220)
    assert not result['records'] and 'MERGED_SOURCE_SCHEMA' in issue_codes(result)
    assert result['residue']['unconsumed'][0]['value']==source
    cli=run_bdc(root,'migrate','merged',str(root/'sources/merged_v2/breeding_jsonl_example_v2.jsonl'),
                '--out',str(tmp_path/'cli'),'--page-offset','2220')
    assert json.loads(cli.stdout)['records']==18


def test_new_fields_are_additive_and_in_extraction_profile(root):
    old=resolve_schema('3.2.0',root)
    new=resolve_schema('3.3.0',root)
    old_fields={f['path']:f for f in old.fields}
    new_fields={f['path']:f for f in new.fields}
    assert all(new_fields[p]==f for p,f in old_fields.items())
    added=set(new_fields)-old_fields.keys()
    assert added=={'common.biological_replicate_id','common.technical_replicate_id','common.sampling_time'}
    assert added <= {f['path'] for f in new.profile('pdf_extraction')['fields']}
    assert all(new_fields[p]['maturity']=='provisional' for p in added)
