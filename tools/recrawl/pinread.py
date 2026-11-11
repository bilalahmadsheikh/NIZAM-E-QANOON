"""pinread.py DOC [UNPINNED_FILE] : pin every reading paragraph of specs/read-DOC.txt to the OCR/text-layer block it was read from.
Word-level alignment (difflib) of the page's blocks against the page's reading lines; each line goes to the block that holds most of its
matched words, never backwards (a scrambled block order keeps the printed order of the text); the lines of one block form one paragraph.
A block that cannot take a fresh unique locator (a short list line that other blocks repeat) hands its lines to the block before it.
Reads the UNPINNED file when given (the pinning is redone from it every time). Prints warnings where a block would hold two Articles."""
import difflib, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc = int(sys.argv[1])
P = f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/specs/read-{doc}.txt"
src = open(sys.argv[2] if len(sys.argv) > 2 else P, encoding="utf-8", newline="").read()
head, *rest = re.split(r"(?m)^(=== p\d+)[ \t]*\n", src)
tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())   # noqa: E731
fl = lambda s: re.sub(r"\s+", " ", s).casefold()      # noqa: E731
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
    blocks = {}
    for i, p, t in cur.fetchall():
        blocks.setdefault(p, []).append((i, t or ""))
    cur.execute("""SELECT DISTINCT page_no, match_text, before_text FROM segmentation_curation_patch WHERE source_observation_id IN
                     (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (doc,))
    used_triples = set(cur.fetchall())


def locatable(p, old, page_blocks, reading_flat):
    """a window of the block's text that is fresh, once in the page's blocks and once in the page's whole new text"""
    cands = [old[:k] for k in [len(old)] + list(range(12, len(old)))]
    for ln in old.split("\n"):
        cands += [ln[k:e] for k in range(max(0, len(ln) - 11)) for e in range(len(ln), k + 11, -1)]
    for m in cands:
        if len(m.strip()) < 12 or m.strip() != m and m != old[:len(m)]:
            continue
        if (p, m, old) in used_triples:
            continue
        if sum(fl(t).count(fl(m)) for t in page_blocks) == 1 and fl(m) not in fl(reading_flat):   # reading_flat: the OTHER groups' new text
            return True
    return False


out = [head]
warn, merged_n = [], 0
for k in range(0, len(rest), 2):
    tag, body = rest[k], rest[k + 1]
    p = int(tag[5:])
    note = ""
    if body.startswith("|"):
        note, _, body = body.partition("\n")
    lines = [re.sub(r"^@\d+\s+", "", l) for l in body.split("\n") if l.strip()]
    if not lines:
        out.append(f"{tag}\n{note}\n")
        continue
    bl = [(i, t) for i, t in blocks.get(p, []) if len(t.strip()) >= 12]
    page_blocks = [t for _i, t in blocks.get(p, [])]
    A, ablk = [], []
    for n, (i, t) in enumerate(bl):
        for w in tok(t):
            A.append(w); ablk.append(n)
    B, bln = [], []
    for n, l in enumerate(lines):
        for w in tok(l):
            B.append(w); bln.append(n)
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    votes = [dict() for _ in lines]
    for m in sm.get_matching_blocks():
        for d in range(m.size):
            v = votes[bln[m.b + d]]
            v[ablk[m.a + d]] = v.get(ablk[m.a + d], 0) + 1
    assign, ptr, first = [], 0, None
    for n, l in enumerate(lines):
        best = max(votes[n], key=lambda b: votes[n][b]) if votes[n] else None
        if best is not None and first is None:
            first = best
        if best is None:
            best = ptr if first is not None else None
        elif best < ptr:
            best = ptr
        if best is not None:
            ptr = best
        assign.append(best)
    if first is None:
        sys.exit(f"page {p}: no line of the reading matches any block")
    assign = [first if a is None else a for a in assign]
    groups = []
    for n, a in enumerate(assign):
        if groups and groups[-1][0] == a:
            groups[-1][1].append(lines[n])
        else:
            groups.append([a, [lines[n]]])
    reading_flat = "\n".join(lines)
    # the segmenter starts an Article only at the start of a block: where one block holds the end of an Article and the start of the
    # next (the OCR ran two paragraphs together), the lines before the label go to the block before (replacements need not keep
    # the OCR's block boundaries, only the printed order)
    art = re.compile(r"(Articles?\s+\d+\s*[.—-]|(CHAPTER|Chapter|PART|Part)\s+([IVXLC]+|\d+)\b)")
    gi = 0
    while gi < len(groups):
        a, ls = groups[gi]
        cut = next((n for n, x in enumerate(ls) if n > 0 and art.match(x)), None)
        if cut is not None and gi > 0:
            groups[gi - 1][1] += ls[:cut]
            groups[gi][1] = ls[cut:]
            continue
        gi += 1
    # a group whose block cannot take a fresh unique locator joins the group before it (the first joins the next)
    changed = True
    while changed and len(groups) > 1:
        changed = False
        for gi, (a, ls) in enumerate(groups):
            others = "\n".join("\n".join(g[1]) for g in groups if g is not groups[gi])
            if not locatable(p, bl[a][1], page_blocks, others):
                if gi > 0:
                    groups[gi - 1][1] += ls
                    del groups[gi]
                else:
                    groups[1][1] = ls + groups[1][1]
                    groups[1][0] = groups[0][0] if False else groups[1][0]
                    del groups[0]
                merged_n += 1
                print("  merged (no fresh locator):", p, bl[a][0], repr(bl[a][1][:50]), "->", repr(ls[0][:40]))
                changed = True
                break
    for a, ls in groups:
        arts = [x for x in ls[1:] if re.match(r"Articles?\s+\d+\s*[.—-]", x)]
        if arts:
            warn.append((p, bl[a][0], arts[0][:50]))
    out.append(f"{tag}\n{note}\n" + "\n\n".join(f"@{bl[a][0]} " + "\n".join(ls) for a, ls in groups) + "\n")
open(P, "w", encoding="utf-8", newline="").write("\n".join(o.rstrip("\n") + "\n" for o in out))
print("pages pinned; blocks merged into a neighbour (no fresh locator):", merged_n, "; warnings (a block would hold a second Article):", len(warn))
for w in warn:
    print("  ", w)

