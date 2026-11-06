"""patch_pages.py PATCH.json PAGE[,PAGE...] : keep only the records of the given pages in a patch file (in place)."""
import json, sys
p, pages = sys.argv[1], {int(x) for x in sys.argv[2].split(",")}
d = json.load(open(p, encoding="utf-8"))
json.dump([x for x in d if x["page_no"] in pages], open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
print(len([x for x in d if x["page_no"] in pages]), "record(s) kept")
