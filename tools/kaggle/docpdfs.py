"""docpdfs.py SUFFIX GROUP DOC... : whole-document PDFs (the active documents' source files, named DOC.pdf) zipped as
in-GROUP.zip into E:/nizam-data/ocr/kaggle/ds-SUFFIX for `kg.sh dataset SUFFIX in-GROUP.zip` (read-only on the DB)."""
import pathlib, sys, zipfile
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
sfx, group, docs = sys.argv[1], sys.argv[2], sorted({int(d) for d in sys.argv[3:]})
ds = pathlib.Path(f"/mnt/e/nizam-data/ocr/kaggle/ds-{sfx}"); ds.mkdir(parents=True, exist_ok=True)
pages = 0
with connect() as conn, conn.cursor() as cur, zipfile.ZipFile(ds / f"in-{group}.zip", "w") as zf:
    for d in docs:
        cur.execute("""SELECT b.object_key, d.page_count, d.is_active FROM document d JOIN blob b ON b.sha256=d.sha256
                        WHERE d.id=%s""", (d,))
        key, n, active = cur.fetchone()
        if not active:
            print("skip inactive", d); continue
        zf.write(pathlib.Path("/mnt/e/nizam-data") / key, f"{d}.pdf")
        pages += n or 0
print(len(docs), "documents,", pages, "pages ->", ds / f"in-{group}.zip")
