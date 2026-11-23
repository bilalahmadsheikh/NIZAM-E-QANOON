"""Authoring aids for the precedent stratum (golden-pk-v1-precedent, D-133). Neither uses L3: gold is found by reading.

    python evals/golden/peek_judgment.py find "further inquiry" "497" --court LHC --limit 20
        paragraphs whose text contains every phrase (case-insensitive SQL match, released judgments only), newest
        first, with document id, case as printed, decision date and printed paragraph number
    python evals/golden/peek_judgment.py read 123456 [7 8 9]
        a judgment's header and its paragraphs (all, or the printed numbers / ordinals given)
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def find(cur, phrases, court, limit, width):
    where = " AND ".join(["p.text ILIKE %s"] * len(phrases))
    args = [f"%{p}%" for p in phrases]
    if court:
        where += " AND j.court_code = %s"
        args.append(court)
    cur.execute(f"""SELECT j.document_id, j.court_code, j.case_no_printed, j.decision_date, j.decided_on_basis,
                           p.printed_no, p.ordinal, p.kind, left(p.text, %s)
                      FROM v_release_judgment_paragraph p
                      JOIN v_release_judgment j ON j.id = p.judgment_id AND j.decided_on = p.decided_on
                     WHERE p.kind = 'body' AND {where}
                     ORDER BY j.decided_on DESC LIMIT %s""", [width] + args + [limit])
    for doc, court_code, case, day, basis, no, ordn, kind, text in cur.fetchall():
        print(f"[{doc}] {court_code} {case} · {day or 'undated'} · para {no or '#' + str(ordn)}")
        print(textwrap.indent(textwrap.fill(" ".join(text.split()), 110), "    "))


def read(cur, doc, refs, width):
    cur.execute("""SELECT j.id, j.decided_on, j.court_code, j.case_no_printed, j.decision_date, j.decided_on_basis,
                          j.parties_display, j.bench_printed, j.disposition, j.reported_flag,
                          (SELECT string_agg(case_key, ', ') FROM judgment_case c
                            WHERE c.judgment_id = j.id AND c.decided_on = j.decided_on)
                     FROM v_release_judgment j WHERE j.document_id = %s""", (doc,))
    rows = cur.fetchall()
    if len(rows) != 1:
        print(f"document {doc}: {len(rows)} released judgments"); return
    jid, decided_on, court, case, day, basis, parties, bench, disp, rep, keys = rows[0]
    print(f"{court} {case} · decided {day or 'undated (' + basis + ')'} · {parties} · bench {bench} · "
          f"{disp} · reported {rep} · cases {keys}")
    cur.execute("""SELECT printed_no, ordinal, kind, text FROM v_release_judgment_paragraph
                    WHERE judgment_id = %s AND decided_on = %s ORDER BY ordinal""", (jid, decided_on))
    for no, ordn, kind, text in cur.fetchall():
        if refs and (no not in refs and f"#{ordn}" not in refs):
            continue
        t = " ".join(text.split())
        print(f"\n-- para {no or '#' + str(ordn)} ({kind}, ordinal {ordn})")
        print(textwrap.indent(textwrap.fill(t[:width], 110), "  "))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find")
    f.add_argument("phrases", nargs="+")
    f.add_argument("--court")
    f.add_argument("--limit", type=int, default=15)
    f.add_argument("--width", type=int, default=400)
    r = sub.add_parser("read")
    r.add_argument("doc", type=int)
    r.add_argument("refs", nargs="*")
    r.add_argument("--width", type=int, default=1500)
    a = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        if a.cmd == "find":
            find(cur, a.phrases, a.court, a.limit, a.width)
        else:
            read(cur, a.doc, a.refs, a.width)
    return 0


if __name__ == "__main__":
    sys.exit(main())
