"""Build S7 source readings from short lines (no DB writes).

    python tools/recrawl/mkread.py MANIFEST LINES OUT.json
LINES, one per unit, '|'-separated:
    U<n>|<observed>                     unit n of the sheet manifest; accept_non_citable; render = demoted page
    D<doc>|<label>|<page>|<observed>    a unit by document and label (the label must be unique among its open units)
A line may start 'R:' for restore_citable instead of accept_non_citable."""
import hashlib, json, sys
from pathlib import Path
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
REL = ".artifacts/release-work-2026-09-24/claude/renders"
man = {str(x["u"]): x for x in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))} if sys.argv[1] != "-" else {}
out = []
for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    res = "accept_non_citable"
    if line.startswith("R:"):
        res, line = "restore_citable", line[2:]
    if line.startswith("U"):
        u, obs = line[1:].split("|", 1)
        x = man[u]
        render = x["demoted_render"]
        r = {"document_id": x["document_id"], "printed_label": x["printed_label"], "candidate_id": x["candidate_id"]}
    elif line.startswith("C"):
        cid, doc, label, page, obs = line[1:].split("|", 4)
        render = f"{REL}/doc{doc}-p{page}.png"
        r = {"document_id": int(doc), "printed_label": label, "candidate_id": cid}
    else:
        doc, label, page, obs = line[1:].split("|", 3)
        render = f"{REL}/doc{doc}-p{page}.png"
        r = {"document_id": int(doc), "printed_label": label}
    sha = hashlib.sha256((ROOT / render).read_bytes()).hexdigest()
    r.update({"resolution": res, "observed": obs.strip(), "render": render, "render_sha256": sha})
    out.append(r)
Path(sys.argv[3]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(out)} readings -> {sys.argv[3]}")
