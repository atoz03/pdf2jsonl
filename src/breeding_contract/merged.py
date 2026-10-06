"""Import merged v2 documents and unit rows while preserving the atomic contract.

The legacy paper-content routes are reused. New observation/asset routes follow
merged_to_current.yaml and join sample/assay context only through explicit IDs.
Unconverted values and rejected inputs remain in the migration outputs.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from . import GENERATOR_VERSION
from .api import resolve_schema
from .ids import build_locator, build_span, stable_record_id
from .legacy import EMPTY, LegacyMigrator, _concrete, _item_id, _leaves, _norm
from .mappings import match_entry
from .paths import repo_root
from .util import (ContractError, dumps_json, dumps_jsonl, load_json, load_yaml,
                   parse_semver, sha256_file, utc_now)

OBSERVATION_KINDS = {"phenotype": "phenotype_observation", "environment": "environment_observation",
                     "genotype": "genotype_observation", "omics_feature": "observation"}


def _issue(code, path, message):
    return {"code": code, "severity": "error", "path": path, "message": message}


def _read_inputs(path):
    text = path.read_text(encoding="utf-8-sig").strip()

    def invalid_constant(value):
        raise ValueError(f"non-JSON constant {value}")

    try:
        try:
            value = json.loads(text, parse_constant=invalid_constant)
        except json.JSONDecodeError:
            return [json.loads(line, parse_constant=invalid_constant) for line in text.splitlines() if line.strip()]
        return value if isinstance(value, list) else [value]
    except (ValueError, TypeError) as exc:
        raise ContractError(f"invalid merged JSON/JSONL input: {exc}") from exc


class MergedMigrator(LegacyMigrator):
    def evidence_from_span(self, t, keys, sections):
        ev, codes = super().evidence_from_span(t, keys, sections)
        if 'quote' not in ev:
            t.used.discard(keys + ('text_snippet',))
        if 'page' not in ev:
            t.used.discard(keys + ('page',))
            span = t.doc
            for key in keys:
                span = span[key]
            section = sections.get(span.get('section_id'))
            if section:
                t.used.discard(('doc_meta', 'document_sections', section[0], 'page'))
        return ev, codes

    def document_values(self, t):
        values, notes = super().document_values(t)
        # merged doc_meta.field contains research topics as well as crop names.
        primary = t.doc.get("doc_meta", {}).get("crop_primary")
        topics = t.doc.get("doc_meta", {}).get("field") or []
        crops = {self._code("crop_name", v) for v in topics if isinstance(v, str)} - {None}
        if primary:
            values["common.crop_name"] = self._code("crop_name", primary) or primary
            t.get("doc_meta", "crop_primary")
        elif len(crops) == 1:
            values["common.crop_name"] = crops.pop()
            notes = [n for n in notes if not n.startswith("doc_meta.field")]
        # Keep unrecognized research-topic values visible in the residue.
        t.used.discard(("doc_meta", "field"))
        t.used.discard(("doc_meta", "affiliations"))
        for i, obj in t.items("doc_meta", "affiliations"):
            if obj.get("name") in values.get("common.source_affiliations", []):
                t.get("doc_meta", "affiliations", i, "name")
        for key in ("source_id", "source_type", "source_uri", "dataset_id", "dataset_version", "study_id",
                    "trial_id", "data_modality", "linked_modalities"):
            v = t.get("doc_meta", key)
            if v not in EMPTY:
                values[f"common.{key}"] = v
        if values["common.source_id"].startswith("urn:legacy-v1:"):
            values["common.source_id"] = "urn:merged-v2:" + str(t.doc["record_id"])
        # A rejected hash is retained, never considered consumed merely because it was read.
        if "common.source_file_sha256" not in values:
            t.used.discard(("provenance", "integrity", "source_file_hash"))
        return values, notes

    def record(self, kind, doc_values, ev, fields, section, qc, ordinal):
        rec = super().record(kind, doc_values, ev, fields, section, qc, ordinal)
        common = rec["common"]
        common["qc_failure_codes"] = [x.replace("LEGACY_", "MERGED_", 1) for x in common["qc_failure_codes"]]
        common["qc_rule_set_version"] = f"{self.rc.name}@{self.rc.version}+merged-migration@{GENERATOR_VERSION}"
        if "common.source_record_id" in fields:
            item_id = fields["common.source_record_id"]
            locator = build_locator(page=ev.get("page"), section=section,
                                    table=common.get("source_table_figure"), row=common.get("source_table_row_key"),
                                    col=common.get("source_table_column_key")) or "document"
            common["source_locator"] = locator
            common["record_id"] = stable_record_id(common["source_id"], kind, f"merged:{item_id}", ev.get("quote"))
        if not self.dataset_id and "common.dataset_id" in fields:
            common["dataset_id"] = fields["common.dataset_id"]
        return rec

    def _convert(self, target, value):
        if target == "common.observation_time" and isinstance(value, str):
            try:
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if timestamp.tzinfo is not None:
                    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                pass
            return value  # The target validator rejects invalid/naive timestamps.
        if target == "agent.confidence_interval" and isinstance(value, list):
            if len(value) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value) \
                    and value[0] <= value[1]:
                return json.dumps(value, ensure_ascii=False)
            return value  # Invalid array shape is rejected by the string field schema.
        spec = self.fields[target]
        if spec['type'] == 'integer' and isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            return int(value)
        if spec['type'] == 'array_string' and isinstance(value, str):
            return [value]
        if spec['type'] == 'string' and isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            return value[0]
        return value

    def copy_fields(self, t, keys, fields, errors):
        node = t.doc
        for key in keys:
            node = node[key]
        for path, raw in _leaves(node, keys):
            normalized = _norm(path)
            # Evidence must be localized through evidence_from_span, never blindly copied.
            if "evidence_spans" in path:
                continue
            entry = match_entry(self.mapping['entries'], normalized)
            target = (entry or {}).get('target')
            if 'omics_feature' in path and normalized.startswith('observations[].omics_feature.'):
                if len(path) != 4:
                    continue  # A nested object's coincidentally named key is not a feature field.
                target = 'common.gene_ids' if path[-1] == 'gene_id' else f"omics.{path[-1]}"
                if target not in self.fields or (target != 'common.gene_ids' and self.fields[target]['availability'] != 'D'):
                    continue
            elif not entry or entry['status'] not in {'mapped', 'partial', 'transformed', 'merged'}:
                continue
            if target not in self.fields or self.fields[target]['availability'] == 'I':
                continue
            value = self._convert(target, raw)
            # Do not collapse a many-valued source into a scalar field.
            if isinstance(value, list) and self.fields[target]['type'] == 'string' and target != 'agent.confidence_interval':
                continue
            if target in fields and fields[target] != value:
                errors.append(_issue('MERGED_FIELD_CONFLICT', _concrete(path),
                                     f"{target} conflicts with another explicitly supplied value"))
                continue
            fields[target] = value
            t.get(*path)

    def additional_records(self, t, doc_values, sections, emit):
        # The inherited route emits numeric key results; preserve other members of that object.
        for i, analysis in t.items('analyses'):
            key = ('analyses', i, 'key_results')
            if key in t.used:
                t.used.discard(key)
                for name, value in (analysis.get('key_results') or {}).items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        t.get(*key, name)
        for name in ('record_kind', 'record_parent_id', 'schema_version'):
            t.get(name)
        indexes = {}
        for group, id_key in [('omics_samples', 'sample_id'), ('omics_experiments', 'omics_experiment_id')]:
            index = {}
            for i, obj in t.items('breed_entities', group):
                key = obj.get(id_key)
                if key:
                    index.setdefault(key, []).append((i, obj))
            indexes[group] = index
        for i, obj in t.items('observations'):
            source = f'observations[{i}]'
            kind = OBSERVATION_KINDS.get(t.get('observations', i, 'observation_type'))
            if not kind:
                continue  # The input schema already rejects unknown kinds.
            fields, errors, codes = {}, [], []
            self.copy_fields(t, ('observations', i), fields, errors)
            for ref_key, group in [('sample_ref', 'omics_samples'), ('assay_ref', 'omics_experiments')]:
                ref = obj.get(ref_key)
                if not ref:
                    continue
                matches = indexes[group].get(ref, [])
                if not matches:
                    codes.append('MERGED_EXTERNAL_REFERENCE_UNRESOLVED')
                    continue
                if len(matches) != 1:
                    errors.append(_issue('MERGED_REFERENCE_AMBIGUOUS', source+'.'+ref_key, f'duplicate context ID: {ref}'))
                    continue
                idx, context = matches[0]
                # Reject disagreeing contexts rather than picking one interpretation.
                context_fields = {}
                self.copy_fields(t, ('breed_entities', group, idx), context_fields, errors)
                for target, value in context_fields.items():
                    if target in fields and fields[target] != value:
                        errors.append(_issue('MERGED_FIELD_CONFLICT', source+'.'+ref_key,
                                             f'{target} differs between observation and referenced context'))
                    else:
                        fields[target] = value
                if group == 'omics_experiments' and obj.get('sample_ref') and context.get('sample_ids'):
                    t.get('breed_entities', group, idx, 'sample_ids')
                    if obj['sample_ref'] not in context['sample_ids']:
                        errors.append(_issue('MERGED_SAMPLE_ASSAY_MISMATCH', source+'.assay_ref',
                                             'referenced assay does not list the observation sample'))
            ev, evidence_codes, section = {}, ['MERGED_NO_EVIDENCE'], None
            for j, span in t.items('observations', i, 'evidence_spans'):
                ev, evidence_codes = self.evidence_from_span(t, ('observations', i, 'evidence_spans', j), sections)
                section = span.get('section_id')
                if 'page' in ev and 'quote' in ev:
                    for key, target in [('block_id','common.source_table_figure'), ('table_row_key','common.source_table_row_key'),
                                        ('table_column_key','common.source_table_column_key')]:
                        if key == 'block_id' and span.get('block_type') not in ('表', '图', 'table', 'figure'):
                            continue
                        v = t.get('observations', i, 'evidence_spans', j, key)
                        if v not in EMPTY:
                            fields[target] = v
                    offsets = span.get('char_span')
                    if isinstance(offsets, list) and len(offsets) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in offsets) \
                            and 0 <= offsets[0] <= offsets[1]:
                        t.get('observations', i, 'evidence_spans', j, 'char_span')
                        fields['common.source_span'] = build_span(ev['page'], *offsets)
                    break
            emit(kind, ev, fields, section, codes + evidence_codes, source, extra_errors=errors)
        for i, obj in t.items('assets'):
            fields, errors = {}, []
            self.copy_fields(t, ('assets', i), fields, errors)
            emit('asset_manifest', {}, fields, None, [], f'assets[{i}]', extra_errors=errors)


def _inherit_context(doc, parent):
    result = copy.deepcopy(doc)
    for key in ('doc_meta', 'record_info', 'provenance'):
        result[key] = {**copy.deepcopy(parent.get(key) or {}), **result.get(key, {})}
    entities = result.setdefault('breed_entities', {})
    for key in ('omics_samples', 'omics_experiments'):
        if key not in entities and key in parent.get('breed_entities', {}):
            entities[key] = copy.deepcopy(parent['breed_entities'][key])
    return result


def migrate_merged_file(path, out_dir, version='latest', page_offset=None, dataset_id=None,
                        source_file_sha256=None, root=None):
    root, path, out_dir = repo_root(root), Path(path), Path(out_dir)
    rc = resolve_schema(version, root)
    if parse_semver(rc.version.split('-')[0]) < (3, 3, 0):
        raise ContractError(f'merged migration targets contract >= 3.3.0 (got {rc.version})')
    mapping_path = root / 'mappings/merged_to_current.yaml'
    mapping = load_yaml(mapping_path)
    source_schema_path = root / mapping['source']['file']
    source_validator = Draft202012Validator(load_json(source_schema_path))
    started = utc_now()
    run_id = 'mig_' + started.strftime('%Y%m%dT%H%M%SZ') + '_' + sha256_file(path)[:8]
    migrator = MergedMigrator(rc, mapping, page_offset, dataset_id, source_file_sha256, run_id)
    docs = _read_inputs(path)
    parents = {}
    for n, doc in enumerate(docs, 1):
        if isinstance(doc, dict) and doc.get('record_kind') == 'document' and isinstance(doc.get('record_id'), str):
            parents.setdefault(doc['record_id'], []).append((n, doc))
    records, rejected, residue, sources, reviews, consumed, notes = [], [], [], {}, {}, [], []
    for n, original in enumerate(docs, 1):
        source_errors = [_issue('MERGED_SOURCE_SCHEMA', '.'.join(map(str,e.absolute_path)), e.message)
                         for e in source_validator.iter_errors(original)]
        doc = original
        if not source_errors and doc.get('record_kind') != 'document':
            matches = parents.get(doc.get('record_parent_id'), [])
            if len(matches) != 1 or not source_validator.is_valid(matches[0][1]):
                source_errors.append(_issue('MERGED_PARENT_UNRESOLVED', 'record_parent_id',
                                            'a unique valid parent document must be supplied in the same input'))
            else:
                parent = matches[0][1]
                for identity in ('source_id', 'doi'):
                    child_source = doc.get('doc_meta', {}).get(identity)
                    parent_source = parent.get('doc_meta', {}).get(identity)
                    if child_source and parent_source and child_source != parent_source:
                        source_errors.append(_issue('MERGED_PARENT_SOURCE_CONFLICT', 'doc_meta.' + identity,
                                                    'child and parent name different sources'))
                if not source_errors:
                    doc = _inherit_context(doc, parent)
        if not source_errors and doc['record_kind'] in ('transform', 'tool_spec'):
            source_errors.append(_issue('MERGED_KIND_RETAINED', 'record_kind',
                                        'derived views and skill runtime state are retained, not emitted as paper facts'))
        if source_errors:
            rejected.append({'error_format':1,'stage':'migration','code':'MERGED_SOURCE_INVALID','input_line':n,
                             'message':'merged input cannot be migrated','issues':source_errors,
                             'detail':{'source_record':original}})
            residue.append({'input_line':n,'path':'$','value':original,'mapping':{'status':'unmapped','note_zh':'输入不满足迁移条件，完整保留。'}})
            continue
        res = migrator.migrate(doc)
        records.extend(res['records'])
        rejected.extend({**e,'input_line':n} for e in res['rejected'])
        # Account against the actual source row, not a virtual document with inherited context.
        original_paths = {_concrete(p) for p,_ in _leaves(original)}
        residue.extend({**r,'input_line':n} for r in res['residue'] if r['path'] in original_paths)
        consumed.extend({'input_line':n,'path':p} for p in res['consumed_paths'] if p in original_paths)
        reviews.update(res['review_candidates'])
        notes.extend(res['notes'])
        for rid, sp in res['record_sources'].items():
            meta={'input_line':n,'source_path':sp,'source_document_id':doc['record_id']}
            if doc.get('record_parent_id'):
                meta['source_parent_id']=doc['record_parent_id']
            if (iid := _item_id(doc, sp)):
                meta['source_item_id']=iid
            sources.setdefault(rid, meta)
    bad = {}
    for idx, issue in migrator.validator.validate_dataset(records):
        if issue.severity == 'error':
            bad.setdefault(idx, []).append(issue.to_dict())
    for idx in sorted(bad, reverse=True):
        rejected.append({'error_format':1,'stage':'dataset','code':'DATASET_RULE','message':bad[idx][0]['message'],
                         'issues':bad[idx],'record':records.pop(idx)})
    out_dir.mkdir(parents=True, exist_ok=True)
    stem=path.stem
    outs={k:out_dir/f'{stem}.{suffix}' for k,suffix in [('records','migrated.jsonl'),('errors','migrated.errors.jsonl'),
                                                       ('residue','residue.json'),('report','migration.json')]}
    outs['records'].write_text(dumps_jsonl(records), encoding='utf-8')
    outs['errors'].write_text(dumps_jsonl(rejected), encoding='utf-8')
    outs['residue'].write_text(dumps_json({'residue_format':1,'source':path.name,'unconsumed':residue,'review_candidates':reviews}),encoding='utf-8')
    counts={'records':len(records),'rejected':len(rejected),'residue_leaves':len(residue),'review_candidates':len(reviews)}
    report={'migration_format':1,'run_id':run_id,'created_at':started.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'source':{'file_name':path.name,'sha256':sha256_file(path),'documents':len(docs),'schema_version':'v2.0.0'},
            'contract':rc.identity(),'mapping':{'id':mapping['id'],'sha256':sha256_file(mapping_path)},
            'source_schema_sha256':sha256_file(source_schema_path),
            'options':{'page_offset':page_offset,'dataset_id':dataset_id,'source_file_sha256':source_file_sha256},
            'counts':counts,'notes':sorted(set(notes)),'consumed_paths':consumed,
            'record_sources':{r['common']['record_id']:sources[r['common']['record_id']] for r in records},
            'outputs':{k:{'file':p.name,'sha256':sha256_file(p)} for k,p in outs.items() if k!='report'},
            'tooling':{'breeding_contract':GENERATOR_VERSION}}
    outs['report'].write_text(dumps_json(report),encoding='utf-8')
    return {'outputs':{k:str(v) for k,v in outs.items()},**counts}
