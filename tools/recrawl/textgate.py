"""textgate.py DOC [MIN_OVERALL] [MIN_PAGE] : exit 0 when DOC's text reads as words, 1 when it does not (read-only).

A release made on structure counts alone can carry OCR damage the quality gate does not see -- printable_ratio counts
printable characters, not words (9733 p5 'Profecco, sch one a ... hell denn r gervice', released 28 Oct). Measured
on the LOWER-CASE words of the text (a capitalised word may be a name -- 'Rakh Kotli Qazi.', 'Tolly's Nala' -- that no
vocabulary holds), against a vocabulary of the words printed 30+ times across the released corpus
(tools/kaggle/mkvocab.py). Defaults: overall >= 0.96, and every page with 40+ lower-case words at >= 0.90."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc = int(sys.argv[1])
min_all = float(sys.argv[2]) if len(sys.argv) > 2 else 0.96
min_page = float(sys.argv[3]) if len(sys.argv) > 3 else 0.90
vocab = set(open("/mnt/e/nizam-data/ocr/kaggle/vocab.txt").read().split())
with connect() as conn, conn.cursor() as cur:
    # 29 Oct: measured on what is released -- the active instrument's provision text (curation patches applied, page
    # furniture set aside), by each provision's first page. Raw OCR blocks only when nothing is segmented: a page the
    # lead transcribed (9841) keeps its garbled raw reading underneath, which no reader ever sees.
    cur.execute("""SELECT p.first_page, string_agg(v.text_en, ' ') FROM instrument i
                     JOIN provision p ON p.instrument_id=i.id AND p.is_active
                     JOIN provision_version v ON v.provision_id=p.id
                    WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL GROUP BY 1 ORDER BY 1""", (doc,))
    rows = cur.fetchall()
    if not rows:
        cur.execute("""SELECT page_no, string_agg(text, ' ') FROM text_block WHERE document_id=%s
                        AND coalesce(script,'latin')='latin' GROUP BY 1 ORDER BY 1""", (doc,))
        rows = cur.fetchall()
    tot = hit = 0
    bad = []
    for p, t in rows:
        low = [w for w in re.findall(r"[A-Za-z]{2,}", t or "") if w.islower()]
        h = sum(w in vocab for w in low)
        tot += len(low); hit += h
        if len(low) >= 40 and h / len(low) < min_page:
            bad.append((p, round(h / len(low), 2)))
overall = hit / tot if tot else 1.0
ok = overall >= min_all and not bad
print(f"{doc} text {'PASS' if ok else 'FAIL'} overall {overall:.1%}" + (f"; pages under {min_page:.0%}: {bad[:12]}" if bad else ""))
sys.exit(0 if ok else 1)
