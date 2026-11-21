"""record_not_law.py [--apply] : record landed files that are not law (migration 0116, DECISION-LOG D-113).

The 21 below were found on 21 Nov 2026 by reading the first page of every law landed that day (recrawl-2026-11-21/1):
19 drafts published for consultation, one SECP circular and one press release. For each, the block on pages 1-2 that
prints the words making it not law is quoted; a document whose words are not found is refused, never guessed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nizam.storage.db import connect  # noqa: E402

DRAFT = r"(?i)\bdraft\b|for public consultation|comments,? if any|objections or suggestions"
NOT_LAW = {
    "draft_for_consultation": (DRAFT, [11401, 11421, 11438, 11446, 11455, 11473, 11478, 11486, 11505, 11506, 11520,
                                       11527, 11543, 11552, 11560, 11577, 11584, 11591, 11608]),
    "regulator_circular": (r"(?i)\bCircular\s+No\b", [11465]),
    "press_release": (r"(?i)\bpress release\b", [11449]),
}
METHOD = "nizam.not_law_first_page/1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows, refused = [], []
    with connect() as conn, conn.cursor() as cur:
        for kind, (pattern, docs) in NOT_LAW.items():
            rx = re.compile(pattern)
            for doc in docs:
                cur.execute("""SELECT o.id FROM source_observation o JOIN document d ON d.sha256 = o.sha256
                                WHERE d.id = %s AND d.is_active AND o.outcome = 'landed'""", (doc,))
                obs = [r[0] for r in cur.fetchall()]
                cur.execute("""SELECT id, page_no, text FROM text_block WHERE document_id = %s AND page_no <= 2
                                ORDER BY page_no, reading_order""", (doc,))
                hit = next(((b, p, " ".join(t.split())) for b, p, t in cur.fetchall() if rx.search(t)), None)
                if not hit or not obs:
                    refused.append(doc)
                    continue
                b, p, text = hit
                m = rx.search(text)
                quote = text[max(0, m.start() - 120): m.end() + 160].strip()
                for o in obs:
                    rows.append((o, doc, kind, quote, b, p))
        for o, doc, kind, quote, b, p in rows:
            print(f"  doc {doc} obs {o} {kind}: p{p} '...{quote[:150]}...'")
        print(f"{len(rows)} row(s); refused {refused}")
        if a.apply and not refused:
            for o, doc, kind, quote, b, p in rows:
                cur.execute("""INSERT INTO source_not_law (source_observation_id, document_id, kind, assertion, quote,
                                                            source_block_id, source_page, method, evidence, recorded_by)
                               VALUES (%s, %s, %s, 'excluded', %s, %s, %s, %s, %s, 'claude')""",
                            (o, doc, kind, quote, b, p, METHOD,
                             json.dumps({"reviewer_type": "assistant_first_page_read", "decision": "DECISION-LOG D-113",
                                         "found_by": "first-page sweep of recrawl-2026-11-21/1"})))
            conn.commit()
            print("recorded")
        elif a.apply:
            print("REFUSED: a document's words were not found; nothing recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
