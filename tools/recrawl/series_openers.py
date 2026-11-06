"""series_openers.py DOC FIRST_BODY_PAGE [SERIES_RX] : list the reviewed-opener candidates of rule
`reviewed_series_regulation` for an SBP prudential-regulations document -- every 'Regulation <series> <n>' (or a bare
SERIES_RX label, e.g. 'IPF') that starts a line of a body block on or after FIRST_BODY_PAGE -- as
source_printed_rule_openers entries (JSON on stdout) plus a readable list on stderr. Read-only."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
from nizam.corpus.segment import _SERIES_LABEL
doc, first = int(sys.argv[1]), int(sys.argv[2]); bare = sys.argv[3] if len(sys.argv) > 3 else None
head = r"(?:(?i:Regulation)\s+)" + ("?" if bare else "")
ser = rf"((?:{bare})|[A-Z]{{1,4}}(?: [A-Z]{{1,3}})?)" if bare else r"([A-Z]{1,4}(?: [A-Z]{1,3})?)"
RX = re.compile(r"(?m)^[ \t]*(" + head + ser + r"[ \t]*([-\u2013.]?)[ \t]*(\d{1,2}(?:[ \t]*\.[ \t]*\d{1,2}){0,3}))(?![\d.])"
                r"(?=[ \t]*(?:[:\u2014-]|\u2013|[ \t]+[A-Za-z]|\n|$))")
out, seen = [], set()
for b in legal_write.blocks_for(doc):
    if b["page_no"] < first:
        continue
    t = b["text"] or ""
    for m in RX.finditer(t):
        sep = "-" if m.group(3) in "-\u2013" and m.group(3) else ("." if m.group(3) == "." else " ")
        nums = re.sub(r"[ \t]", "", m.group(4))
        label = f"{m.group(2)}{sep}{nums}"
        if not _SERIES_LABEL.fullmatch(label) or label in seen or (bare and m.group(2) != bare):
            # with a bare series ('IPF'), only that series -- 'Regulation R-8' in an annex of 8062 cites another PR
            continue
        rest = t[m.start(1):]
        prefix = rest[:max(len(m.group(1)) + 8, 14)]   # a heading-only block keeps its newline: it ends the label
        if t.count(prefix) != 1:
            continue
        seen.add(label)
        out.append({"source_block_id": b["id"], "kind": "section", "label": label, "source_prefix": prefix})
        print(f"p{b['page_no']} b{b['id']} {label!r:14} {prefix!r}", file=sys.stderr)
print(json.dumps(out, ensure_ascii=False))
