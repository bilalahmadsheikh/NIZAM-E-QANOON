"""mansum.py MANIFEST : one line per S7 unit -- label, kept and demoted page/length/opening text (read-only)"""
import json, re, sys
for x in json.load(open(sys.argv[1], encoding="utf-8")):
    s = lambda k: re.sub(r"\s+", " ", x[k] or "")[:45]
    print(x["u"], x["printed_label"], f"K p{x['kept_page']}", x["kept_len"], repr(s("kept_text")), f"| D p{x['demoted_page']}", x["demoted_len"], repr(s("demoted_text")))
