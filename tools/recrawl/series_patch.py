"""series_patch.py DOC SUFFIX : turn .artifacts/recrawl-queue/series-DOC.over.json (series_trial.sh) into curation-patch
records, one per page (the openers of that page), for patch.sh DOC apply SUFFIX -- rule `reviewed_series_regulation`
(owner chat 28 Oct 2026 'release 6 with 1 numbering rule'). Read-only on the database."""
import json, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
doc, suf = int(sys.argv[1]), sys.argv[2]
ops = json.load(open(f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/series-{doc}.over.json"))["source_printed_rule_openers"]
blocks = legal_write.blocks_for(doc)
page = {b["id"]: b["page_no"] for b in blocks}
text = {b["id"]: b["text"] or "" for b in blocks}
def heading(o):
    """the printed heading line(s) of the opener, from its prefix to the end of the next line (what the page shows)"""
    t = text[o["source_block_id"]]; i = t.find(o["source_prefix"])
    return " ".join(t[i:].split("\n")[:2]).strip()[:120]
by = {}
for o in ops:
    by.setdefault(page[o["source_block_id"]], []).append(o)
R = [{"document_id": doc, "page_no": p, "source_printed_rule_openers": v,
      "defect": "the regulations are numbered in a lettered series ('Regulation R-1', 'HF 1', 'IPF.1.1') that no rule of the "
                "parser reads, so they were not opened and their text ran into the definitions or each other",
      "fixes": "rule reviewed_series_regulation: each reviewed 'Regulation <series> <n>' heading opens that regulation, "
               "labelled as printed; its numbered paragraphs are its sub-sections",
      "observed": f"Page {p} prints the regulation heading(s) " + "; ".join(repr(heading(x)) for x in v)
                  + ", each followed by that regulation's text"} for p, v in sorted(by.items())]
json.dump(R, open(f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/patches/patch-{doc}{suf}.json", "w", encoding="utf-8",
                  newline="\n"), ensure_ascii=False, indent=1)
print(f"doc {doc}: {len(ops)} openers on {len(R)} page(s)")
