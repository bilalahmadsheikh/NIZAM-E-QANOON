"""Read-only lookups for catalogue readers. Never writes.

    subtree <candidate_id>          every node and its text under a demoted S7 unit
    page <document_id> <page>       extracted blocks on one page, in reading order
    tree <document_id> <from> <to>  provisions starting on pages from..to
    grep <document_id> <regex>      blocks whose text matches (case-insensitive)
    entry <toc_entry_id>            the contents entry and its neighbours
"""
from __future__ import annotations

import sys

from nizam.storage.db import connect


def clip(text: str, n: int = 400) -> str:
    return " / ".join(" ".join(line.split()) for line in (text or "").splitlines() if line.strip())[:n]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        if cmd == "subtree":
            cur.execute("""
                SELECT x.kind::text, x.label, x.first_page,
                       (SELECT pa.kind::text || ' ' || pa.label FROM provision pa WHERE pa.id = cand.parent_id),
                       pb.role::text, tb.page_no, tb.text
                  FROM v_structural_adjudication_pending s
                  JOIN provision cand ON cand.id = s.candidate_provision_id
                  JOIN provision x ON x.instrument_id = s.instrument_id AND x.is_active AND x.path <@ cand.path
                  LEFT JOIN provision_block pb ON pb.provision_id = x.id
                  LEFT JOIN text_block tb ON tb.id = pb.block_id
                 WHERE s.id = %s ORDER BY x.path::text, tb.id""", (args[0],))
            rows = cur.fetchall()
            if rows:
                print(f"demoted node's parent: {rows[0][3] or 'root'}")
            for kind, label, fp, _, role, pg, text in rows:
                print(f"[{kind} {label} p{fp}] role={role} page={pg}: {clip(text, 500)}")
        elif cmd == "page":
            cur.execute("""SELECT DISTINCT ON (tb.reading_order) tb.id, round(tb.x0), round(tb.y0), pb.role::text,
                                  (SELECT p.kind::text || ' ' || p.label FROM provision p WHERE p.id = pb.provision_id),
                                  tb.text
                             FROM text_block tb
                             LEFT JOIN (provision_block pb JOIN block_assignment_set bas
                                        ON bas.id = pb.assignment_set_id AND bas.is_active
                                        JOIN instrument ii ON ii.id = bas.instrument_id
                                        AND ii.is_active AND ii.duplicate_of IS NULL)
                                    ON pb.block_id = tb.id
                            WHERE tb.document_id = %s AND tb.page_no = %s
                            ORDER BY tb.reading_order""", (int(args[0]), int(args[1])))
            for bid, x0, y0, role, owner, text in cur.fetchall():
                print(f"blk {bid} x{x0} y{y0} role={role} owner={owner}: {clip(text)}")
        elif cmd == "tree":
            cur.execute("""SELECT p.kind::text, p.label, p.first_page,
                                  (SELECT pa.kind::text || ' ' || pa.label FROM provision pa WHERE pa.id = p.parent_id),
                                  (SELECT string_agg(tb.text, ' ' ORDER BY tb.id) FROM provision_block pb
                                     JOIN text_block tb ON tb.id = pb.block_id WHERE pb.provision_id = p.id)
                             FROM provision p JOIN instrument i ON i.id = p.instrument_id
                                  AND i.is_active AND i.duplicate_of IS NULL
                            WHERE i.document_id = %s AND p.is_active AND p.first_page BETWEEN %s AND %s
                            ORDER BY p.ordinal""", (int(args[0]), int(args[1]), int(args[2])))
            for kind, label, fp, parent, text in cur.fetchall():
                print(f"{kind} {label} p{fp} under {parent or 'root'}: {clip(text, 160)}")
        elif cmd == "grep":
            cur.execute("""SELECT id, page_no, text FROM text_block
                            WHERE document_id = %s AND text ~* %s ORDER BY reading_order LIMIT 40""",
                        (int(args[0]), args[1]))
            for bid, pg, text in cur.fetchall():
                print(f"blk {bid} p{pg}: {clip(text, 300)}")
        elif cmd == "entry":
            cur.execute("""SELECT e.instrument_id, e.ordinal FROM instrument_toc_entry e WHERE e.id = %s""", (int(args[0]),))
            row = cur.fetchone()
            if row is None:
                print("no such entry")
                return 1
            cur.execute("""SELECT e.ordinal, e.printed_label, e.printed_heading, e.source_page,
                                  p.kind::text, p.label, p.first_page
                             FROM instrument_toc_entry e LEFT JOIN provision p ON p.id = e.provision_id
                            WHERE e.instrument_id = %s AND e.ordinal BETWEEN %s AND %s ORDER BY e.ordinal""",
                        (row[0], row[1] - 3, row[1] + 3))
            for o, lab, head, pg, kind, plab, fp in cur.fetchall():
                link = f"-> {kind} {plab} p{fp}" if kind else "-> UNLINKED"
                print(f"{'*' if o == row[1] else ' '} #{o} '{lab}' {clip(head, 90)} (contents p{pg}) {link}")
        else:
            print(__doc__)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
