"""vlm_inputs.py SUFFIX DOC... : copy each document's source PDF to E:/nizam-data/ocr/kaggle/vlm-SUFFIX/<doc>.pdf for
the vision-model pre-read (tools/kaggle/vlm_kernel.py). Read-only on the DB."""
import shutil, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
suffix, docs = sys.argv[1], [int(d) for d in sys.argv[2:]]
dst = Path(f"/mnt/e/nizam-data/ocr/kaggle/vlm-{suffix}"); dst.mkdir(parents=True, exist_ok=True)
with connect() as conn, conn.cursor() as cur:
    for d in docs:
        cur.execute("SELECT b.object_key, d.page_count FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (d,))
        key, n = cur.fetchone()
        shutil.copy(Path("/mnt/e/nizam-data") / key, dst / f"{d}.pdf")
        print(d, n, "pages")
