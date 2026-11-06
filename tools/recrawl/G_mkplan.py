"""[agent G variant of mkplan.py: an expression may give "spans": [[start_block_id, end_block_id], ...] (reading order)
instead of start/end, for a law whose margin notes or slivers the extractor read inside a neighbour's blocks.]
Build a reviewed multi-expression split plan (owner policy q1 'split', 22 Oct) from a short spec.

    python tools/recrawl/mkplan.py SPEC.json        writes tools/evidence/multi-instrument-plans/doc-N.json

SPEC: {"document_id": N, "pages": [p, ...] (pages read, rendered by render.sh),
       "expressions": [{"start_block_id": B, "end_block_id": E (optional), "role": "primary"|"embedded",
                        "title": "...", "kind": "act|ordinance|order|rules|regulation|notification", "year": 1972,
                        "number": "15" | null, "title_basis": "p3 block B prints '...'",
                        "title_correction": {...} (optional, primary only)}],
       "skip_before": true (optional: blocks before the first start are apparatus, e.g. a tail of an earlier law)}
The primary (the catalogued law) must be first in the list (ordinal 0). Each expression runs from its start block to
the block before the next expression's start in reading order (or to end_block_id); blocks outside every span are
apparatus. Read-only on the database."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
REL = ".artifacts/release-work-2026-09-24/claude/renders"
POLICY = ".artifacts/decision-review/exports/policy-application-2026-10-22.json"
spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
doc = spec["document_id"]
blocks = legal_write.blocks_for(doc)
pos = {b["id"]: i for i, b in enumerate(blocks)}
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active
                    AND duplicate_of IS NULL AND expression_role='primary' ORDER BY expression_ordinal LIMIT 1""", (doc,))
    obs = cur.fetchone()[0]
exprs = spec["expressions"]
starts = sorted(pos[e["spans"][0][0] if e.get("spans") else e["start_block_id"]] for e in exprs)
out = []
for ordinal, e in enumerate(exprs):
    if e.get("spans"):
        sp = [{"start_block_id": a, "end_block_id": b,
               "pages": f"{blocks[pos[a]]['page_no']}-{blocks[pos[b]]['page_no']}"} for a, b in e["spans"]]
        x = {"ordinal": ordinal, "role": e["role"], "title": e["title"], "kind": e["kind"], "year": e["year"],
             "number": e.get("number"), "spans": sp, "title_basis": e["title_basis"]}
        if e.get("title_correction"):
            x["title_correction"] = e["title_correction"]
        out.append(x)
        continue
    first = pos[e["start_block_id"]]
    if "end_block_id" in e:
        last = pos[e["end_block_id"]]
    else:
        later = [s for s in starts if s > first]
        last = (later[0] - 1) if later else len(blocks) - 1
    x = {"ordinal": ordinal, "role": e["role"], "title": e["title"], "kind": e["kind"], "year": e["year"],
         "number": e.get("number"),
         "spans": [{"start_block_id": blocks[first]["id"], "end_block_id": blocks[last]["id"],
                    "pages": f"{blocks[first]['page_no']}-{blocks[last]['page_no']}"}],
         "title_basis": e["title_basis"]}
    if e.get("title_correction"):
        x["title_correction"] = e["title_correction"]
    out.append(x)
pages = []
for p in spec["pages"]:
    r = f"{REL}/doc{doc}-p{p}.png"
    pages.append({"page": p, "render": "." + "/" + r if not r.startswith(".") else r,
                  "render_sha256": hashlib.sha256((ROOT / r).read_bytes()).hexdigest()})
plan = {"schema": "nizam.multi_expression_plan/1", "document_id": doc, "source_observation_id": obs,
        "review_basis": "source_verified", "reviewed_on": "2026-10-22",
        "reviewed_by": "lead page review (22 Oct 2026) on the owner's corpus policy q1 'split'",
        "owner_decision": {"export": POLICY, "document_id": doc, "question_id": "q1",
                           "policy": ".artifacts/decision-review/exports/decision-review-2026-10-22-q22.json q1 split"},
        "reviewed_pages": pages, "expressions": out}
dest = ROOT / f"tools/evidence/multi-instrument-plans/doc-{doc}.json"
if dest.exists():
    sys.exit(f"{dest} exists -- refusing to overwrite a plan")
dest.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
for x in out:
    print(f"  ordinal {x['ordinal']} {x['role']:8} pages {x['spans'][0]['pages']:6} {x['title'][:70]}")
print("->", dest.relative_to(ROOT))
