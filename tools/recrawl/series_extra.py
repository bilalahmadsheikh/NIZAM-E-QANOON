"""series_extra.py PATCH.json DOC PAGE KEY JSONVALUE DEFECT OBSERVED : add a structural key to the record of PAGE in a
series patch file (or a new record for that page) -- e.g. the reviewed contents region on the contents page."""
import json, sys
p, doc, page, key, val, defect, obs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], json.loads(sys.argv[5]), sys.argv[6], sys.argv[7]
R = json.load(open(p, encoding="utf-8"))
r = next((x for x in R if x["page_no"] == page), None)
if r is None:
    r = {"document_id": doc, "page_no": page, "defect": defect, "fixes": "", "observed": obs}; R.append(r)
else:
    r["defect"] += "; " + defect; r["observed"] += "; " + obs
r[key] = val
r["fixes"] = (r.get("fixes") or "") + ("; " if r.get("fixes") else "") + {
    "source_contents_region": "rule reviewed_contents_region: the contents list is bounded to its own pages (rows 'none': its series rows link to nothing) and the body starts at the Preface",
    "source_apparatus_blocks": "rule reviewed_apparatus_block: a divider page heading is not a unit",
    "source_division_openers": "rule reviewed_division_opener: the printed 'ANNEXURE-<n>' heading opens that annexure, its title line its heading"}.get(key, key)
R.sort(key=lambda x: x["page_no"])
json.dump(R, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
print(len(R), "records")
