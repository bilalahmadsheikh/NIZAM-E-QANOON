"""Offline sizing of diagnostic leads; never a release decision."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
def read(name):
    return json.loads((root / f"{name}.json").read_text())
items, gaps, s7, blocks = (read(n) for n in ("instruments", "toc", "s7", "blocks"))
lookup = {i["id"]:i for i in items}
blockmap = {b["id"]:b for b in blocks}
pageblocks = defaultdict(list)
for b in blocks:
    pageblocks[b["document_id"], b["page_no"]].append(b)
groups = defaultdict(list)
for g in gaps:
    if g["toc_entry_id"] is None:
        groups["TOC: run-only missing label; no actual entry anchor"].append(g)
    if re.fullmatch(r"(?:18|19|20)\d\d", g["printed_label"]):
        groups["TOC: year-shaped label (needs source check)"].append(g)
    if re.match(r"^(Faculties|Dean\b|Teaching Department|Boards? of Studies|Advanced Studies|Selection Board|Functions of Selection Board|Finance and Planning Committee|Functions of the Finance|Affiliation Committee|Disciplinary Committee)", g["printed_heading"] or "", re.I):
        groups["TOC: university schedule-heading lead"].append(g)
    if re.match(r"^(Subs\.|Ins\.|The words|For Statement|Cl\. .*ins\.)", g["printed_heading"] or "", re.I):
        groups["TOC: editorial-note-shaped entry"].append(g)
for s in s7:
    doc, page = s["document_id"], s["canonical_source_page"]
    if any(re.fullmatch(r"\s*(?:CONTENTS|ARRANGEMENT OF SECTIONS)[.\s]*", b["text"], re.I) for b in pageblocks[doc,page]):
        groups["S7: kept block on page explicitly marked CONTENTS"].append(s)
    if re.search(r"\b(?:rule|section|regulation)\s+" + re.escape(s["printed_label"]) + r"\s*\.\s*$", s["candidate_block_text"] or "", re.I) and not s["candidate_provision_text"]:
        groups["S7: empty candidate at trailing cross-reference"].append(s)
results = {}
for name,rows in groups.items():
    byinst=Counter(r["instrument_id"] for r in rows)
    blocker_key = "toc_count" if name.startswith("TOC") else "s7_count"
    other_key = "s7_count" if name.startswith("TOC") else "toc_count"
    only = [iid for iid,n in byinst.items() if n == lookup[iid][blocker_key] and lookup[iid][other_key] == 0]
    results[name] = dict(units=len(rows), instruments=len(byinst),
        instruments_with_all_pending_units_in_this_signal=len(only),
        documents=sorted({r["document_id"] for r in rows}),
        ids=[str(r.get("toc_entry_id") if name.startswith("TOC") else r["id"]) for r in rows])
    print(name, json.dumps({k:v for k,v in results[name].items() if k != "ids"}))
(root / "signals.json").write_text(json.dumps(results,indent=2))
lines = ["# Blocked-instrument inventory", "", "Snapshot: " + str(read("summary")["measured_at"]), "",
    "This is a blocker inventory, not a claim that each root cause has been visually reviewed.", "",
    "| Document | Instrument UUID | Title | TOC gaps | S7 pending | Missing labels |", "|---|---|---|---:|---:|---|"]
for i in sorted(items,key=lambda x:(x["toc_count"]+x["s7_count"],x["document_id"])):
    title = i["short_title"].replace("|","/").replace("\n"," ")
    lines.append(f'| {i["document_id"]} | {i["id"]} | {title} | {i["toc_count"]} | {i["s7_count"]} | {", ".join(i["labels"])} |')
(root / "INVENTORY.md").write_text("\n".join(lines)+"\n")
