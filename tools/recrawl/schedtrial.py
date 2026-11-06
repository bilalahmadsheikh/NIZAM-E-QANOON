"""schedtrial.py DOC [DOC ...] : schedule-opener trial per document (writes; reversible by retirement).

For each doc: the uppercase headings proposed in .artifacts/recrawl-queue/schedfind-up.json become one
source_division_unit_openers patch (patch-DOCsch.json); the doc is pinned to unreleased-v4, the patch recorded and the
doc replayed. KEPT only if every top-level section/rule label that the tree held before on pages before the first
heading is still a top-level unit after; otherwise the patch is retired and the doc replayed back."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = Path("/mnt/e/Nizam_e_Qanoon"); Q = ROOT / ".artifacts/recrawl-queue"
props = json.load(open(Q / "schedfind-up.json", encoding="utf-8"))
sh = lambda *a: subprocess.run(["bash", *a], cwd=ROOT, capture_output=True, text=True).stdout

def top(doc, before_page):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT pr.label FROM provision pr JOIN instrument i ON i.id=pr.instrument_id
                        LEFT JOIN text_block t ON t.id=pr.first_block
                        WHERE i.document_id=%s AND i.is_active AND pr.is_active AND pr.parent_id IS NULL
                          AND pr.kind::text IN ('section','rule','regulation','article') AND coalesce(t.page_no, pr.first_page) < %s""",
                    (doc, before_page))
        return {r[0] for r in cur.fetchall()}

for doc in map(int, sys.argv[1:]):
    ps = [p for p in props if p["doc"] == doc]
    if not ps:
        print(doc, "no proposal"); continue
    first = min(p["page"] for p in ps)
    before = top(doc, first)
    L = [{"document_id": doc, "page_no": p["page"],
          "source_division_unit_openers": [{"source_block_id": p["block"], "source_prefix": p["prefix"], "kind": "schedule", "label": p["label"]}],
          "defect": f"the schedule heading '{p['prefix']}' printed on page {p['page']} opens nothing, so the schedule's numbered rows/paragraphs were read as sections and collided with the enactment's sections",
          "fixes": "rule reviewed_division_unit_opener: the schedule opens at its printed heading; its numbered rows are the schedule's items",
          "observed": f"Page {p['page']} prints the heading '{p['prefix']}' on its own line, after the enactment's last section and before the schedule's numbered entries."}
         for p in ps]
    f = Q / f"patches/patch-{doc}sch.json"
    f.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")
    sh("tools/recrawl/render_list.sh", "/dev/stdin") if False else None
    for p in ps:
        sh("tools/recrawl/render.sh", str(doc), str(p["page"]), "70")
    pin = sh("tools/recrawl/pinv4.sh", str(doc))
    rec = sh("tools/recrawl/recfile.sh", str(f.relative_to(ROOT)))
    rep = sh("tools/recrawl/replay.sh", str(doc))
    after = top(doc, first)
    lost = sorted(before - after)
    state = [l for l in rep.splitlines() if l.startswith(f"{doc}|")]
    err = [l for l in rep.splitlines() if "ERROR" in l]
    if lost or err:
        sh("tools/recrawl/retire_file.sh", str(f.relative_to(ROOT)), f"schedule-opener trial reverted: {'error' if err else 'top-level units lost ' + ','.join(lost)[:120]}")
        rep2 = sh("tools/recrawl/replay.sh", str(doc))
        print(doc, "REVERTED", "lost", lost[:8], err[:1], [l for l in rep2.splitlines() if l.startswith(f"{doc}|")])
    else:
        print(doc, "KEPT", rec.strip()[:60], state)
