"""pagefurniture.py DOC OUT.json REGEX... : apparatus records for a book reprint's page furniture (read-only on the DB).

A block is set aside when its WHOLE text (whitespace-collapsed) matches one of the REGEXes -- the running head, folio,
act head, running section guide '(Chapter I.--Preliminary.--Section 3.)', a margin citation 'XVI of 1877.' -- or when
it is a catchword: the last block of a page whose text (2-40 characters) is the start of the next page's first block
that is not itself furniture ('(c) any' at the foot of p10, '(c) any annual rate ...' at the head of p11).
One record per page, for tools/recrawl/patch.sh; prints every block it takes, for review."""
import json, re, sys
from collections import defaultdict
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write

args = [a for a in sys.argv[3:] if a != "--auto"]
doc, out, rxs = int(sys.argv[1]), sys.argv[2], [re.compile(r) for r in args]
flat = lambda s: re.sub(r"\s+", " ", s or "").strip()   # noqa: E731
pages = defaultdict(list)
for b in legal_write.blocks_for(doc):
    pages[b["page_no"]].append(b)
if "--auto" in sys.argv:
    # --auto: the furniture a code-book reprint prints on every page, found from the document itself. A short line
    # (up to 60 characters) among a page's first four or last three blocks whose shape -- digits taken out -- recurs
    # on at least 30% of the pages (and 3+) is a running head ('1889.] Central Provinces Municipalities. 233',
    # '[ACT XVII', '(Chapter I.--Preliminary.--Section 3.)'); so are a bare folio, a sheet mark, a margin citation of
    # an enactment ('XVI of 1877.') and the printer's mark ('L (iv) 31-54').
    shape = lambda s: re.sub(r"\d+", "#", flat(s)).strip(" .")   # noqa: E731
    edge = lambda bs: bs[:4] + bs[-3:]   # noqa: E731
    seen = defaultdict(set)
    for p, bs in pages.items():
        for b in edge(bs):
            t = flat(b["text"])
            if 0 < len(t) <= 60:
                seen[shape(t)].add(p)
    # 15%: after a partial re-read the running head is printed one way on the re-read pages and another on the rest
    # (doc 9785: '1889.] Central Provinces Municipalities. 241' on 16 of 67 pages, variants on the others)
    floor = max(3, int(0.15 * len(pages)))
    heads = {k for k, ps in seen.items() if len(ps) >= floor and re.search(r"[A-Za-z]", k)}
    # the head's title core ('Central Provinces Municipalities'): any short edge line holding it is the same head
    cores = {max(re.findall(r"[A-Za-z][A-Za-z ,'&-]{11,}[A-Za-z]", k), key=len, default="") for k in heads}
    cores = {c for c in cores if len(c) >= 12 and not c.startswith(("Chapter", "CHAPTER"))}
    rxs += [re.compile(r"\d{1,4}"), re.compile(r"[A-Z]"), re.compile(r"[IVXL]{1,7} of 1[6-9]\d\d\.?"),
            re.compile(r"L\s*\(iv\)\s*\d+\s*[-—–]+\s*\d+"), re.compile(r"\[?\d{4}\.?\]"),
            re.compile(r"\((?:Chapter|Schedule|Part)\b[^()]{3,120}\)?")]
    for p, bs in pages.items():
        for b in edge(bs):
            t = flat(b["text"])
            if shape(t) in heads or (len(t) <= 70 and any(c in t and len(t) <= len(c) + 28 for c in cores)):
                b["_auto_head"] = True
    print("auto running heads:", sorted(heads)[:12], "cores:", sorted(cores))
take = defaultdict(list)
for p, bs in pages.items():
    for b in bs:
        if b.get("_auto_head") or any(r.fullmatch(flat(b["text"])) for r in rxs):
            take[p].append((b["id"], flat(b["text"]), "head"))
for p, bs in pages.items():
    if not bs or p + 1 not in pages:
        continue
    # the last block that is not furniture: a sheet mark ('9', 'R') may follow the catchword at the foot
    rest = [b for b in bs if all(b["id"] != i for i, _, _ in take[p])]
    if not rest:
        continue
    last = rest[-1]
    # the next page's first three content blocks: a side note may stand before the section the catchword repeats
    # ('7. (1) There' at the foot of p12; p13 prints the side note 'Financial Commissioner.' then '7. (1) There shall')
    nxt = [b for b in pages[p + 1] if all(b["id"] != i for i, _, _ in take[p + 1])][:3]
    lt = flat(last["text"])
    # a heading may be repeated whole: 'CHAPTER VI.' at the foot of p33 and again at the head of p34 (doc 9695)
    if 2 <= len(lt) <= 40 and any(flat(b["text"]).startswith(lt) for b in nxt):
        take[p].append((last["id"], lt, "catchword"))
recs = []
for p in sorted(take):
    items = take[p]
    kinds = sorted({k for _, _, k in items})
    recs.append({"document_id": doc, "page_no": p, "source_apparatus_blocks": [i for i, _, _ in items],
                 "defect": "the page's furniture (" + ", ".join(kinds) + ") was read into the provisions' text",
                 "fixes": "rule reviewed_apparatus_block: running head, folio, running section guide, margin citations "
                          "and the catchword repeating the next page's first words are set aside",
                 "observed": f"Page {p} prints " + "; ".join(f"{t!r} ({k})" for _, t, k in items),
                 "render": f".artifacts/release-work-2026-09-24/claude/renders/doc{doc}-p{p}.png"})
    print(f"p{p}: " + " | ".join(f"{t[:40]}{'*' if k == 'catchword' else ''}" for _, t, k in items))
json.dump(recs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(recs), "pages;", sum(len(v) for v in take.values()), "blocks;",
      sum(1 for v in take.values() for _, _, k in v if k == "catchword"), "catchwords")
