"""mandem.py MANIFEST [U ...] : per S7 unit, the demoted and kept unit texts (read-only)"""
import json, re, sys
m = json.load(open(sys.argv[1], encoding="utf-8")); want = set(map(int, sys.argv[2:]))
for x in m:
    if want and x["u"] not in want: continue
    s = lambda k, n=400: re.sub(r"\s+", " ", x.get(k) or "")[:n]
    print(f"U{x['u']} doc {x['document_id']} label {x['printed_label']!r} kept {x['kept_block']} p{x['kept_page']} / demoted {x['demoted_block']} p{x['demoted_page']}")
    print("  K:", repr(s("kept_text"))); print("  D:", repr(s("demoted_text")))
