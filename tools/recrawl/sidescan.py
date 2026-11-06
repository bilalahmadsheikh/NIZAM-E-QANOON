"""sidescan.py DOC VLM.json : side notes a vision-model reading left inside the body (read-only).

The model lists each page's side notes, but it sometimes also keeps them inline, where the OCR interleaved them
(doc 9594 pp.3-18): word-pair support cannot see that, the OCR reads the same interleaving. Each run of 3+ words of
a side note (the page's own list, plus every 'N. title' line of an arrangement-of-sections page) that recurs in a
body paragraph out of place is printed with its context, for a reader to check against the page."""
import json, re, sys
from pathlib import Path
doc, vlm = int(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
W = re.compile(r"[A-Za-z0-9&]+")
titles = []
for p, pg in vlm["pages"].items():
    for x in (pg.get("side_notes") or "").splitlines():
        if len(W.findall(x)) >= 2:
            titles.append(x.strip())
    for x in (pg.get("body") or "").splitlines():
        m = re.match(r"\s*\d+[A-Z]?\.\s+(.{6,200})$", x)
        if m and len(x) < 220:
            titles.append(m.group(1).strip())
runs = set()
for t in titles:
    w = [x.casefold() for x in W.findall(t)]
    for n in range(len(w) - 2):
        runs.add(tuple(w[n:n + 3]))
for p in sorted(int(k) for k in vlm["pages"]):
    pg = vlm["pages"][str(p)]
    for para in re.split(r"\n\s*\n", pg.get("body") or ""):
        if len(para) < 220:                    # a contents row or heading is its own title
            continue
        toks = [(m.group(0).casefold(), m.start(), m.end()) for m in W.finditer(para)]
        hits = [k for k in range(len(toks) - 2) if tuple(t[0] for t in toks[k:k + 3]) in runs]
        if hits:
            k = hits[0]
            a, b = max(0, toks[k][1] - 60), min(len(para), toks[min(k + 2, len(toks) - 1)][2] + 60)
            print(f"p{p} [{len(hits)} runs] ...{para[a:b]}...".replace("\n", " "))
