"""txedit.py DOC EDITS.json : apply a page reader's corrections to the draft transcription specs/transcribe-DOC.txt
(written by draft.py), in place. EDITS = {"drop": [block ids -- apparatus, set aside],
"sub": [[old, new], ...] -- each old must occur exactly once, "notes": {"<page>": "what else the page prints"}}.
Refuses an old string that is absent or repeated, so a correction never lands somewhere unread."""
import json, re, sys
from pathlib import Path
doc = int(sys.argv[1])
path = Path(f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/specs/transcribe-{doc}.txt")
ed = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
src = path.read_text(encoding="utf-8")
drop = {int(i) for i in ed.get("drop", [])}
out = []
for para in re.split(r"\n\n+", src):
    m = re.match(r"(?s)(.*?\n)?@(\d+) ", para)
    if m and m.group(2) in (ed.get("para") or {}):
        # "para": {"<block id>": "the paragraph as printed"} -- the block's whole paragraph, read anew
        out.append((m.group(1) or "") + f"@{m.group(2)} " + ed["para"][m.group(2)])
        continue
    if m and int(m.group(2)) in drop:
        if m.group(1):              # the '=== pN\n| note' lines before the page's first block stay
            out.append(m.group(1).rstrip("\n"))
        drop.discard(int(m.group(2)))
        continue
    out.append(para)
assert not drop, ("blocks not in the draft", sorted(drop))
txt = "\n\n".join(out)
for old, new in ed.get("sub", []):
    n = txt.count(old)
    assert n == 1, (n, old)
    txt = txt.replace(old, new)
for p, note in ed.get("notes", {}).items():
    txt, n = re.subn(rf"(?m)^(=== p{p}\n)\|[^\n]*", lambda mm: mm.group(1) + "| " + note, txt)
    assert n == 1, ("page", p)
# a page heading line followed by a blank line would end the note: keep '=== pN\n| note\n@...' together -- the note
# line only: a schedule row '| | ...' before a pin lost its blank line too, and the pin was recorded as text (docs
# 9212, 9856, 9858, 9859, 5 Nov 2026)
txt = re.sub(r"(?m)^(=== p\d+[ \t]*\n\| [^\n]*)\n\n(@)", r"\1\n\2", txt)
path.write_text(txt.rstrip("\n") + "\n", encoding="utf-8")
print("ok", path.name)
