"""Read-only before/after probe for title-year TOC promises (doc 02 §5.1–5.2).

The baseline is committed HEAD, not a second copy of corpus data. This writes
review artifacts only. It neither adjudicates nor persists segmentation.
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    baseline_source = subprocess.check_output(
        ['git', 'show', 'HEAD:nizam/corpus/segment.py'], text=True)
    baseline = types.ModuleType('nizam.corpus._contents_title_year_baseline')
    sys.modules[baseline.__name__] = baseline
    exec(compile(baseline_source, '<committed segment baseline>', 'exec'), baseline.__dict__)
    # No arbitrary page/index limit: scan all active documents for any
    # section-shaped year. Extra candidates cost reads, not correctness.
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
        cur.execute(r"""
            SELECT DISTINCT b.document_id
            FROM text_block b JOIN document d ON d.id=b.document_id AND d.is_active
            WHERE b.text ~ '(^|\n)[[:space:]]*(18|19|20)[0-9]{2}[[:space:]]*[.]'
            ORDER BY b.document_id
        """)
        docs = [r[0] for r in cur.fetchall()]
    changed = []
    for doc in docs:
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY')
            cur.execute("""
                SELECT t.id,t.text,t.page_no,t.y0,p.height,t.x0,t.x1
                FROM text_block t JOIN document d ON d.id=t.document_id AND d.is_active
                JOIN page p ON p.document_id=t.document_id AND p.page_no=t.page_no
                WHERE t.document_id=%s ORDER BY t.reading_order,t.id
            """, (doc,))
            blocks = [dict(id=r[0],text=r[1],page_no=r[2],y0=float(r[3]),
                           page_height=float(r[4] or 792),x0=float(r[5]),x1=float(r[6]))
                      for r in cur.fetchall()]
        if not blocks:  # retired concurrently; never profile it as current
            continue
        before = baseline.parse_contents(deepcopy(blocks))
        after = current.parse_contents(deepcopy(blocks))
        if before == after:
            continue
        removed = sorted(set(before[0]) - set(after[0]))
        record = dict(document_id=doc, before=before, after=after,
            removed=removed, added=sorted(set(after[0])-set(before[0])),
            boundary_unchanged=before[1:] == after[1:],
            source_blocks=[dict(index=i, id=b['id'], page=b['page_no'], text=b['text'])
                for i, b in enumerate(blocks[:max(before[1],after[1])])
                if any(line.strip().startswith(label+'.') for line in b['text'].splitlines()
                       for label in removed) or current._has_contents_marker(b['text'])])
        changed.append(record)
        print(json.dumps({k:v for k,v in record.items() if k not in ('before','after','source_blocks')}), flush=True)
    report = dict(baseline_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        baseline_source_sha256=hashlib.sha256(baseline_source.encode()).hexdigest(),
        current_source_sha256=hashlib.sha256(Path('nizam/corpus/segment.py').read_bytes()).hexdigest(),
        candidates=len(docs), changed=changed)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Candidate documents: {len(docs)}; changed: {len(changed)}', flush=True)


if __name__ == '__main__':
    main()
