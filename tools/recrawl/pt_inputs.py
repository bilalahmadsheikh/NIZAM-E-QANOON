"""pt_inputs.py TARGETS.json MAXPAGES OUTDIR : one-page PDFs '<doc>-page<N>.pdf' for documents needing <= MAXPAGES
target pages, documents ordered by fewest pages first (read-only on the database)."""
import json, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
t = json.load(open(sys.argv[1])); mx = int(sys.argv[2]); out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
sel = sorted(((d, ps) for d, ps in t.items() if 0 < len(ps) <= mx), key=lambda kv: len(kv[1]))
n = 0
with connect() as conn, conn.cursor() as cur:
    for rank, (d, ps) in enumerate(sel):
        cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (int(d),))
        src = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
        for p in ps:
            f = out / f"{d}-page{p}.pdf"
            if f.exists():
                continue
            o = pymupdf.open(); o.insert_pdf(src, from_page=p - 1, to_page=p - 1); o.save(f); n += 1
print(len(sel), "documents;", n, "page files written to", out)
