"""prefixdiff.py DUMP_DIR DOC... : compare stored and built with the instrument path prefix normalised."""
import json, pathlib, sys
dd = pathlib.Path(sys.argv[1])
for doc in sys.argv[2:]:
    for dp in sorted(dd.glob(f"{doc}_*.json")):
        d = json.loads(dp.read_text(encoding="utf-8")); f = d["fields"]
        norm = lambda p: p.split(".", 3)[3] if p.count(".") >= 3 else ""
        st = {norm(r[0]): dict(zip(f, r)) for r in d["stored"]}; bu = {norm(r[0]): dict(zip(f, r)) for r in d["built"]}
        pref = (d["stored"][0][0].split(".")[:3], d["built"][0][0].split(".")[:3])
        rem, add = sorted(set(st) - set(bu)), sorted(set(bu) - set(st))
        diff = [k for k in set(st) & set(bu) for c in ("kind", "label", "heading", "text")
                if (st[k].get(c) or "") != (bu[k].get(c) or "")]
        print(f"== {dp.stem} prefix {'.'.join(pref[0])} -> {'.'.join(pref[1])}: removed {rem[:5]} added {add[:5]} field-diffs {len(diff)} {sorted(set(diff))[:4]}")
