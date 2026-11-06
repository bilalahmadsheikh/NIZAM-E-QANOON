"""noteweave.py DOC OUT.json [--block ID] : side notes the OCR threaded word by word through the law text, found
from the document's own contents headings and lifted out (read-only on the DB; prints every cut for review).

A two-column reprint prints each section's side note in the margin; Surya reads margin and text line by line and
interleaves them: '27. Any person dissatisfied with any order Appeal from order on under section twenty-six
petition. may, within ...' (doc 9826 p5: note 'Appeal from order on petition.'). The contents print the same words
('27. Appeal from order on petition.'), so a heading's words found IN ORDER inside a block, its first word
capitalised and not at the block's start, its last word carrying the heading's stop, with at most 10 law words
between them and no more than 2 law words per gap on average, are the note: those words (and that stop) are cut,
the law words kept. sidenote_strip.py handles a note printed whole; this one the interleaved ones.
Every cut is printed before -> after; OUT.json holds one parser-input patch per block for patch.sh."""
import hashlib, json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from pathlib import Path

args = sys.argv[1:]
only = int(args[args.index("--block") + 1]) if "--block" in args else None
doc, out = int(args[0]), args[1]
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
TOK = re.compile(r"\S+")
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT DISTINCT e.printed_heading FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id
                    WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL""", (doc,))
    heads = [re.sub(r"\s+", " ", h).strip() for (h,) in cur.fetchall() if h]
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
    blocks = cur.fetchall()
    cur.execute("""SELECT DISTINCT e.source_block_id FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id
                    WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL""", (doc,))
    contents = {r[0] for r in cur.fetchall()}
# heading token lists: 2+ words, first capitalised; stop kept on the last token for matching
H = []
for h in heads:
    h = re.sub(r"^\d+[A-Z]?\.\s*", "", h).strip(" |")
    toks = h.split()
    if len(toks) >= 2 and toks[0][:1].isupper():
        H.append(toks)
H.sort(key=len, reverse=True)
norm = lambda w: re.sub(r"[^\w]", "", w).lower()   # noqa: E731


def find(words, toks):
    """indices in `words` of the heading tokens, matched in order with small law-word gaps, or None"""
    n = len(toks)
    for s in range(1, len(words)):
        if words[s] != toks[0]:               # the note's first word exactly, capitalised
            continue
        idx, j, k = [s], 1, s + 1
        while j < n and k < len(words) and k - idx[-1] <= 6:
            if norm(words[k]) == norm(toks[j]):
                idx.append(k); j += 1
            k += 1
        if j < n:
            continue
        inner = (idx[-1] - idx[0] + 1) - n
        if inner > 10 or inner > 2 * (n - 1):
            continue
        last = words[idx[-1]]
        if toks[-1][-1:] in ".," and last[-1:] not in ".,":
            continue
        return idx
    return None


recs, cuts = [], 0
for bid, page, text in blocks:
    if bid in contents or (only and bid != only):
        continue
    spans = [(m.start(), m.end()) for m in TOK.finditer(text)]
    words = [text[a:b] for a, b in spans]
    drop = set()
    for toks in H:
        idx = find(words, toks)
        if idx and not drop.intersection(idx):
            drop.update(idx)
    if not drop:
        continue
    kept = [w for i, w in enumerate(words) if i not in drop]
    new = " ".join(kept)
    old_flat = " ".join(words)
    print(f"  p{page} b{bid}:\n     {old_flat[:260]}\n  -> {new[:260]}")
    cuts += 1
    render = f".artifacts/release-work-2026-09-24/claude/renders/doc{doc}-p{page}.png"
    rp = ROOT / render
    recs.append({"document_id": doc, "page_no": page, "match_text": text, "before_text": text, "after_text": new,
                 "defect": "the margin side note was read into the law text word by word, interleaved with the line",
                 "fixes": "parser-input correction: the side note's words (the section's contents heading) are lifted out "
                          "of the line, the law words kept in order",
                 "observed": f"Page {page} prints the law text '{new[:200]}' with the side note in the margin",
                 "render": render, "render_sha256": hashlib.sha256(rp.read_bytes()).hexdigest() if rp.exists() else None})
json.dump(recs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"doc {doc}: {cuts} block(s) with an interleaved note; {len(H)} contents headings")
