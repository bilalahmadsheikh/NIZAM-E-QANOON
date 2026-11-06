"""vlmdraft.py DOC VLM.json [PAGE...] : a pagewrite transcription drafted from a vision-model page reading
(tools/kaggle/vlm_kernel.py), checked word by word against the document's own OCR (read-only on the DB).

Writes .artifacts/recrawl-queue/specs/transcribe-DOC.txt (an existing one is moved to .prevN) and
specs/vlmflags-DOC.txt. Each page's note lists the model's side notes, heads and footnotes (set aside). Each body
paragraph is checked against the page's OCR text: the share of its word pairs the OCR also reads ('support'), and the
words the OCR never has. A paragraph under SUPPORT_MIN, or with an unsupported number, is FLAGGED: a reader checks
exactly those spans against the page image and corrects them in the transcription before txgo.sh records anything.
The model's text is never recorded unread -- it can write fluent words that are not on the page."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

SUPPORT_MIN = 0.80
doc, vlm = int(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
only = {int(p) for p in sys.argv[3:]}
Q = Path("/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/specs")
W = re.compile(r"[a-z0-9]+")
norm = lambda s: W.findall(s.casefold().replace("ſ", "s"))   # noqa: E731

with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT page_no, string_agg(text, ' ' ORDER BY block_no) FROM text_block WHERE document_id=%s GROUP BY 1", (doc,))
    ocr = {p: t or "" for p, t in cur.fetchall()}
    cur.execute("SELECT page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
    blocks_by_page = {}
    for _p, _t in cur.fetchall():
        blocks_by_page.setdefault(_p, []).append(_t or "")

from collections import Counter
doc_words = Counter(x for t in ocr.values() for x in norm(t))


def _close(a, b):
    """the two spellings differ only by one silent 'e' (immovable/immoveable, judgment/judgement); nothing else --
    against a noisy OCR any wider rule turns real words into misreads ('clause' -> 'cause', doc 9717)"""
    if len(b) != len(a) + 1:
        return False
    return any(b[:i] + b[i + 1:] == a for i, ch in enumerate(b) if ch == "e")


def respell(para, oset):
    """the model modernises spelling ('immoveable' -> 'immovable'): a word the page's OCR does not have, of 6+ letters,
    whose close variant the OCR reads on this page and at least twice in the document, takes the OCR's spelling (the
    OCR read the letters on the page). Case of the first letter kept."""
    subs = []
    def fix(m):
        w = m.group(0); lw = w.casefold()
        if lw in oset or len(lw) < 6 or not lw.isalpha():
            return w
        cands = [o for o in oset if o.isalpha() and o[0] == lw[0] and _close(lw, o) and doc_words[o] >= 2]
        if len(cands) != 1:
            return w
        new = cands[0].capitalize() if w[0].isupper() else cands[0]
        subs.append((w, new))
        return new
    return re.sub(r"[A-Za-z]+", fix, para), subs


out, flags, nflag, npara = [f"DOC {doc}"], [], 0, 0
respelled = Counter()
for p in sorted(int(k) for k in vlm["pages"]):
    if only and p not in only:
        continue
    pg = vlm["pages"][str(p)]
    ow = norm(ocr.get(p, "")); oset, opairs = set(ow), set(zip(ow, ow[1:]))
    side = [x.strip() for x in (pg.get("side_notes") or "").splitlines() if x.strip() and x.strip().strip(".").casefold() not in ("none", "n/a", "-")]
    heads = [x.strip() for x in (pg.get("heads") or "").splitlines() if x.strip() and x.strip().strip(".").casefold() not in ("none", "n/a", "-")]
    foot = [x.strip() for x in (pg.get("footnotes") or "").splitlines() if x.strip() and x.strip().strip(".").casefold() not in ("none", "n/a", "-")]
    note = "; ".join(filter(None, [
        ("the running heads and furniture " + ", ".join(repr(h) for h in heads)) if heads else "",
        ("the side notes " + ", ".join(repr(s) for s in side)) if side else "",
        ("the footnotes " + ", ".join(repr(f) for f in foot)) if foot else ""]))
    out += [f"=== p{p}", "| " + (note or "nothing outside the text")]
    paras = [x.strip() for x in re.split(r"\n\s*\n", pg.get("body") or "") if x.strip()]
    for para in paras:
        npara += 1
        para, subs = respell(para, oset)
        respelled.update(subs)
        w = norm(para)
        pairs = list(zip(w, w[1:]))
        sup = (sum(1 for x in pairs if x in opairs) / len(pairs)) if pairs else (1.0 if all(x in oset for x in w) else 0.0)
        missing = [x for x in w if x not in oset]
        bad_num = [x for x in missing if x.isdigit()]
        if sup < SUPPORT_MIN or bad_num:
            nflag += 1
            flags.append(f"p{p} support {sup:.2f} unsupported: {' '.join(dict.fromkeys(missing))[:300]}\n    {para[:400]}")
        out += [para, ""]
    # the reverse check: the model can also DROP text (doc 9594 p20, most of section 47). Each OCR block's word pairs
    # must reappear in the model's reading of the page (body, notes, heads); a block of 12+ words with under half its
    # pairs there is flagged as possibly omitted.
    mw = norm(" ".join([pg.get("body") or "", pg.get("side_notes") or "", pg.get("heads") or "", pg.get("footnotes") or ""]))
    mpairs = set(zip(mw, mw[1:]))
    for bt in blocks_by_page.get(p, []):
        bw = norm(bt)
        bp = list(zip(bw, bw[1:]))
        if len(bw) >= 12:
            cov = sum(1 for x in bp if x in mpairs) / len(bp)
            if cov < 0.5:
                nflag += 1
                flags.append(f"p{p} OMITTED? only {cov:.2f} of an OCR block's word pairs are in the model's reading\n    {bt[:400]!r}")
dst = Q / f"transcribe-{doc}.txt"
if dst.exists():
    k = 1
    while (Q / f"transcribe-{doc}.prev{k}.txt").exists():
        k += 1
    dst.rename(Q / f"transcribe-{doc}.prev{k}.txt")
dst.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
(Q / f"vlmflags-{doc}.txt").write_text("\n".join(flags) + "\n", encoding="utf-8")
print(f"doc {doc}: {npara} paragraphs, {nflag} flagged for a page check -> {dst.name}, vlmflags-{doc}.txt")
if respelled:
    print("  respelled to the OCR's reading:", ", ".join(f"{a}->{b} x{n}" for (a, b), n in respelled.most_common(12)))
