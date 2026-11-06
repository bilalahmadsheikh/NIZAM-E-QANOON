"""add_to_bundle.py FOLDER DOC [DOC ...] : add whole documents to an extra Colab input zip
(E:/nizam-data/ocr/colab/in-<FOLDER>.zip, created or extended) -- for documents found later to need a re-read."""
import sys, zipfile
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
folder, docs = sys.argv[1], [int(d) for d in sys.argv[2:]]
z = Path(f"/mnt/e/nizam-data/ocr/colab/in-{folder}.zip")
have = set(zipfile.ZipFile(z).namelist()) if z.exists() else set()
with connect() as conn, conn.cursor() as cur, zipfile.ZipFile(z, "a", zipfile.ZIP_STORED) as zf:
    for d in docs:
        if f"{d}.pdf" in have: continue
        cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (d,))
        zf.write(Path("/mnt/e/nizam-data") / cur.fetchone()[0], f"{d}.pdf")
print(z.name, sorted(zipfile.ZipFile(z).namelist()))
