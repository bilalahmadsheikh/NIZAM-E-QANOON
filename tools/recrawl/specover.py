"""specover.py SPEC.json EDITS.json : merge the edits' reviewed structural overrides into a pagewrite spec, per page
({"overrides": {"<page>": {key: value}}, "overrides_fix": {"<page>": "what the override records"}}). In place."""
import json, sys
spec = json.load(open(sys.argv[1], encoding="utf-8"))
ed = json.load(open(sys.argv[2], encoding="utf-8"))
for p, ov in (ed.get("overrides") or {}).items():
    spec["pages"][p].setdefault("overrides", {}).update(ov)
    if (ed.get("overrides_fix") or {}).get(p):
        spec["pages"][p]["overrides_fix"] = ed["overrides_fix"][p]
json.dump(spec, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
