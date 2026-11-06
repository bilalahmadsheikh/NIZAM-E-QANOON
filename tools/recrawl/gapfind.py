"""gapfind.py GAPS.jsonl DOC [DOC ...] : for each pending contents gap, the body blocks printing its heading (read-only).

Search words: the gap heading's first three words of >= 4 letters; a body block matches when it holds all of them
(case-folded, letters only). Prints the block id, page and 70 chars before / 50 after the first word's hit."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
gaps = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
docs = set(map(int, sys.argv[2:]))
with connect() as conn, conn.cursor() as cur:
    for d in sorted(docs):
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (d,))
        blocks = cur.fetchall()
        for g in [x for x in gaps if x["doc"] == d]:
            words = [w for w in re.findall(r"[A-Za-z]{4,}", g["heading"])][:3]
            print(f"--- doc {d} gap {g['label']!r} {g['heading'][:60]!r} (row block {g['block']} p{g['page']})")
            if not words:
                continue
            hits = 0
            for bid, p, t in blocks:
                if bid == g["block"]:
                    continue
                low = t.lower()
                if all(w.lower() in low for w in words):
                    i = low.find(words[0].lower())
                    one = re.sub(r"\s+", " ", t[max(0, i - 70): i + 50])
                    print(f"    {bid} p{p}: ...{one}...")
                    hits += 1
                    if hits >= 3:
                        break
