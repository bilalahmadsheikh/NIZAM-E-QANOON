"""draft.py DOC [PAGE...] : a pinned pagewrite transcription drafted from the document's current block texts
(read-only on the DB) -> .artifacts/recrawl-queue/specs/transcribe-DOC.txt (refuses to overwrite one).

Every block becomes a paragraph '@<block id> <text>' in reading order, under '=== p<N>' and an empty '| ' note line.
The reader then corrects it against the page renders: deletes the paragraphs of blocks that are apparatus (heads,
side notes, margin citations, signatures -- an unpinned block is set aside), mends misread words, and states in the
note what the page prints outside the text. Nothing here is a reading until that is done."""
import sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

doc = int(sys.argv[1])
pages = {int(p) for p in sys.argv[2:]}
out = Path(f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/specs/transcribe-{doc}.txt")
if out.exists():
    sys.exit(f"{out} exists; move it aside first")
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
    rows = [r for r in cur.fetchall() if not pages or r[1] in pages]
lines, last = [f"DOC {doc}"], None
for i, p, t in rows:
    if p != last:
        lines += [f"=== p{p}", "| "]
        last = p
    lines += [f"@{i} " + (t or "").strip().replace("\n\n", "\n"), ""]
out.write_text("\n".join(lines), encoding="utf-8")
print(out, len(rows), "blocks")
