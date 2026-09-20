"""Verify the 15 September bounded replays and Claude review artifact integrity.

Read-only corpus queries; writes a review report only. Render hash/identity
checks are NOT a semantic page audit and must never be described as one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from nizam.storage.db import connect


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--documents', default='1224,16',
                    help='Comma-separated, source-reviewed single-expression repairs')
    ap.add_argument('--snapshot', type=Path,
                    help='Pre-repair snapshot containing source fixtures and dry-run trees')
    ap.add_argument('--worker', type=int,
                    help='Expected writer revision for this newly reviewed bounded batch')
    args = ap.parse_args()
    documents = [int(v) for v in args.documents.split(',')]
    fixtures = {1224:'contents-1224.json',16:'dotted-commencement-16.json',
                1927:'split-notes-1927.json',2960:'split-notes-2960.json'}
    with connect() as conn,conn.cursor() as cur:
        cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        def query(sql,params=None):
            cur.execute(sql,params)
            names=[c.name for c in cur.description]
            return [dict(zip(names,r)) for r in cur.fetchall()]
        state=query("""
            SELECT now() AS measured_at,current_database() AS database,
              (SELECT count(*) FROM instrument i JOIN document d ON d.id=i.document_id AND d.is_active
                WHERE i.is_active AND i.duplicate_of IS NULL) AS canonical,
              (SELECT count(*) FROM v_release_instrument) AS released,
              (SELECT count(*) FROM v_toc_gap_pending) AS toc_pending,
              (SELECT count(*) FROM v_structural_adjudication_pending) AS s7_pending,
              pg_size_pretty(pg_database_size(current_database())) AS db_size
        """)[0]
        repairs=[]
        for doc in documents:
            inst=query("""
                SELECT i.id,i.supersedes_instrument_id,d.sha256,b.object_key,
                  EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id) AS released
                FROM instrument i JOIN document d ON d.id=i.document_id AND d.is_active
                JOIN blob b ON b.sha256=d.sha256
                WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL
            """,(doc,))
            assert len(inst)==1,(doc,'expected one current canonical expression')
            inst=inst[0]
            run=query("""
                SELECT r.segmenter,r.outcome,r.run_at
                FROM segmentation_run r
                JOIN instrument i ON i.id=r.instrument_id AND i.is_active AND i.duplicate_of IS NULL
                JOIN document d ON d.id=i.document_id AND d.is_active
                WHERE r.instrument_id=%s ORDER BY r.run_at DESC,r.id DESC LIMIT 1
            """,(inst['id'],))[0]
            expected_worker = args.worker or {1224:56,16:57}.get(doc,58)
            assert run['outcome']=='segmented' and run['segmenter']==f'nizam.corpus.segment/{expected_worker}',(doc,'unexpected writer identity')
            blocks=query("""
                SELECT t.id,t.text FROM text_block t
                JOIN document d ON d.id=t.document_id AND d.is_active
                WHERE t.document_id=%s ORDER BY t.reading_order,t.id
            """,(doc,))
            fixture_path = (Path('tests/fixtures')/fixtures[doc] if doc in fixtures
                            else args.snapshot/'source-fixtures'/f'contents-{doc}.json')
            saved=json.loads(fixture_path.read_text(encoding='utf-8'))
            assert [(b['id'],b['text']) for b in blocks]==[(b['id'],b['text']) for b in saved],(doc,'source text changed')
            tree=query("""
                SELECT p.kind::text,p.label,p.marginal_note,p.parent_id,p.first_block,
                       p.path::text,p.heading,p.ordinal,p.first_page,p.last_page,
                       v.text_en AS text
                FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
                JOIN document d ON d.id=i.document_id AND d.is_active
                LEFT JOIN provision_version v ON v.provision_id=p.id AND v.validity @> current_date
                WHERE p.instrument_id=%s AND p.is_active ORDER BY p.ordinal
            """,(inst['id'],))
            # Explicit historical lineage check, intentionally not a current-state
            # query: the predecessor must still exist and be retired, not deleted.
            old=query("""
                SELECT i.id,i.is_active,(SELECT count(*) FROM provision p WHERE p.instrument_id=i.id) AS provisions,
                  (SELECT count(*) FROM provision p WHERE p.instrument_id=i.id AND p.is_active) AS active_provisions
                FROM instrument i WHERE i.id=%s
            """,(inst['supersedes_instrument_id'],))
            assert len(old)==1 and not old[0]['is_active'] and old[0]['active_provisions']==0,(doc,'missing retained predecessor')
            assert inst['released'],(doc,'repair not released')
            pending=query("""
                SELECT (SELECT count(*) FROM v_toc_gap_pending WHERE instrument_id=%s) AS toc,
                  (SELECT count(*) FROM v_structural_adjudication_pending WHERE instrument_id=%s) AS s7,
                  (SELECT count(DISTINCT pb.block_id) FROM provision_block pb
                    JOIN block_assignment_set a ON a.id=pb.assignment_set_id AND a.is_active
                    JOIN document d ON d.id=a.document_id AND d.is_active
                    WHERE a.document_id=%s) AS assigned_blocks
            """,(inst['id'],inst['id'],doc))[0]
            assert pending['toc']==0 and pending['s7']==0,(doc,'pending repair defects')
            assert pending['assigned_blocks']==len(blocks),(doc,'unassigned source blocks')
            candidate_identical=None
            if args.snapshot:
                drypath=args.snapshot/'dry-runs'/f'{doc}.json'
                if drypath.exists():
                    dry=json.loads(drypath.read_text())
                    fields=('kind','label','marginal_note','first_block','path','heading',
                            'ordinal','first_page','last_page','text')
                    expected=[tuple(p.get(f) for f in fields) for p in dry['provisions']]
                    actual=[tuple(p.get(f) for f in fields) for p in tree]
                    if actual!=expected:
                        differences=[dict(ordinal=n,fields={f:dict(expected=e,actual=a)
                            for f,e,a in zip(fields,left,right) if e!=a})
                            for n,(left,right) in enumerate(zip(expected,actual)) if left!=right]
                        print(json.dumps(dict(document_id=doc,expected_nodes=len(expected),
                            actual_nodes=len(actual),differences=differences[:3]),default=str),flush=True)
                        raise AssertionError((doc,'persisted tree differs from source-reviewed dry run'))
                    candidate_identical=True
            if doc==16:
                section=next(p for p in tree if p['kind']=='section' and p['label']=='2')
                assert section['text']=='In the Sind Civil Servants Act, 1973, section 9-A shall be omitted.'
                assert section['marginal_note']=='Omission of section 9-A Sind Act No.XIV of 1973.'
                assert not any(p['kind']=='subsection' and p['parent_id'] is None for p in tree)
            pdf=Path('/mnt/e/nizam-data')/inst['object_key']
            assert hashlib.sha256(pdf.read_bytes()).hexdigest()==inst['sha256'].strip(),(doc,'source PDF hash mismatch')
            repairs.append(dict(document_id=doc,current=inst,run=run,predecessor=old[0],source_blocks=len(blocks),
                                source_text_unchanged=True,pdf_hash_verified=True,
                                pending=pending,persisted_tree_matches_reviewed_dry_run=candidate_identical,tree=tree))
        reviews=query("""
            SELECT a.id,a.resolution,a.evidence,c.document_id,c.source_page,c.canonical_source_page
            FROM v_structural_adjudication_latest a
            JOIN v_active_structural_candidate c ON c.id=a.candidate_id
            JOIN instrument i ON i.id=c.instrument_id AND i.is_active AND i.duplicate_of IS NULL
            JOIN document d ON d.id=c.document_id AND d.is_active
            WHERE a.decided_by='claude.s7-source-review/1' AND a.review_basis='source_verified'
        """)
        checked=[]
        for row in reviews:
            evidence=row.pop('evidence')
            path=Path(evidence.get('render_artifact') or '')
            digest=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            name=re.search(r'(?:doc|r)(\d+)-?p(\d+)',path.name)
            checked.append(dict(**row,render=str(path),exists=path.is_file(),
                hash_matches=digest is not None and digest==evidence.get('render_sha256'),
                filename_matches_candidate=bool(name and int(name[1])==row['document_id'] and int(name[2])==row['source_page']),
                evidence_page_matches_candidate=evidence.get('source_page')==row['source_page']))
        report=dict(state=state,repairs=repairs,claude_source_review_metadata=dict(
            scope='Latest source_verified decisions attached to current canonical candidates; NOT verdict correctness',
            checked=len(checked),issues=[r for r in checked if not all(r[k] for k in
                ('exists','hash_matches','filename_matches_candidate','evidence_page_matches_candidate'))],rows=checked))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(state=state,verified_documents=[r['document_id'] for r in repairs],
        claude_metadata_checked=len(checked),claude_metadata_issues=len(report['claude_source_review_metadata']['issues'])),default=str),flush=True)


if __name__ == '__main__':
    main()
