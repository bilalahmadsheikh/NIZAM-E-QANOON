"""rotpage.py DOC PAGE OUT.pdf : one-page PDF of DOC's page PAGE turned 180 degrees (a page printed upside down),
for a Surya re-read (read-only on the database)."""
import sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
d, p, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (d,))
    src = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
o = pymupdf.open(); o.insert_pdf(src, from_page=p - 1, to_page=p - 1); o[0].set_rotation((o[0].rotation + 180) % 360); o.save(out)
print("wrote", out)
