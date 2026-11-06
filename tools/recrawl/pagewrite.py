"""pagewrite.py TRANSCRIPTION.txt SPEC.json : a blockfix spec from a page-by-page transcription (read-only on the DB).

TRANSCRIPTION: a first line 'DOC <id>', then for each page '=== p<N>' optionally followed by '| what else the page
prints' (set aside: heads, side notes, slips' amending lines, handwriting), then the page's printed paragraphs,
separated by blank lines, in reading order. Each paragraph replaces one of the page's blocks of 12+ characters, in
reading order; the page's other blocks are set aside. A division heading ('CHAPTER II' + title) should be its own
paragraph so it stays its own block. Refuses a page with more paragraphs than usable blocks."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
src = open(sys.argv[1], encoding="utf-8").read()
doc = int(re.match(r"DOC (\d+)", src).group(1))
pages = re.split(r"(?m)^=== p(\d+)[ \t]*\n", src)[1:]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
    blocks = {}
    for i, p, t in cur.fetchall():
        blocks.setdefault(p, []).append((i, t or ""))
spec = {"document_id": doc, "pages": {}}
for k in range(0, len(pages), 2):
    p, body = int(pages[k]), pages[k + 1]
    note = ""
    if body.startswith("|"):
        note, _, body = body.partition("\n")
        note = note[1:].strip()
    paras = [x.strip("\n") for x in re.split(r"\n[ \t]*\n", body.strip()) if x.strip()]
    # '@<block id> ' at a paragraph's start pins it to that block (a page whose blocks are mostly short contents rows)
    pins = [re.match(r"@(\d+)\s+", x) for x in paras]
    # a page pins all its paragraphs or none: a mixed page was homed, and its pins recorded as text (5 Nov 2026)
    if any(pins) and not all(pins):
        sys.exit(f"page {p}: paragraphs pinned and unpinned together: "
                 + repr(next(x for m, x in zip(pins, paras) if not m)[:60]))
    # ... and a pin opens a paragraph: one on a later line of a paragraph would be recorded as text
    inner = [ln for x in paras for ln in x.split("\n")[1:] if re.match(r"@\d+\s", ln)]
    if inner:
        sys.exit(f"page {p}: a pin inside a paragraph (no blank line before it): {inner[0][:60]!r}")
    if all(pins):
        rep = {m.group(1): x[m.end():] for m, x in zip(pins, paras)}
        aside = [i for i, _t in blocks[p] if str(i) not in rep]
        spec["pages"][str(p)] = {"set_aside": aside, "replace": rep,
            "observed": (note + "; " if note else "") + "the page's printed text, transcribed paragraph by paragraph"}
        continue
    # A block's HOME is the paragraph holding its opening words (whitespace and case ignored): each paragraph goes to
    # the first block homed in it, so a block's own text only ever lands in its own paragraph and its locator cannot
    # recur in another block's new text (patches apply in turn: a repeated locator would match two blocks). A
    # paragraph no block is homed in (the reading was garbled) takes the first free unhomed block between its
    # neighbours' blocks. Every other block is set aside.
    flat = lambda x: re.sub(r"\s+", " ", x).strip().casefold()   # noqa: E731
    fp = [flat(x) for x in paras]
    order = [(i, t) for i, t in blocks[p] if len(t.strip()) >= 12]
    home, seen = {}, set()
    for i, t in order:
        for n in (24, 48, 96):                     # a longer opening when a short one recurs (s.20 and s.21 tails)
            hits = [k for k, x in enumerate(fp) if flat(t)[:n] in x]
            if len(hits) <= 1 or n >= len(flat(t)):
                break
        if hits:
            seen.add(i)                            # real text: never a free block for another paragraph
        if len(hits) == 1:
            home[i] = hits[0]
    rep, owner = {}, {}
    for i, _t in order:
        k = home.get(i)
        if k is not None and k not in owner:
            owner[k] = i
    pos = {i: n for n, (i, _t) in enumerate(order)}
    # Blocks are replayed in block order: an owner out of that order (a Surya reading that numbered the columns'
    # blocks across each other, doc 9209 p2) would move its paragraph. Keep the longest run of owners in block order;
    # the paragraphs of the others fall back as unhomed ones (a free block between their neighbours, or appended).
    ks = sorted(owner)
    best = []                                   # longest increasing subsequence of block positions, O(n^2) is plenty
    for a in range(len(ks)):
        run = max((r for r in best if pos[owner[r[-1]]] < pos[owner[ks[a]]]), key=len, default=[])
        best.append(run + [ks[a]])
    keep = set(max(best, key=len, default=[]))
    owner = {k: i for k, i in owner.items() if k in keep}
    taken = set(owner.values())
    for k in range(len(paras)):
        if k in owner:
            continue
        lo = max((pos[owner[j]] for j in owner if j < k), default=-1)
        hi = min((pos[owner[j]] for j in owner if j > k), default=len(order))
        free = [i for i, _t in order[lo + 1:hi] if i not in taken and i not in seen]
        if free:
            owner[k] = free[0]; taken.add(free[0])
        # else: no block of its own -- it is appended to the paragraph before it, below
    ks = sorted(owner)
    assert ks, (p, "no paragraph has a block")
    if ks[0] != 0:
        # leading paragraphs no block is homed in (a vision-model reading whose first lines the OCR missed): they
        # open the first owned block's paragraph, in reading order
        owner[0] = owner.pop(ks[0])
        paras[0] = "\n".join(paras[:ks[0] + 1])
        for k in range(1, ks[0] + 1):
            paras[k] = None
        ks = sorted(owner)
    assert [pos[owner[k]] for k in ks] == sorted(pos[owner[k]] for k in ks), (p, "paragraph order != block order")
    rep = {}
    for k in range(len(paras)):
        if paras[k] is None:
            continue
        if k in owner:
            last = str(owner[k]); rep[last] = paras[k]
        else:
            rep[last] += "\n" + paras[k]
    aside = [i for i, _t in blocks[p] if str(i) not in rep]
    spec["pages"][str(p)] = {"set_aside": aside, "replace": rep,
        "observed": (note + "; " if note else "") + "the page's printed text, transcribed paragraph by paragraph"}
json.dump(spec, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"doc {doc}: {len(spec['pages'])} pages; " + ", ".join(f"p{p} {len(v['replace'])}/{len(v['replace']) + len(v['set_aside'])}"
                                                        for p, v in spec["pages"].items()))
