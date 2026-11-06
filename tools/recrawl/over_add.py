"""over_add.py OVER.json KEY JSONLIST : append entries to a list key of a trial overrides file (series-DOC.over.json)."""
import json, sys
p, k, v = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
o = json.load(open(p)); o.setdefault(k, []).extend(v); json.dump(o, open(p, "w")); print(k, len(o[k]))
