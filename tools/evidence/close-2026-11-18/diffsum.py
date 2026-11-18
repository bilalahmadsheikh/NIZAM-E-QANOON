"""diffsum.py DUMP_DIR [DOC] : per document, what a rebuild changes against the stored release."""
import difflib, json, pathlib, sys, collections
dd = pathlib.Path(sys.argv[1]); only = sys.argv[2] if len(sys.argv) > 2 else None
for dp in sorted(dd.glob("*.json")):
    if only and not dp.name.startswith(only + "_"):
        continue
    d = json.loads(dp.read_text(encoding="utf-8")); f = d["fields"]
    st = {r[0]: dict(zip(f, r)) for r in d["stored"]}; bu = {r[0]: dict(zip(f, r)) for r in d["built"]}
    rem, add = sorted(set(st) - set(bu)), sorted(set(bu) - set(st))
    ch = collections.Counter(); ex = {}
    for p in set(st) & set(bu):
        for k in ("kind", "label", "parent", "heading", "text"):
            if (st[p].get(k) or "") != (bu[p].get(k) or ""):
                ch[k] += 1; ex.setdefault(k, (p, (st[p].get(k) or "")[:90], (bu[p].get(k) or "")[:90]))
    short = lambda p: p.split(".", 2)[-1]
    print(f"== {dp.stem}: stored {len(st)} built {len(bu)}  removed {len(rem)} added {len(add)}  changed {dict(ch)}")
    if rem: print("   removed:", [short(p) for p in rem[:6]])
    if add: print("   added:  ", [short(p) for p in add[:6]])
    for k, (p, a, b) in ex.items():
        print(f"   {k} @ {short(p)}:\n      stored {a!r}\n      built  {b!r}")
