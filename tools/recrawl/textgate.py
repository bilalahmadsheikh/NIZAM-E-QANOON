"""textgate.py DOC [MIN_OVERALL] [MIN_PAGE] : exit 0 when DOC's text reads as words, 1 when it does not (read-only).

A release made on structure counts alone can carry OCR damage the quality gate does not see -- printable_ratio counts
printable characters, not words (9733 p5 'Profecco, sch one a ... hell denn r gervice', released 28 Oct). Measured
on the LOWER-CASE words of the text (a capitalised word may be a name -- 'Rakh Kotli Qazi.', 'Tolly's Nala' -- that no
vocabulary holds), against a vocabulary of the words printed 30+ times across the released corpus
(tools/kaggle/mkvocab.py). Defaults: overall >= 0.96, and every page with 40+ lower-case words at >= 0.90.
--expression N checks one active canonical expression; missing/empty scopes fail without using raw fallback."""
import argparse,re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('document',type=int)
ap.add_argument('min_overall',type=float,nargs='?',default=0.96)
ap.add_argument('min_page',type=float,nargs='?',default=0.90)
ap.add_argument('--expression',type=int,help='Check only this active canonical expression ordinal; missing/empty expressions fail.')
args=ap.parse_args()
doc,min_all,min_page,expression=args.document,args.min_overall,args.min_page,args.expression
if expression is not None and expression<0:ap.error('--expression must be nonnegative')
vocab = set(open("/mnt/e/nizam-data/ocr/kaggle/vocab.txt").read().split())
with connect() as conn, conn.cursor() as cur:
    if expression is not None:
        cur.execute('SELECT count(*) FROM instrument WHERE document_id=%s AND expression_ordinal=%s AND is_active AND duplicate_of IS NULL',(doc,expression))
        if cur.fetchone()[0]!=1:sys.exit(f'{doc}/e{expression}: expected exactly one active canonical expression')
    # 29 Oct: measured on what is released -- the active instrument's provision text (curation patches applied, page
    # furniture set aside), by each provision's first page. Raw OCR blocks only when nothing is segmented: a page the
    # lead transcribed (9841) keeps its garbled raw reading underneath, which no reader ever sees.
    cur.execute("""SELECT p.first_page, string_agg(v.text_en, ' ') FROM instrument i
                     JOIN provision p ON p.instrument_id=i.id AND p.is_active
                     JOIN provision_version v ON v.provision_id=p.id
                    WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL
                      AND (%s::int IS NULL OR i.expression_ordinal=%s) GROUP BY 1 ORDER BY 1""", (doc,expression,expression))
    rows = cur.fetchall()
    if expression is not None and not any((text or '').strip()for _page,text in rows):sys.exit(f'{doc}/e{expression}: no nonblank active operative version text to check')
    if not rows:
        if expression is not None:sys.exit(f'{doc}/e{expression}: no active operative version text to check')
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
scope=f'{doc}/e{expression}'if expression is not None else str(doc)
print(f"{scope} text {'PASS' if ok else 'FAIL'} overall {overall:.1%}" + (f"; pages under {min_page:.0%}: {bad[:12]}" if bad else ""))
sys.exit(0 if ok else 1)
