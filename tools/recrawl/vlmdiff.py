"""vlmdiff.py TRANSCRIPTION.txt [PAGE...] : every word a transcription and the document's OCR disagree on (read-only).

A vision-model reading can change one word in a fluent sentence ('signification' -> 'significance', 'Mortgagees' ->
'Mortgagors', doc 9594) and keep its paragraph's word-pair support high, so vlmdraft's flags never see it. Each page's
body words are aligned with its OCR's words (difflib); every replaced run, and every run the transcription has that
the OCR does not, is printed with its context, for a reader to settle against the page image. Runs only the OCR has
are printed when they are 4+ words (a side note the OCR interleaved is expected there; a dropped clause is not)."""
import difflib, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

src = open(sys.argv[1], encoding="utf-8").read()
doc = int(re.match(r"DOC (\d+)", src).group(1))
only = {int(p) for p in sys.argv[2:]}
W = re.compile(r"[A-Za-z0-9]+")
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT page_no, string_agg(text, ' ' ORDER BY block_no) FROM text_block WHERE document_id=%s GROUP BY 1", (doc,))
    ocr = {p: t or "" for p, t in cur.fetchall()}
parts = re.split(r"(?m)^=== p(\d+)[ \t]*\n", src)[1:]
n = 0
for k in range(0, len(parts), 2):
    p, body = int(parts[k]), parts[k + 1]
    if only and p not in only:
        continue
    body = "\n".join(x for x in body.splitlines() if not x.startswith("|"))
    body = re.sub(r"(?m)^@\d+\s+", "", body)
    a = [m.group(0) for m in W.finditer(body)]
    o = [m.group(0) for m in W.finditer(re.sub(r"-\s*\n\s*", "", ocr.get(p, "")))]
    sm = difflib.SequenceMatcher(None, [x.casefold() for x in a], [x.casefold() for x in o], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "insert" and j2 - j1 < 4):
            continue
        ctx = " ".join(a[max(0, i1 - 5):i1])
        aft = " ".join(a[i2:i2 + 4])
        n += 1
        print(f"p{p} {tag:7} [{' '.join(a[i1:i2])}] / ocr [{' '.join(o[j1:j2])[:120]}]   ...{ctx} _ {aft}")
print(f"-- {n} disagreements", file=sys.stderr)
