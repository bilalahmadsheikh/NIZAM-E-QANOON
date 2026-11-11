"""Append a reviewed source-only facsimile notice. Never qualify/replay legal text."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from nizam.storage.db import connect
from tools.expression_source_variants import digest, unchanged_source_state
from tools.materialize_multi_instrument import owner_decision_answer
from tools.source_access_notice import METHOD, validate_source_access

CHOICE = 'annotated-source-only'
REQUIRED_FILES = ('tools/release_annotated_source.py', 'tools/source_access_notice.py',
                  'tools/corpus-browser/serve.py', 'tests/test_source_access_notice.py',
                  'tests/test_source_access_browser.py', 'docs/ANNOTATED-SOURCE-ACCESS.md')


def validate_proposal(proposal):
    n = proposal['notice']
    validate_source_access(n)
    if (proposal.get('schema') != METHOD or proposal['document_id'] != 9361
            or proposal['source_observation_id'] != 13533 or proposal['expression_ordinal'] != 0
            or proposal['spans'] != [[2510898, 2511399]]
            or n['source_sha256'] != '06c9627234683325116fdd8f9f9ac186ced50b94be2a0d6d9f33a9e72cf16122'):
        raise ValueError('Outside the reviewed original9361/e0 source-only scope')
    if ((n.get('document_id'), n.get('source_observation_id'), n.get('expression_ordinal')) != (9361,13533,0)
            or n.get('source_blocks') != [2510898,2511399]
            or n.get('owner_decision', {}).get('question_id') != 'q6'
            or proposal.get('artifact_directory') != '.artifacts/annotated-source-9361'):
        raise ValueError('Notice identity/scope/owner decision differs from source proposal')
    if digest(n) != proposal['notice_sha256']:
        raise ValueError('Notice drift')
    required = {proposal['artifact_directory']+'/'+name for name in
                ('index.html','NOTICE.txt','source-release.json','original-compilation.pdf')}
    if not required <= set(proposal['artifact_hashes']):
        raise ValueError('Missing companion source/notice artifacts')
    if proposal['artifact_hashes'][proposal['artifact_directory']+'/original-compilation.pdf'] != n['source_sha256']:
        raise ValueError('Companion PDF must be the unchanged source')
    for filename, expected in proposal['artifact_hashes'].items():
        p = Path(filename).resolve()
        if not p.is_relative_to(Path.cwd().resolve()) or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('Companion source/notice artifact drift')


def snapshot(cur):
    cur.execute('SELECT row_to_json(i)FROM instrument i WHERE source_observation_id=13533 AND is_active ORDER BY expression_ordinal')
    instruments = [r[0] for r in cur.fetchall()]
    cur.execute('''SELECT row_to_json(m)FROM instrument_expression_manifest m
                    WHERE source_observation_id=13533 AND is_active AND expression_ordinal<>0
                    ORDER BY expression_ordinal''')
    other_manifests = [r[0] for r in cur.fetchall()]
    cur.execute('SELECT id::text FROM v_release_instrument ORDER BY id')
    released = [r[0] for r in cur.fetchall()]
    return dict(instruments=instruments, other_manifests=other_manifests,
                source_raw_ledger=unchanged_source_state(cur), released_ids=released)


def append_notice(cur, proposal, *, write=False):
    validate_proposal(proposal)
    answer = owner_decision_answer(proposal['notice']['owner_decision'], 9361)
    if (answer['choice'] != CHOICE or answer['card']['recommended'] != CHOICE
            or proposal['notice_sha256'] not in answer['card']['question']
            or answer['card_sha256'] != hashlib.sha256(json.dumps(answer['card'], sort_keys=True).encode()).hexdigest()):
        raise ValueError('Missing exact owner-authorized annotated-source decision')
    cur.execute('SELECT id FROM source_observation WHERE id=13533 FOR UPDATE')
    assert cur.fetchone() == (13533,)
    cur.execute('SELECT row_to_json(i)FROM instrument i WHERE source_observation_id=13533 AND expression_ordinal=0 AND is_active FOR UPDATE')
    rows = cur.fetchall()
    if len(rows) != 1 or rows[0][0] != proposal['reviewed_instrument']:
        raise ValueError('Original source identity changed')
    inst = rows[0][0]
    cur.execute('SELECT EXISTS(SELECT 1 FROM v_release_instrument WHERE id=%s)', (inst['id'],))
    if cur.fetchone() != (False,) or inst['duplicate_of'] is not None:
        raise ValueError('This route cannot withdraw or relabel a legal release/copy')
    cur.execute('SELECT count(*)FROM provision WHERE instrument_id=%s AND is_active', (inst['id'],))
    if cur.fetchone() != (0,):
        raise ValueError('Unqualified facsimile route requires zero active provisions')
    cur.execute('SELECT row_to_json(m)FROM instrument_expression_manifest m WHERE source_observation_id=13533 AND expression_ordinal=0 AND is_active FOR UPDATE')
    rows = cur.fetchall()
    if len(rows) != 1:
        raise ValueError('Missing or ambiguous active original manifest')
    mf = rows[0][0]
    existing = mf['evidence'].get('source_access_release')
    if existing is None and mf != proposal['reviewed_manifest']:
        raise ValueError('Reviewed manifest changed')
    cur.execute('SELECT start_block_id,end_block_id FROM instrument_expression_span WHERE manifest_id=%s ORDER BY span_ordinal', (mf['id'],))
    if [list(r) for r in cur.fetchall()] != proposal['spans']:
        raise ValueError('Source scope changed')
    if mf.get('historical_validity') is not None:
        raise ValueError('A dated historical expression is outside source-only scope')
    cur.execute('SELECT d.sha256,b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=9361')
    sha, key = cur.fetchone()
    if sha != proposal['notice']['source_sha256'] or key != proposal['source_object_key']:
        raise ValueError('Source archive key/hash changed')
    if hashlib.sha256((Path('/mnt/e/nizam-data') / key).read_bytes()).hexdigest() != sha:
        raise ValueError('Original PDF bytes changed')
    if existing is not None:
        if existing != proposal['notice'] or mf['evidence'].get('source_access_owner_answer') != answer:
            raise ValueError('Standing source-access decision differs')
        return dict(action='already-noted', manifest_id=mf['id'])
    if not write:
        return dict(action='preview', previous_manifest_id=mf['id'])
    evidence = dict(mf['evidence'], source_access_release=proposal['notice'], source_access_owner_answer=answer)
    cur.execute('UPDATE instrument_expression_manifest SET is_active=false,retired_at=now()WHERE id=%s', (mf['id'],))
    columns = ['source_observation_id','document_id','expression_ordinal','expression_role',
               'start_block_id','end_block_id','detected_title','detected_kind','detected_year',
               'detected_number','review_basis','method','evidence','materialized_instrument_id','supersedes_manifest_id']
    values = [mf.get(k) for k in columns]
    values[columns.index('method')] = METHOD
    values[columns.index('evidence')] = json.dumps(evidence, ensure_ascii=False)
    values[columns.index('supersedes_manifest_id')] = mf['id']
    cur.execute('INSERT INTO instrument_expression_manifest('+','.join(columns)+')VALUES('+','.join(['%s']*len(columns))+')RETURNING id', values)
    new = cur.fetchone()[0]
    cur.execute('''INSERT INTO instrument_expression_span(manifest_id,span_ordinal,start_block_id,end_block_id)
                   SELECT %s,span_ordinal,start_block_id,end_block_id FROM instrument_expression_span WHERE manifest_id=%s''', (new, mf['id']))
    return dict(action='noted', previous_manifest_id=mf['id'], manifest_id=str(new))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--proposal', required=True)
    group = ap.add_mutually_exclusive_group()
    group.add_argument('--trial', action='store_true'); group.add_argument('--apply', action='store_true')
    ap.add_argument('--approval'); args = ap.parse_args()
    path = Path(args.proposal); proposal = json.loads(path.read_text())
    if args.apply:
        if not args.approval: ap.error('--apply requires --approval')
        a = json.loads(Path(args.approval).read_text())
        hashes = a.get('approved_hashes') or {}
        if (a.get('approved') is not True or not a.get('reviewer') or a.get('remaining_findings') != []
                or not (set(REQUIRED_FILES) | {str(path)}) <= set(hashes)):
            raise ValueError('Incomplete independent source-only approval')
        for filename, h in hashes.items():
            if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != h:
                raise ValueError('Source-only approval drift: '+filename)
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        before = snapshot(cur)
        change = append_notice(cur, proposal, write=args.trial or args.apply)
        if snapshot(cur) != before:
            raise ValueError('Source-only note changed an identity, sibling manifest, raw ledger or release')
        if args.trial: conn.rollback()
    report = dict(applied=args.apply, rolled_back=args.trial, change=change,
                  source_access='original-facsimile-only', legal_text_released=False,
                  newly_released_legal_texts=0, released_count=len(before['released_ids']),
                  original_and_siblings_unchanged=True)
    out = path.parent / ('source-only-applied.json' if args.apply else 'source-only-trial.json' if args.trial else 'source-only-preview.json')
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
