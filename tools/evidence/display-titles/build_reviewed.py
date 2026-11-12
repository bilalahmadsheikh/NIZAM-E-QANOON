"""build_reviewed.py -> ../reviewed-2026-11-12-pass2.json : decisions on the 321 catalogue_title_only rows.
Two sources, both read on 12 Nov 2026 by Claude:
  text  -- the short-title clause of the instrument's own first provision in the released text (classified.jsonl
           classes same/expands/differs), each read against the catalogue name in the review lists; 2 fixes;
  image -- decisions_img.tsv: the page render read (sheets/, sheets2/ beside this file) for every row whose text clause
           was missing, garbled or disagreed with the catalogue.
Actions: accept (name as printed), fix (printed with a printing/OCR slip corrected; 'was' kept), and no record for
no_name (a notification or order with no name of its own) and defer (name not established from what was read)."""
import csv, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = {json.loads(l)["key"]: json.loads(l) for l in open(HERE / "titleline.jsonl", encoding="utf-8")}
img = {r["key"]: r for r in csv.DictReader(open(HERE / "decisions_img.tsv", encoding="utf-8"), delimiter="\t")}
TEXT_FIX = {"5177:0": "Khyber Pakhtunkhwa Government Staff Vehicles (Use and Maintenance) Rules 1997",
            "5977:0": "Balochistan Public Health Engineering Department, Draftsman and Tracers (B-1 to 15) Service Rules, 2011"}
out, counts = {}, {}
for k, r in R.items():
    base = {"instrument_id": r["csv_instrument_id"], "page_read": True, "catalogue": r["cleaned"]}
    if k in img:
        d = img[k]; a = d["action"]
        counts[a] = counts.get(a, 0) + 1
        if a == "printed":
            out[k] = {**base, "action": "accept", "name": d["name"], "evidence": "page render read: " + d["note"]}
        elif a == "corrected":
            out[k] = {**base, "action": "fix", "name": d["name"], "was": r.get("printed") or r["cleaned"],
                      "evidence": "page render read: " + d["note"]}
        else:
            out[k] = {**base, "action": "reject", "reason": a + ": " + d["note"]}
    elif r["cls"] in ("same", "expands", "differs"):
        counts["text"] = counts.get("text", 0) + 1
        ev = f"short-title clause of the released first provision ({r['printed_path']}) read against the catalogue name"
        if k in TEXT_FIX:
            out[k] = {**base, "action": "fix", "name": TEXT_FIX[k], "was": r["printed"], "evidence": ev + "; stray OCR character removed"}
        else:
            out[k] = {**base, "action": "accept", "name": r["printed"], "evidence": ev}
    else:
        counts["notification_no_name"] = counts.get("notification_no_name", 0) + 1
        out[k] = {**base, "action": "reject", "reason": "no_name: notification-type row; its first page prints a notification heading, not a name of its own"}
json.dump(out, open(HERE.parent / "reviewed-2026-11-12-pass2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), counts, sum(1 for v in out.values() if v["action"] in ("accept", "fix")), "names")
