"""pt_skip_toc.py ROOT : move staged page PDFs (ROOT/pt-in-*/<doc>-page<N>.pdf) whose page holds contents rows of the
document's active instrument to ROOT/pt-skip-toc/ -- a re-read contents page changes contents detection for the
whole document (9563 -> 9664, 24 Oct). Read-only on the database."""
import re, shutil, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
root = Path(sys.argv[1]); skip = root / "pt-skip-toc"; skip.mkdir(exist_ok=True); n = 0
with connect() as conn, conn.cursor() as cur:
    for f in sorted(root.glob("pt-in-*/*.pdf")):
        m = re.fullmatch(r"(\d+)-page(\d+)", f.stem); d, p = int(m.group(1)), int(m.group(2))
        cur.execute("""SELECT count(*) FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id AND i.is_active
                        WHERE i.document_id=%s AND e.source_page=%s""", (d, p))
        if cur.fetchone()[0]:
            shutil.move(str(f), skip / f.name); n += 1
print(n, "contents-page files moved to", skip)
