"""pack.py READING.txt OUT.txt : a pinned pagewrite transcription from a page-by-page reading (read-only on the DB).

READING: 'DOC <id>', then per page '=== p<N>', an optional '| note' line, and the page's printed paragraphs in reading
order, blank-line separated; a page given with no paragraphs is set aside whole (a duplicate scan). The OCR's blocks need not follow reading order (two columns read across each other, doc 9572 pp.6-7): the
segmenter replays blocks in block order, so the paragraphs are spread, still in reading order, over the page's blocks
of 12+ characters taken in block order -- each block receiving the paragraphs whose start falls in its share of the
page's characters -- and every other block is set aside. Pages not in READING are left out of OUT."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

src = open(sys.argv[1], encoding="utf-8").read()
doc = int(re.match(r"DOC (\d+)", src).group(1))
parts = re.split(r"(?m)^=== p(\d+)[ \t]*\n", src)[1:]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
    blocks = {}
    for i, p, t in cur.fetchall():
        blocks.setdefault(p, []).append((i, t or ""))
out = [f"DOC {doc}"]
for k in range(0, len(parts), 2):
    p, body = int(parts[k]), parts[k + 1]
    note = ""
    if body.startswith("|"):
        note, _, body = body.partition("\n")
    # whitespace-only lines inside a paragraph are dropped: pagewrite reads one as a paragraph break, and the pin of
    # every paragraph on the page was then recorded as text (docs 4994, 9212, 9856, 9858, 9859, 5 Nov 2026)
    paras = ["\n".join(ln for ln in x.split("\n") if ln.strip())
             for x in re.split(r"\n[ \t]*\n", body.strip()) if x.strip()]
    # a paragraph over ~1000 characters is cut at its line breaks into pieces of about that size: a short block
    # cannot carry a page-long paragraph (blockfix cuts the OLD text at its line breaks, doc 9164 p2)
    _cut = []
    for x in paras:
        lines, cur = x.split("\n"), ""
        for ln in lines:
            if cur and len(cur) + len(ln) > 1000:
                _cut.append(cur); cur = ln
            else:
                cur = cur + "\n" + ln if cur else ln
        _cut.append(cur)
    paras = _cut
    out.append(f"=== p{p}")
    out.append(note or "| ")
    if not paras:
        out.append("")
        continue
    # 20+ characters: a block re-recorded needs a fresh locator prefix, and a 12-character block has one or two
    hosts = [(i, t) for i, t in blocks[p] if len(t.strip()) >= 20]
    # '@<block id> ' opening a paragraph pins it to that block (a running head or stray row the contents ledger would
    # otherwise read from the raw block, doc 9763 pp.2-4: the head '1877.] Broach ...' parsed as contents row 1877)
    pinned = {}
    for k, x in enumerate(paras):
        m = re.match(r"@(\d+)\s+", x)
        if m:
            b = int(m.group(1))
            if b not in [i for i, _t in hosts]:
                hosts.append(next((i, t) for i, t in blocks[p] if i == b))
            hosts.sort(key=lambda h: [i for i, _t in blocks[p]].index(h[0]))
            pinned[k] = b
            paras[k] = x[m.end():]
    raw = lambda x: re.sub(r"\s+", " ", x).strip().casefold()   # noqa: E731
    rp = [raw(x) for x in paras]
    # a block whose whole reading recurs inside another block of the page has no unique locator: never a host
    _pg = [raw(t) for _i, t in blocks[p]]
    hosts = [(i, t) for i, t in hosts if sum(raw(t) in x for x in _pg) == 1 or i in pinned.values()]
    # homes compare letters and digits only: an OCR '29, Appeal.' is the row '29. Appeal.' (doc 9763 p2, whose
    # unhomed contents block was anchored twice by the contents ledger)
    flat = lambda x: re.sub(r"[^a-z0-9]+", " ", x.casefold()).strip()   # noqa: E731
    fp = [flat(x) for x in paras]
    # A block whose opening the reading repeats (the OCR read it right) is HOMED on the paragraph holding that opening:
    # it hosts that paragraph, so its locator recurs only in its own new text (blockfix refuses a locator another
    # block's new text repeats, doc 9761 p14). Homes are kept in block order (longest increasing run); a block whose
    # opening recurs but is not kept is set aside. The other paragraphs are spread, in reading order, over the
    # unhomed blocks between their neighbours' homes, or appended to the paragraph before them.
    home = {}
    for n_, (i, t) in enumerate(hosts):
        hits = [k for k, x in enumerate(fp) if flat(t)[:20] in x]
        if len(hits) == 1:
            home[n_] = hits[0]
    # 'clean' (its locator would recur in new text) is judged as blockfix judges a locator: whitespace collapsed,
    # case folded, punctuation kept, over the block's first 40 characters -- an OCR line that ran two columns together
    # ('at which the Ship shall touch | Act, shall', doc 9540 p4) recurs in no transcription
    clean = {n_ for n_, (i, t) in enumerate(hosts) if any(raw(t)[:40] in x for x in rp)}
    # where a correctly read block's opening occurs: such a block may still host the one paragraph that holds it
    # (its locator then recurs only in its own new text; doc 9540 p3, whose right column is read cleanly)
    clean_in = {n_: {k for k, x in enumerate(rp) if raw(t)[:40] in x} for n_, (i, t) in enumerate(hosts)}
    ks = sorted(home)
    best = []
    for a_ in range(len(ks)):
        run = max((r for r in best if home[r[-1]] < home[ks[a_]]), key=len, default=[])
        best.append(run + [ks[a_]])
    keep = max(best, key=len, default=[])
    pin_h = {k: [i for i, _t in hosts].index(b) for k, b in pinned.items()}
    keep = [h for h in keep if home[h] not in pin_h and h not in pin_h.values()]
    # a home out of order with a pin gives way to the pin (doc 8962 p1: the OCR's 'e costs of management' block
    # follows the block pinned to the next paragraph)
    keep = [h for h in keep if all((home[h] < k) == (h < ph) for k, ph in pin_h.items())]
    anchor = {home[h]: h for h in keep}                  # paragraph -> host index
    anchor.update(pin_h)
    order = sorted(anchor.items())
    assert [h for _k, h in order] == sorted(h for _k, h in order), (p, "pinned blocks out of reading order")
    got = {}
    for k in range(len(paras)):
        if k in anchor:
            got.setdefault(anchor[k], []).append(paras[k])
            continue
        lo = max((h for q, h in anchor.items() if q < k), default=-1)
        hi = min((h for q, h in anchor.items() if q > k), default=len(hosts))
        free = [h for h in range(lo + 1, hi) if (h not in clean or clean_in[h] == {k})
                and h not in got and h not in pin_h.values()]
        if free:
            got[free[0]] = [paras[k]]
        else:
            prev = max((h for h in got if h < hi), default=None)
            assert prev is not None, (p, "no block for the page's first paragraph", paras[k][:60])
            got[prev].append(paras[k])
    for h, xs in sorted(got.items()):
        out.append(f"@{hosts[h][0]} " + "\n".join(xs))
        out.append("")
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n")
print(f"doc {doc}: " + ", ".join(f"p{int(parts[k])}" for k in range(0, len(parts), 2)) + f" -> {sys.argv[2]}")
