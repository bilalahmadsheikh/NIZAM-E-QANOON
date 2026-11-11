"""Review-bound same-issued-instrument print variants; never text equality.

Initial scope is only the paired9361 amendments. Default is read-only; --trial
executes the exact write and rolls back. --apply requires an independent,
hash-bound implementation approval. Published targets and source text never
change. Ordinary replay of a standing disposition is deliberately refused.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from nizam.storage.db import connect
from tools.second_parser_release import RELEASE_FINGERPRINT_SQL

SCHEMA='nizam.expression_source_variant/1'
METHOD='nizam.expression_source_variant/1'
CHOICE='retain-print-variant-link-existing'
PAIRS={3:712,4:518,5:727,6:9391,7:985,8:933,9:3591}
META=('jurisdiction','kind','year','number','document_id','source_observation_id','expression_ordinal','source_sha256')
REVIEW_FILES=('tools/expression_source_variants.py','nizam/storage/legal_write.py',
 'tools/materialize_multi_instrument.py','tests/test_expression_source_variants.py',
 'docs/SCHEMA.md','docs/EXPRESSION-SOURCE-VARIANTS.md')

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def validate_approval(approval,matrix_path):
 required=set(REVIEW_FILES)|{str(matrix_path)}
 hashes=approval.get('approved_hashes')or{}
 if (approval.get('approved')is not True or not approval.get('reviewer')
     or approval.get('remaining_findings')!=[] or not required<=set(hashes)):
  raise ValueError('Incomplete independent implementation/matrix approval')
 for file,h in hashes.items():
  if hashlib.sha256(Path(file).read_bytes()).hexdigest()!=h:raise ValueError(f'Audit drift: {file}')

def raw_digest(cur,document_id):
 cur.execute('SELECT row_to_json(t)FROM text_block t WHERE document_id=%s ORDER BY id',(document_id,))
 rows=[x[0]for x in cur.fetchall()]
 return dict(block_count=len(rows),sha256=digest(rows))

def unchanged_source_state(cur):
 """Small scoped ledger fingerprint, including raw bytes and existing curations."""
 state={}
 for table,column in [('text_block','document_id'),('block_assignment_set','source_observation_id'),
                      ('segmentation_curation_patch','source_observation_id')]:
  cur.execute(f'SELECT row_to_json(t)FROM {table} t WHERE {column}=%s ORDER BY id',(9361 if table=='text_block' else 13533,))
  state[table]=[x[0]for x in cur.fetchall()]
 cur.execute('''SELECT row_to_json(p) FROM provision_block p JOIN block_assignment_set s
                ON s.id=p.assignment_set_id WHERE s.source_observation_id=13533
                ORDER BY p.assignment_set_id,p.block_id''')
 state['provision_block']=[x[0]for x in cur.fetchall()]
 return digest(state)

def validate_pair(p,source,target,*,copy_released,target_released,source_historical=False,target_historical=False):
 if p.get('schema')!=SCHEMA or p.get('method')!=METHOD:
  raise ValueError('Unknown source-variant contract')
 s,t=p['source'],p['canonical'];ordinal=s['expression_ordinal']
 if ((s['document_id'],s['source_observation_id'])!=(9361,13533)
     or PAIRS.get(ordinal)!=t['document_id']or t['expression_ordinal']!=0):
  raise ValueError('Pair outside independently reviewed9361 scope')
 for key in(s,t):
  if any(key.get(k)!=key['metadata'].get(k)for k in('document_id','source_observation_id','expression_ordinal')):
   raise ValueError('Outer key does not match reviewed metadata')
  if key.get('source_pdf_sha256')!=key['metadata']['source_sha256']:
   raise ValueError('Reviewed PDF hash does not match source metadata')
 if any(source.get(k)!=s['metadata'].get(k)for k in META)or any(target.get(k)!=t['metadata'].get(k)for k in META):
  raise ValueError('Source/canonical issued metadata changed')
 if (source['source_observation_id'],source['expression_ordinal'])==(target['source_observation_id'],target['expression_ordinal']):
  raise ValueError('Self link')
 if copy_released or not target_released or target.get('duplicate_of')is not None:
  raise ValueError('Released copy, unreleased canonical or duplicate chain')
 if source_historical or target_historical:
  raise ValueError('Historical legal versions are not print variants')
 identity=p['printed_issued_identity']
 if any(source[k]!=identity[k]or target[k]!=identity[k]for k in('jurisdiction','kind','year')):
  raise ValueError('Jurisdiction/kind/year mismatch')
 for side,actual in [('source',source),('canonical',target)]:
  if actual['number']!=identity['number']:
   anomaly=p.get('metadata_number_anomaly')or{}
   if not(side=='canonical'and ordinal==6 and actual['number']is None
          and identity['number']=='I'and anomaly.get('canonical_printed_number')=='I'
          and anomaly.get('basis')):
    raise ValueError('Issued number mismatch')
 c=p['classification']
 if (c.get('relation')!='same_issued_instrument_print_variant'
     or c.get('actual_legal_version')is not False or c.get('partial_copy')is not False
     or c.get('different_commencement')is not False
     or c.get('comparison_complete_for_issued_identity')is not True):
  raise ValueError('Unknown/legal-version/incomplete source classification')
 if not p.get('comparison')or not p['comparison'].get('differences_classified'):
  raise ValueError('Missing paired comparison')
 if not all(p['comparison'].get(k)is True for k in('no_word_equivalence_claim','no_current_version_equivalence_claim','no_target_text_substitution')):
  raise ValueError('Variant link must not assert word/current-version equivalence or substitute text')
 if not p.get('reviewed_files')or not s.get('spans')or not t.get('spans'):
  raise ValueError('Missing image/span evidence')
 decision=p.get('owner_decision')or{}
 if (decision.get('document_id'),decision.get('question_id'))!=(9361,'q5'):
  raise ValueError('Missing pair-bound owner decision')

def read_identity(cur,key,*,lock=False):
 cur.execute('''SELECT row_to_json(i) FROM instrument i WHERE source_observation_id=%s
                AND expression_ordinal=%s AND is_active'''+(' FOR UPDATE OF i'if lock else''),
             (key['source_observation_id'],key['expression_ordinal']))
 rows=cur.fetchall()
 if len(rows)!=1:raise ValueError('Missing or ambiguous active source key')
 i=rows[0][0]
 cur.execute('SELECT EXISTS(SELECT 1 FROM v_release_instrument WHERE id=%s)',(i['id'],));released=cur.fetchone()[0]
 cur.execute('''SELECT row_to_json(m) FROM instrument_expression_manifest m WHERE
                source_observation_id=%s AND expression_ordinal=%s AND is_active'''+(' FOR UPDATE OF m'if lock else''),
             (key['source_observation_id'],key['expression_ordinal']))
 rows=cur.fetchall()
 if len(rows)>1:raise ValueError('Ambiguous source manifest')
 manifest=rows[0][0]if rows else None
 historical=bool(manifest and manifest.get('historical_validity'))
 return i,released,manifest,historical

def apply_matrix(cur,matrix,*,write=False):
 from tools.materialize_multi_instrument import owner_decision_answer
 if matrix.get('schema')!='nizam.expression_source_variant_matrix/1':raise ValueError('Matrix schema')
 pairs=matrix['pairs']
 if sorted(p['source']['expression_ordinal']for p in pairs)!=list(PAIRS):raise ValueError('Exact seven-pair matrix required')
 answer=owner_decision_answer(matrix['owner_decision'],9361)
 if (answer['choice']!=CHOICE or answer['card']['recommended']!=CHOICE
     or matrix['pair_matrix_sha256']not in answer['card']['question']
     or answer['card_sha256']!=hashlib.sha256(json.dumps(answer['card'],sort_keys=True).encode()).hexdigest()):
  raise ValueError('Owner decision does not bind the directional matrix')
 if digest(pairs)!=matrix['pair_matrix_sha256']:raise ValueError('Pair matrix drift')
 for p in pairs:
  if p['owner_decision']!=matrix['owner_decision']:raise ValueError('Pair decision drift')
  for name,h in p['reviewed_files'].items():
   path=Path(name).resolve()
   if not path.is_relative_to(Path.cwd().resolve())or hashlib.sha256(path.read_bytes()).hexdigest()!=h:
    raise ValueError('Paired source artifact drift')
  # Stable lock order includes canonical source keys, not only source copies.
 keys=sorted({(p[side]['source_observation_id'],p[side]['expression_ordinal'])for p in pairs for side in('source','canonical')})
 identities={k:read_identity(cur,dict(source_observation_id=k[0],expression_ordinal=k[1]),lock=True)for k in keys}
 checked_docs={}
 changes=[]
 for p in pairs:
  s,t=p['source'],p['canonical']
  source,sreleased,manifest,shist=identities[(s['source_observation_id'],s['expression_ordinal'])]
  target,treleased,target_manifest,thist=identities[(t['source_observation_id'],t['expression_ordinal'])]
  if not p.get('eligible',True):
   changes.append(dict(ordinal=s['expression_ordinal'],copy=source['id'],action='held',reason=p['deferred_reason']));continue
  validate_pair(p,source,target,copy_released=sreleased,target_released=treleased,source_historical=shist,target_historical=thist)
  for side in(s,t):
   doc=side['document_id']
   if doc not in checked_docs:
    cur.execute('SELECT d.sha256,b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s',(doc,))
    current=cur.fetchone()
    pdf=(Path('/mnt/e/nizam-data')/side['source_pdf_object_key']).resolve()
    if (not pdf.is_relative_to(Path('/mnt/e/nizam-data').resolve())or
        current!=(side['source_pdf_sha256'],side['source_pdf_object_key'])or
        hashlib.sha256(pdf.read_bytes()).hexdigest()!=side['source_pdf_sha256']):
     raise ValueError('Source archive hash/key drift')
    checked_docs[doc]=raw_digest(cur,doc)
   if checked_docs[doc]!=side['reviewed_raw_blocks']:raise ValueError('Reviewed raw block evidence changed')
  if manifest is None:raise ValueError('Copy requires a current reviewed manifest')
  cur.execute('SELECT start_block_id,end_block_id FROM instrument_expression_span WHERE manifest_id=%s ORDER BY span_ordinal',(manifest['id'],))
  if cur.fetchall()!=[(x['start_block_id'],x['end_block_id'])for x in s['spans']]:raise ValueError('Copy source spans changed')
  if target_manifest:
   cur.execute('SELECT start_block_id,end_block_id FROM instrument_expression_span WHERE manifest_id=%s ORDER BY span_ordinal',(target_manifest['id'],))
   target_spans=cur.fetchall()
  else:target_spans=[(target['source_start_block_id'],target['source_end_block_id'])]
  if target_spans!=[(x['start_block_id'],x['end_block_id'])for x in t['spans']]:raise ValueError('Canonical source spans changed')
  cur.execute('SELECT count(*) FROM provision WHERE instrument_id=%s AND is_active',(source['id'],))
  if cur.fetchone()!=(0,):raise ValueError('Only raw unstructured source holders may be resolved')
  cur.execute('SELECT count(*) FROM instrument WHERE is_active AND duplicate_of=%s',(source['id'],))
  if cur.fetchone()!=(0,):raise ValueError('Copy is already the canonical target of another active copy; chain refused')
  if source['duplicate_of']is not None:
   if source['duplicate_of']==target['id']and manifest['evidence'].get('source_variant_disposition')==p:
    changes.append(dict(ordinal=s['expression_ordinal'],copy=source['id'],canonical=target['id'],action='already-resolved'));continue
   raise ValueError('Already points elsewhere or standing proof changed')
  if source['id']!=s['reviewed_instrument_id']or target['id']!=t['reviewed_instrument_id']:
   raise ValueError('First-link reviewed revision changed; review its successor first')
  if str(manifest['id'])!=s['reviewed_manifest_id']or (str(target_manifest['id'])if target_manifest else None)!=t['reviewed_manifest_id']:
   raise ValueError('First-link reviewed manifest changed')
  if manifest['review_basis']!='source_verified':raise ValueError('Unreviewed source identity')
  if not write:
   changes.append(dict(ordinal=s['expression_ordinal'],copy=source['id'],canonical=target['id']));continue
  # Append the decision; retain the old manifest, tree, raw ledger and source.
  evidence=dict(manifest['evidence'],source_variant_disposition=p,
                source_variant_owner_answer=answer,
                source_body_review_state='identity-resolved/raw-variant-retained',
                source_variant_current_target_at_resolution=target['id'])
  cur.execute('UPDATE instrument_expression_manifest SET is_active=false,retired_at=now()WHERE id=%s',(manifest['id'],))
  columns=['source_observation_id','document_id','expression_ordinal','expression_role','start_block_id','end_block_id','detected_title','detected_kind','detected_year','detected_number','review_basis','method','evidence','materialized_instrument_id','supersedes_manifest_id']
  values=[manifest.get(k)for k in columns]
  values[columns.index('method')]=METHOD;values[columns.index('evidence')]=json.dumps(evidence,ensure_ascii=False)
  values[columns.index('supersedes_manifest_id')]=manifest['id']
  cur.execute('INSERT INTO instrument_expression_manifest('+','.join(columns)+')VALUES('+','.join(['%s']*len(columns))+')RETURNING id',values)
  new_manifest=cur.fetchone()[0]
  cur.execute('''INSERT INTO instrument_expression_span(manifest_id,span_ordinal,start_block_id,end_block_id)
                 SELECT %s,span_ordinal,start_block_id,end_block_id FROM instrument_expression_span WHERE manifest_id=%s''',(new_manifest,manifest['id']))
  cur.execute('''UPDATE instrument SET duplicate_of=%s WHERE id=%s AND is_active AND duplicate_of IS NULL
                 AND NOT EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=instrument.id)''',(target['id'],source['id']))
  if cur.rowcount!=1:raise ValueError('Copy became released or changed')
  changes.append(dict(ordinal=s['expression_ordinal'],copy=source['id'],canonical=target['id'],manifest_id=str(new_manifest)))
 return changes

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--matrix',required=True)
 group=ap.add_mutually_exclusive_group();group.add_argument('--trial',action='store_true');group.add_argument('--apply',action='store_true')
 ap.add_argument('--approval');args=ap.parse_args();path=Path(args.matrix)
 matrix=json.loads(path.read_text());write=args.trial or args.apply
 if args.apply:
  if not args.approval:ap.error('--apply requires --approval')
  validate_approval(json.loads(Path(args.approval).read_text()),path)
 with connect()as conn,conn.cursor()as cur:
  cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
  cur.execute('SELECT id FROM source_observation WHERE id=13533 FOR UPDATE');assert cur.fetchone()==(13533,)
  cur.execute('SELECT id::text FROM v_release_instrument');before={x[0]for x in cur.fetchall()}
  if args.apply:cur.execute(RELEASE_FINGERPRINT_SQL);fingerprints=dict(cur.fetchall())
  source_before=unchanged_source_state(cur)
  changes=apply_matrix(cur,matrix,write=write)
  if unchanged_source_state(cur)!=source_before:raise ValueError('Source/raw/assignment/curation drift')
  cur.execute('SELECT id::text FROM v_release_instrument');assert {x[0]for x in cur.fetchall()}==before
  if args.apply:
   cur.execute(RELEASE_FINGERPRINT_SQL);assert dict(cur.fetchall())==fingerprints,'Released fingerprint drift'
  if args.trial:conn.rollback()
 report=dict(applied=args.apply,rolled_back=args.trial,identity_resolutions=changes,
             new_releases=0,released_count=len(before),all_released_ids_unchanged=True,
             all_released_fingerprints_unchanged=args.apply,source_raw_ledger_unchanged=True)
 out=path.parent/('variants-applied.json'if args.apply else'variants-trial.json'if args.trial else'variants-preview.json')
 out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
