"""Read provisions while authoring a golden set: heading, text, currency (docs/10 §5 stage A0/A3 helper).

    python evals/golden/peek.py 4441:379 4501:154 4237:fed.act.y1908_o107.pt_VI_n10_1.s_113 [--chars 900]
    python evals/golden/peek.py --labels 4441              # list a law's top-level labels and headings

A reference is DOCUMENT:LABEL (a section/article label) or DOCUMENT:PATH (an ltree path, contains a dot). The text is
the whole subtree, read from the database; nothing here writes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    from nizam.storage.db import connect
    from golden_common import resolve
    ap = argparse.ArgumentParser()
    ap.add_argument("refs", nargs="*")
    ap.add_argument("--chars", type=int, default=700)
    ap.add_argument("--labels", type=int)
    ap.add_argument("--grep", help="with --labels: only headings matching this regex")
    a = ap.parse_args()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        if a.labels:
            cur.execute("""SELECT p.label, p.kind::text, left(coalesce(p.heading, ''), 90) FROM provision p
                             JOIN v_release_instrument i ON i.id = p.instrument_id
                            WHERE i.document_id = %s AND p.is_active
                              AND p.kind::text IN ('section', 'article', 'order', 'schedule', 'rule')
                              AND (%s::text IS NULL OR p.heading ~* %s)
                            ORDER BY p.ordinal""", (a.labels, a.grep, a.grep))
            for label, kind, head in cur.fetchall():
                print(f"{kind[:3]} {label:>8}  {head}")
            return 0
        for ref in a.refs:
            doc, _, key = ref.partition(":")
            u = resolve(cur, int(doc), key, chars=a.chars)
            if not u:
                print(f"=== {ref}: DOES NOT RESOLVE\n"); continue
            print(f"=== {ref} | {u['instrument']} ({u['jurisdiction']} {u['year']}) | {u['currency']}: "
                  f"{u['currencyReason']} | s.{u['label']} {u['heading'] or ''}")
            print(u["excerpt"], "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
