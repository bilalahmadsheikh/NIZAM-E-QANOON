"""inventfilter.py IN_SPEC.json OUT_SPEC.json : keep, of a crossread.py spec, only the blocks that are INVENTED rather
than garbled -- fluent text (90%+ of its lower-case words in the corpus vocabulary that textgate.py uses, and 6+ such
words) that Tesseract does not support on a page it read well. A garbled block (OCR junk over a masthead, a smudged
line of law text) also scores no support, but it is not invented: it goes to the text-quality work, never set aside
here. Prints what it keeps; writes OUT only when something is kept. Read-only on the DB."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
vocab = set(open("/mnt/e/nizam-data/ocr/kaggle/vocab.txt", encoding="utf-8").read().split())
spec = json.load(open(sys.argv[1], encoding="utf-8"))
ids = [i for pg in spec["pages"].values() for i in pg["set_aside"]]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, text FROM text_block WHERE id = ANY(%s)", (ids,))
    text = dict(cur.fetchall())
out = {"document_id": spec["document_id"], "pages": {}}
for p, pg in spec["pages"].items():
    keep = []
    for i in pg["set_aside"]:
        words = re.findall(r"\b[a-z]{2,}\b", text.get(i) or "")
        share = sum(w in vocab for w in words) / max(1, len(words))
        if len(words) >= 6 and share >= 0.90:
            keep.append(i)
            print(f"  {spec['document_id']} p{p} b{i} fluent {share:.2f}: {(text[i] or '')[:110]!r}")
    if keep:
        out["pages"][p] = dict(pg, set_aside=keep)
if out["pages"]:
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{spec['document_id']}: {sum(len(v['set_aside']) for v in out['pages'].values())} invented of {len(ids)} flagged")
