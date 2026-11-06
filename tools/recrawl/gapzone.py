"""gapzone.py GAPS.jsonl OUT.json DOC [DOC ...] : for each numeric contents gap N, the body blocks between the units N-1
and N+1 (read-only). A block whose opening looks like a damaged number ('l1.', 'I0.', '1O,', 'S.') is the candidate.
Writes candidates {doc, label, block, page, text} for cropping."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
gaps = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
docs = set(map(int, sys.argv[3:]))
NUMISH = re.compile(r"^\W{0,4}[\dIlOoSsZzB|]{1,3}\s*[.,:;]\s")
out = []
with connect() as conn, conn.cursor() as cur:
    for g in [x for x in gaps if x["doc"] in docs and re.fullmatch(r"\d{1,3}", (x["label"] or "").strip())]:
        n = int(g["label"]); d = g["doc"]
        cur.execute("""SELECT pr.label, t.page_no, t.reading_order, t.id FROM provision pr JOIN instrument i ON i.id=pr.instrument_id AND i.is_active
                         JOIN text_block t ON t.id=pr.first_block
                        WHERE i.document_id=%s AND pr.is_active AND pr.kind::text IN ('section','rule','regulation','article')
                          AND pr.label IN (%s, %s)""", (d, str(n - 1), str(n + 1)))
        nb = {r[0]: r for r in cur.fetchall()}
        lo, hi = nb.get(str(n - 1)), nb.get(str(n + 1))
        if not lo:
            print(d, n, "no unit", n - 1); continue
        cur.execute("""SELECT id, page_no, reading_order, text FROM text_block WHERE document_id=%s
                        AND (page_no, reading_order) > (%s, %s) AND (%s OR (page_no, reading_order) < (%s, %s))
                        ORDER BY page_no, reading_order LIMIT 40""",
                    (d, lo[1], lo[2], hi is None, hi[1] if hi else 0, hi[2] if hi else 0))
        rows = cur.fetchall()
        cands = [r for r in rows if NUMISH.match(r[3] or "")]
        print(f"--- doc {d} gap {n} {g['heading'][:40]!r}: {len(rows)} blocks between {n-1} and {n+1}; candidates {len(cands)}")
        for b, p, o, t in cands[:3]:
            print(f"    {b} p{p} {re.sub(chr(10), ' | ', t)[:90]!r}")
            out.append({"doc": d, "label": str(n), "proposed": str(n), "block": b, "page": p, "role": "gap", "text": t[:200], "heading": g["heading"]})
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
