"""sindh_title_proof.py DUMP_DIR PATCH_DIR OUT_JSON -- prove, document by document, that the running-head readings
change nothing but the head itself.

Reads the release gate's own tree dumps (segment --dry-run --release-diff --release-tree-dump) of every document
with a patch-<doc>t.json. A document PASSES only when, between its stored release and its rebuild:
  * no path is removed or added (setting a block aside must not drop a provision it opened -- 15 Nov 2026);
  * no kind, label, parent or heading changes;
  * every text change is a pure deletion, and every deleted word is a word of that document's printed running head
    (its title, citation and folio lines, as the readings record them).
Writes {"pass": [...], "fail": {doc: reason}} to OUT_JSON and prints totals."""
import collections
import difflib
import json
import pathlib
import re
import sys

dump_dir, patch_dir, out = map(pathlib.Path, sys.argv[1:4])
suffix = sys.argv[4] if len(sys.argv) > 4 else "t"     # 't' running heads (Sindh), 'f' folios (AJK)
result = {"pass": [], "fail": {}}
for pf in sorted(patch_dir.glob(f"patch-*{suffix}.json")):
    doc = int(re.search(rf"patch-(\d+){suffix}", pf.name).group(1))
    head_words = set()
    for r in json.loads(pf.read_text(encoding="utf-8")):
        m = re.search(r"running head '(.*)' at its head", r["observed"], re.S)
        if m:
            head_words.update(w for w in re.split(r"\s+|/", m.group(1)) if w)
        m = re.search(r"prints its folio '(\d+)'", r["observed"])
        if m:
            head_words.add(m.group(1))
    dumps = sorted(dump_dir.glob(f"{doc}_*.json"))
    if not dumps:
        result["fail"][doc] = "no tree dump (the dry run failed or the rebuild was identical)"
        continue
    reason = None
    for dp in dumps:
        d = json.loads(dp.read_text(encoding="utf-8"))
        f = d["fields"]
        stored = {row[0]: dict(zip(f, row)) for row in d["stored"]}
        built = {row[0]: dict(zip(f, row)) for row in d["built"]}
        if set(stored) != set(built):
            reason = f"paths removed {sorted(set(stored) - set(built))[:3]} added {sorted(set(built) - set(stored))[:3]}"
            break
        for path, a in stored.items():
            b = built[path]
            for k in ("kind", "label", "parent", "heading"):
                if (a.get(k) or "") != (b.get(k) or ""):
                    reason = f"{k} changed at {path}"
                    break
            if reason:
                break
            if (a.get("text") or "") != (b.get("text") or ""):
                x, y = (a.get("text") or "").split(), (b.get("text") or "").split()
                for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
                    if tag == "equal":
                        continue
                    if tag != "delete":
                        reason = f"text {tag} at {path}: -{x[i1:i2][:6]} +{y[j1:j2][:6]}"
                        break
                    stray = [w for w in x[i1:i2] if w not in head_words]
                    if stray:
                        reason = f"deleted words not in the head at {path}: {stray[:6]}"
                        break
            if reason:
                break
        if reason:
            break
    if reason:
        result["fail"][doc] = reason
    else:
        result["pass"].append(doc)
out.write_text(json.dumps(result, indent=1), encoding="utf-8")
print(f"{len(result['pass'])} pass, {len(result['fail'])} fail")
for doc, why in list(result["fail"].items())[:25]:
    print(f"  FAIL {doc}: {why[:200]}")
