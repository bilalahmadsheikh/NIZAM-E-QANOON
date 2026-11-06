"""ptq.py TARGETS.json OUTROOT : one-page PDFs '<doc>-page<N>.pdf' for held E4 documents needing 1-4 target pages,
staged by need into OUTROOT/pt-in-1 .. pt-in-4 so the documents nearest to release are read first (read-only on DB).
Skips pages already read (OUTROOT/pt-output/<stem>/results.json) and documents now released or not E4."""
import json, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
t = json.load(open(sys.argv[1])); root = Path(sys.argv[2]); n = {}; docs = {}
with connect() as conn, conn.cursor() as cur:
    for d, ps in t.items():
        if not 0 < len(ps) <= 4: continue
        cur.execute("""SELECT d.lane, b.object_key, EXISTS(SELECT 1 FROM instrument i JOIN v_release_instrument r ON r.id=i.id
                              WHERE i.document_id=d.id) FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s AND d.is_active""", (int(d),))
        row = cur.fetchone()
        if not row or row[0] != "E4" or row[2]: continue
        out = root / f"pt-in-{len(ps)}"; out.mkdir(parents=True, exist_ok=True)
        src = pymupdf.open(Path("/mnt/e/nizam-data") / row[1])
        for p in ps:
            stem = f"{d}-page{p}"
            if (root / "pt-output" / stem / "results.json").exists() or (out / f"{stem}.pdf").exists(): continue
            o = pymupdf.open(); o.insert_pdf(src, from_page=p - 1, to_page=p - 1); o.save(out / f"{stem}.pdf")
            n[len(ps)] = n.get(len(ps), 0) + 1
        docs[len(ps)] = docs.get(len(ps), 0) + 1
print("docs by pages needed:", dict(sorted(docs.items())), "| page files written:", dict(sorted(n.items())))
