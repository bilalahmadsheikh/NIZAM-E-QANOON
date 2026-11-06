"""contfind.py OUT.json DOC [DOC ...] : propose a contents region (first, last, body start) per document (read-only).

first = the first block on pages 1-3 printing a contents heading (CONTENTS / SECTIONS / ARRANGEMENT OF SECTIONS) or,
failing that, the first block whose lines are mostly short numbered rows; body = the first later block printing the
preamble ('WHEREAS', 'Whereas', 'It is hereby enacted') or '1. (1)' / '1. This Act' / '1. These rules'; last = the
block before body. Prints the three blocks' openings for a page check."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
HEAD = re.compile(r"(?i)\b(CONTENTS|SECTIONS\.?|ARRANGEMENT OF SECTIONS)\b")
BODY = re.compile(r"(?im)^\W{0,3}(W\S{0,3}REAS|It is hereby enacted|.{0,40}enacted as follows|1\s*[.,]\s*[\(\{]\s*[1lI]\s*[\)\}]|1\s*[.,]\s+(This|These|Tis)|1\.\s*[—-]+\s*\(1\))")
one = lambda t: re.sub(r"\s+", " ", t)[:90]
out = []
with connect() as conn, conn.cursor() as cur:
    for d in map(int, sys.argv[2:]):
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s AND page_no<=4 ORDER BY page_no, reading_order", (d,))
        bl = cur.fetchall()
        fi = next((i for i, (b, p, t) in enumerate(bl) if p <= 3 and HEAD.search(t[:200])), None)
        if fi is None:
            print(d, "no contents heading"); continue
        bi = next((i for i in range(fi + 1, len(bl)) if BODY.search(bl[i][2])), None)
        if bi is None or bi - 1 < fi:
            print(d, "no body start after contents"); continue
        x = {"doc": d, "first": bl[fi][0], "last": bl[bi - 1][0], "body": bl[bi][0], "pages": [bl[fi][1], bl[bi][1]]}
        out.append(x)
        print(f"{d}: first {bl[fi][0]} p{bl[fi][1]} {one(bl[fi][2])!r}\n      last  {bl[bi-1][0]} p{bl[bi-1][1]} {one(bl[bi-1][2])!r}\n      body  {bl[bi][0]} p{bl[bi][1]} {one(bl[bi][2])!r}")
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1)
