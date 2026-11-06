"""local_queue.py GROUP MAXPAGES OUTDIR : while the Kaggle GPU is unavailable, stage the still-unreleased documents of
an OCR bundle group (E:/nizam-data/ocr/colab/in/GROUP) whose results are not yet back, smallest first, as links in
OUTDIR for the local CPU queue (tools/run_surya_ocr.sh OUTDIR E:/nizam-data/ocr/colab/output). Read-only on the DB."""
import os, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
g, maxp, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
src = Path("/mnt/e/nizam-data/ocr/colab/in") / g; done = Path("/mnt/e/nizam-data/ocr/colab/output")
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT i.document_id FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL
                    AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)""")
    held = {r[0] for r in cur.fetchall()}
rows = []
for f in src.glob("*.pdf"):
    d = int(f.stem.split("-")[0])
    if d in held and not (done / f.stem / "results.json").exists():
        rows.append((pymupdf.open(f).page_count, f))
rows.sort()
n = p = 0
for pc, f in rows:
    if pc > maxp: continue
    link = out / f.name
    if not link.exists(): os.symlink(f, link)
    n += 1; p += pc
print(f"{g}: staged {n} held document(s), {p} pages (<= {maxp} pages each) of {len(rows)} pending")
