"""Read-only whole-family probe of dotted commencement repairs (doc 02 §5.1).

Compares committed HEAD against the working parser. Outputs evidence only,
never adjudications or corpus revisions. Review each changed source before replay.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

from nizam.corpus import segment as current
from nizam.storage.db import connect


def fingerprint(result):
    return dict(toc=result.toc, missing=result.missing,
        demoted=result.repeated_labels_demoted,
        nodes=[dict(kind=n.kind,label=n.label,heading=n.heading,text=n.text,
                    marginal_note=n.marginal_note,first_block=n.first_block,
                    parent_kind=n.parent.kind,parent_label=n.parent.label,
                    blocks=n.blocks) for n in result.flatten()],
        assigned_blocks=sorted(result.block_roles))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args = ap.parse_args()
    baseline_source = subprocess.check_output(['git','show','HEAD:nizam/corpus/segment.py'],text=True)
    baseline = types.ModuleType('nizam.corpus._dotted_commencement_baseline')
    sys.modules[baseline.__name__] = baseline
    exec(compile(baseline_source,'<committed baseline>','exec'),baseline.__dict__)
    changed=[]
    with connect() as conn,conn.cursor() as cur:
        cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cur.execute(r"""
            SELECT DISTINCT b.document_id FROM text_block b
            JOIN document d ON d.id=b.document_id AND d.is_active
            WHERE b.text ~* '(^|\n)[[:space:]]*2[[:space:]]*[.][[:space:]]*It[[:space:]]+shall[[:space:]]+come[[:space:]]+into[[:space:]]+force[[:space:]]+at[[:space:]]+once'
              AND EXISTS (SELECT 1 FROM instrument i WHERE i.document_id=d.id
                          AND i.is_active AND i.duplicate_of IS NULL)
            ORDER BY b.document_id
        """)
        docs=[r[0] for r in cur.fetchall()]
        for doc in docs:
            cur.execute("""
                SELECT t.id,t.text,t.page_no,t.y0,p.height,t.x0,t.x1
                FROM text_block t JOIN document d ON d.id=t.document_id AND d.is_active
                JOIN page p ON p.document_id=t.document_id AND p.page_no=t.page_no
                WHERE t.document_id=%s ORDER BY t.reading_order,t.id
            """,(doc,))
            blocks=[dict(id=r[0],text=r[1],page_no=r[2],y0=float(r[3]),
                         page_height=float(r[4] or 792),x0=float(r[5]),x1=float(r[6]))
                    for r in cur.fetchall()]
            before=fingerprint(baseline.segment(deepcopy(blocks)))
            after=fingerprint(current.segment(deepcopy(blocks)))
            if before == after:
                continue
            record=dict(document_id=doc,before=before,after=after,
                        all_source_blocks_assigned=after['assigned_blocks']==sorted(b['id'] for b in blocks),
                        source_text_sha256=hashlib.sha256(json.dumps(
                            [(b['id'],b['text']) for b in blocks],ensure_ascii=False).encode()).hexdigest())
            changed.append(record)
            print(json.dumps(dict(document_id=doc,demotions=f"{before['demoted']}->{after['demoted']}",
                                  missing=f"{before['missing']}->{after['missing']}",
                                  all_source_blocks_assigned=record['all_source_blocks_assigned'])),flush=True)
    report=dict(baseline_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        current_source_sha256=hashlib.sha256(Path('nizam/corpus/segment.py').read_bytes()).hexdigest(),
        candidates=len(docs),changed=changed)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,default=str,indent=2),encoding='utf-8')
    print(f'Candidate documents: {len(docs)}; changed: {len(changed)}',flush=True)


if __name__ == '__main__':
    main()
