"""mkvocab.py : the corpus vocabulary rotchoose.py and the quality checks use -- words printed 30+ times in a 20% sample
of released provision text -- written to E:/nizam-data/ocr/kaggle/vocab.txt (read-only on the DB)."""
import pathlib, re, sys
from collections import Counter
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
freq = Counter()
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT v.text_en FROM v_release_instrument r JOIN provision p ON p.instrument_id=r.id AND p.is_active
                    JOIN provision_version v ON v.provision_id=p.id WHERE random() < 0.2""")
    for (t,) in cur:
        freq.update(w.lower() for w in re.findall(r"[A-Za-z]{2,}", t or ""))
vocab = sorted(w for w, n in freq.items() if n >= 30)
pathlib.Path("/mnt/e/nizam-data/ocr/kaggle/vocab.txt").write_text("\n".join(vocab))
print(len(vocab), "words")
