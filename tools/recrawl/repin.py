"""repin.py DOC PAGE : re-pin a pinned page of specs/transcribe-DOC.txt to the page's blocks in reading order,
skipping blocks under 12 characters and blocks whose whole text occurs (case folded, whitespace collapsed) in any of
the page's new paragraphs (such a block could not be located once another paragraph's text is in place). In place."""
import re, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, page = int(sys.argv[1]), int(sys.argv[2])
p = Path(f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/specs/transcribe-{doc}.txt")
src = p.read_text(encoding="utf-8")
m = re.search(rf"(?ms)^=== p{page}\n(\|[^\n]*\n)?(.*?)(?=^=== p|\Z)", src)
body = m.group(2)
paras = [re.sub(r"^@\d+\s+", "", x.strip()) for x in re.split(r"\n\s*\n", body) if x.strip()]
fl = lambda s: re.sub(r"\s+", " ", s).strip().casefold()   # noqa: E731
news = [fl(x) for x in paras]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, text FROM text_block WHERE document_id=%s AND page_no=%s ORDER BY block_no", (doc, page))
    blocks = [(i, t or "") for i, t in cur.fetchall()]
ok = [i for i, t in blocks if len(t.strip()) >= 12 and not any(fl(t) in n or fl(t)[:14] in n for n in news)]
assert len(ok) >= len(paras), (len(ok), len(paras), "not enough usable blocks")
# spread the paragraphs over the usable blocks in order (first paragraphs to first blocks)
new_body = "\n\n".join(f"@{b} {x}" for b, x in zip(ok, paras)) + "\n"
p.write_text(src[:m.start(2)] + new_body + src[m.end(2):], encoding="utf-8")
print(f"page {page}: {len(paras)} paragraphs on {len(ok)} usable blocks")
