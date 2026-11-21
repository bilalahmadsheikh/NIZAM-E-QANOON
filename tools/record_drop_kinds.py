"""record_drop_kinds.py VERSION [VERSION ...] [--apply] : the kind of a landed notification, from its catalogue and its own
first page (DECISION-LOG D-113).

The segmenter infers kind from the title alone (nizam.workers.segment.infer_kind), and "Rules" outranks "S.R.O.": an
SECP notification titled "SRO 243 of 2024 - Amendments to CRC Rules 2019" became kind `rules`, one "regarding
constitution of ..." became `constitution`. The source drops' catalogue (source_metadata.type) names what each file is:
SECP's Notifications folder, FBR's Customs SRO listing. An instrument is corrected when ALL hold:

  * its catalogue type is `notification` or `sro`, and its kind is neither;
  * it is not a principal instrument issued by notification: its title amends, alters, supersedes, substitutes,
    exempts, delegates, directs, rescinds or is "regarding" something -- or its inferred kind is one a notification
    can never be (constitution, ordinance, order, act);
  * its first page prints the notification heading ("NOTIFICATION", or the S.R.O. number line): that block is the
    quoted evidence.

Each correction is an append-only instrument_metadata_assertion (field kind, basis printed_notification_heading;
0101), applied by tools/apply_instrument_metadata.py and re-applied after every replay. A principal "X Regulations,
2015" made by SRO keeps its inferred kind.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nizam.storage.db import connect  # noqa: E402

NOT_PRINCIPAL = re.compile(r"(?i)\b(amend\w*|alteration\w*|supersession|superseded|substitut\w+|exempt\w*|delegat\w+|"
                           r"direction\w*|rescind\w*|regarding|omission|insertion|extension|withdrawal)\b")
NEVER_A_NOTIFICATION_KIND = {"constitution", "ordinance", "order", "act"}
HEADING = re.compile(r"(?i)\bNOTIFICATION\b|\bS\.?\s?R\.?\s?O\.?\s*(?:No\.?\s*)?\d")
METHOD = "nizam.drop_catalogue_kind/1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("versions", nargs="+")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.kind::text, i.short_title,
                              o.source_metadata->>'type', i.document_id
                         FROM instrument i JOIN source_observation o ON o.id = i.source_observation_id
                        WHERE o.scraper_version = ANY(%s) AND i.is_active AND i.duplicate_of IS NULL
                          AND o.source_metadata->>'type' IN ('notification', 'sro')
                          AND i.kind::text NOT IN ('notification', 'sro')""", (a.versions,))
        for iid, obs, ordinal, kind, title, cat, doc in cur.fetchall():
            if not (NOT_PRINCIPAL.search(title or "") or kind in NEVER_A_NOTIFICATION_KIND):
                continue
            cur.execute("""SELECT id, page_no, text FROM text_block WHERE document_id = %s AND page_no <= 2
                            ORDER BY page_no, reading_order LIMIT 40""", (doc,))
            hit = next(((b, p, " ".join(t.split())) for b, p, t in cur.fetchall() if HEADING.search(t)), None)
            if not hit:
                print(f"  no printed heading on pp.1-2: doc {doc} {title[:70]}")
                continue
            b, p, text = hit
            m = HEADING.search(text)
            quote = text[max(0, m.start() - 40): m.end() + 80].strip()
            rows.append((obs, ordinal, cat, b, p, quote, kind, title, doc))
        print(f"{len(rows)} kind correction(s): " + json.dumps(
            {f"{k}->{c}": sum(1 for r in rows if r[6] == k and r[2] == c) for k in {r[6] for r in rows}
             for c in {r[2] for r in rows}}))
        for r in rows[:12]:
            print(f"  doc {r[8]} {r[6]} -> {r[2]}: {r[7][:60]} | p{r[4]} '{r[5][:70]}'")
        if a.apply:
            for obs, ordinal, cat, b, p, quote, kind, title, doc in rows:
                cur.execute("""INSERT INTO instrument_metadata_assertion
                                 (source_observation_id, expression_ordinal, field, value, assertion, basis,
                                  source_block_id, source_page, quote, method, evidence, recorded_by)
                               VALUES (%s, %s, 'kind', %s, 'asserted', 'printed_notification_heading', %s, %s, %s, %s,
                                       %s, 'claude')""",
                            (obs, ordinal, cat, b, p, quote, METHOD,
                             json.dumps({"catalogue_type": cat, "inferred_kind": kind, "title": title,
                                         "page_read": False, "reviewer_type": "machine_quote_check",
                                         "decision": "DECISION-LOG D-113"})))
            conn.commit()
            print("recorded")
        else:
            print("dry run: pass --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
