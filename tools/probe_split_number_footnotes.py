"""Compare split-number apparatus parsing against a captured working baseline.

All database reads are repeatable-read/read-only and canonical/current. This
produces evidence, never corpus revisions (docs 02 section 5, 03 section 2A).
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import types

from nizam.corpus import segment as current
from nizam.storage.db import connect


def fingerprint(result):
    return dict(toc=result.toc, missing=result.missing,
        demoted=result.repeated_labels_demoted,
        nodes=[dict(kind=n.kind, label=n.label, heading=n.heading, text=n.text,
                    marginal_note=n.marginal_note, first_block=n.first_block,
                    first_page=n.first_page, parent_kind=n.parent.kind,
                    parent_label=n.parent.label, blocks=n.blocks)
               for n in result.flatten()],
        roles={str(k): (v[0], v[1].first_block if v[1] else None)
               for k, v in result.block_roles.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--defect', choices=('footnote','dotted-suffix','amended-schedule','form-statement','contents-boundary','dashed-section','editorial-provenance'), default='footnote')
    args = parser.parse_args()
    source_path = Path('nizam/corpus/segment.py')
    source_bytes = source_path.read_bytes()
    source = source_path.read_text(encoding='utf-8')
    if args.baseline is None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(dict(source=source,
            sha256=hashlib.sha256(source.encode()).hexdigest()),
            ensure_ascii=False), encoding='utf-8')
        print('Captured current working parser baseline; no database query.')
        return
    captured = json.loads(args.baseline.read_text(encoding='utf-8'))
    assert hashlib.sha256(captured['source'].encode()).hexdigest() == captured['sha256']
    baseline = types.ModuleType('nizam.corpus._split_number_baseline')
    sys.modules[baseline.__name__] = baseline
    exec(compile(captured['source'], '<captured working baseline>', 'exec'), baseline.__dict__)
    changes = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        pattern = (r'(^|\n)[ \t]*[0-9]{1,2}[ \t]*[.][ \t]*\n'
                   if args.defect == 'footnote' else r'[0-9]{1,4}[.][A-Z]{1,3}[.]')
        if args.defect == 'amended-schedule':
            pattern = (r'(?i)(^|\n)[[:space:]]*[0-9]{0,4}[[:space:]]*\['
                       r'[[:space:]]*("|“|‘|\x27)?[[:space:]]*(THE[[:space:]]+)?'
                       r'((FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|[IVXLC0-9]+)'
                       r'[[:space:]]+)?S[[:space:]]*C[[:space:]]*H[[:space:]]*'
                       r'E[[:space:]]*D[[:space:]]*U[[:space:]]*L[[:space:]]*E')
        if args.defect == 'form-statement':
            pattern = r'(?i)(^|\n)[[:space:]]*FORM[[:space:]]+OF[[:space:]]+STATEMENT'
        if args.defect == 'contents-boundary':
            pattern = (r'(?i)\[[[:space:]]*(Repealed|Omitted|Deleted)[[:space:]]*'
                       r'[.]?[[:space:]]*\]|Short[[:space:]]+title[.][[:space:]]+'
                       r'(Commencement|Extent|Local[[:space:]]+extent)')
        if args.defect == 'dashed-section':
            # Broad source selector; the actual Python rule also requires a
            # new extracted line and first-subsection/uppercase-word proof.
            pattern = (r'[0-9]{1,4}[[:space:]]*[-–]?[[:space:]]*[A-Z]{1,3}'
                       r'[[:space:]]*[.]{1,2}[[:space:]]*[-–—]{1,3}'
                       r'[[:space:]]*[(][[:space:]]*1[[:space:]]*[)]')
        if args.defect == 'editorial-provenance':
            pattern = (r'(?i)(^|[[:space:]])[0-9]{1,2}[.:-][[:space:]]*'
                       r'(S[.][[:space:]]*[0-9]{1,4}[A-Z-]?[[:space:]]*'
                       r'(ins|subs|inserted|substituted|omitted|deleted)'
                       r'|See[[:space:]]+now[[:space:]]+(the[[:space:]]+)?Code'
                       r'|The[[:space:]]+(original[[:space:]]+)?(words|brackets|provisions).{0,200}'
                       r'(rep[.]?[[:space:]]+by))')
        # Official federal PDFs commonly extract NBSP. PostgreSQL's C-locale
        # POSIX whitespace does not cover it, unlike Python's grammar \s.
        # Include it explicitly or the family probe misses its own 4495 case.
        pattern = pattern.replace('[[:space:]]','[[:space:]\u00a0]')
        cur.execute(r"""
            SELECT b.document_id,b.text FROM text_block b
            JOIN document d ON d.id=b.document_id AND d.is_active
            WHERE b.text ~ %s
              AND EXISTS (SELECT 1 FROM instrument i WHERE i.document_id=d.id
                          AND i.is_active AND i.duplicate_of IS NULL)
            ORDER BY b.document_id,b.reading_order
        """, (pattern,))
        blocks_to_check = cur.fetchall()
        docs = sorted({doc for doc,text in blocks_to_check
            if args.defect != 'footnote'
            or baseline._is_footnote_run(text) != current._is_footnote_run(text)
            or current._is_footnote_run(text, split_numbers_only=True)})
        for doc in docs:
            cur.execute("""
                SELECT b.id,b.text,b.page_no,b.y0,p.height,b.x0,b.x1
                FROM text_block b JOIN document d ON d.id=b.document_id AND d.is_active
                JOIN page p ON p.document_id=b.document_id AND p.page_no=b.page_no
                WHERE b.document_id=%s ORDER BY b.reading_order,b.id
            """, (doc,))
            blocks = [dict(id=r[0],text=r[1],page_no=r[2],y0=float(r[3]),
                          page_height=float(r[4] or 792),x0=float(r[5]),x1=float(r[6]))
                      for r in cur.fetchall()]
            before = fingerprint(baseline.segment(deepcopy(blocks)))
            after = fingerprint(current.segment(deepcopy(blocks)))
            if before == after:
                continue
            record = dict(document_id=doc,before=before,after=after,blocks=blocks,
                all_source_blocks_assigned=set(after['roles']) == {str(b['id']) for b in blocks})
            changes.append(record)
            print(json.dumps(dict(document_id=doc,
                missing=[before['missing'],after['missing']],
                demotions=[before['demoted'],after['demoted']],
                sections=[sum(n['kind']=='section' for n in f['nodes']) for f in (before,after)])), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(baseline_sha256=captured['sha256'],
        baseline_hash_basis='Captured parser text, universal-newline normalized',
        current_sha256=hashlib.sha256(source_bytes).hexdigest(),
        current_hash_basis='Exact parser file bytes, including line endings',
        current_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        defect=args.defect,candidate_blocks=len(blocks_to_check),candidates=len(docs),changes=changes),ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(docs)} candidate documents; {len(changes)} changed.', flush=True)


if __name__ == '__main__':
    main()
