"""Record the boundary anchors a reviewed split plan needs (owner policy q1 'split', 22 Oct; agent G, lead-approved).

    python tools/recrawl/anchor.py DOC            dry run: prints what it would insert, then rolls back
    python tools/recrawl/anchor.py DOC --apply    commits

Does exactly what tools/evidence/split-doc-1822-boundaries.sql does, append-only (INSERT only, never UPDATE/DELETE):
for every span start of tools/evidence/multi-instrument-plans/doc-DOC.json that is NOT the document's first block,
one segmentation_boundary_candidate keyed to the document's ACTIVE single-tree instrument and observation
(confidence 1.0, method 'claude.multi-expression-plan/1', title/kind/year/number as printed = the plan expression),
then its 'confirmed_split' adjudication (review basis source_verified).  Run it BEFORE materializing.

Refuses unless: DOC is in .artifacts/recrawl-queue/list-split.txt; no expression of DOC is released; the spec
.artifacts/recrawl-queue/splits/spec-DOC.json carries "agent": "G" and its starts equal the plan's; the active
instrument is exactly one, a single tree on the plan's observation; every anchored expression in the spec carries
"source_facts" (what the page image prints at that block) and its start page has a render under
.artifacts/release-work-2026-09-24/claude/renders/."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
REL = ".artifacts/release-work-2026-09-24/claude/renders"
METHOD = "claude.multi-expression-plan/1"
EXPORT = ".artifacts/decision-review/exports/policy-application-2026-10-22.json"

doc = int(sys.argv[1])
apply = "--apply" in sys.argv[2:]
listed = {int(x) for x in (ROOT / ".artifacts/recrawl-queue/list-split.txt").read_text().split()}
if doc not in listed:
    sys.exit(f"{doc} is not in list-split.txt")
plan_path = f"tools/evidence/multi-instrument-plans/doc-{doc}.json"
plan = json.loads((ROOT / plan_path).read_text(encoding="utf-8-sig"))
spec = json.loads((ROOT / f".artifacts/recrawl-queue/splits/spec-{doc}.json").read_text(encoding="utf-8-sig"))
if spec.get("agent") not in ("G", "lead"):
    sys.exit("spec is not agent G's or the lead's")
pstarts = [x["spans"][0]["start_block_id"] for x in plan["expressions"]]
sstarts = [e["spans"][0][0] if e.get("spans") else e["start_block_id"] for e in spec["expressions"]]
if pstarts != sstarts:
    sys.exit(f"plan starts {pstarts} differ from spec starts {sstarts}")
blocks = legal_write.blocks_for(doc)
first, page_of = blocks[0]["id"], {b["id"]: b["page_no"] for b in blocks}
obs = plan["source_observation_id"]
owner = {"export": EXPORT, "document_id": doc, "question_id": "q1"}

with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT count(*) FROM instrument i JOIN v_release_instrument r ON r.id=i.id
                    WHERE i.document_id=%s""", (doc,))
    if cur.fetchone()[0]:
        sys.exit(f"{doc} has a released expression -- refusing")
    cur.execute("""SELECT id, source_observation_id, expression_ordinal FROM instrument
                    WHERE document_id=%s AND is_active AND duplicate_of IS NULL""", (doc,))
    rows = cur.fetchall()
    if not rows:
        # a promoted OCR revision of a split document (5017 -> 9773): the segmenter refuses an observation with
        # several active expressions, so the revision has no tree of its own; the anchors key to the primary
        # expression that stands on the superseded revision -- same file, same observation as the plan
        cur.execute("""SELECT i.id, i.source_observation_id, i.expression_ordinal FROM document n
                         JOIN instrument i ON i.document_id=n.supersedes_document_id AND i.is_active
                              AND i.duplicate_of IS NULL AND i.source_sha256=n.sha256
                        WHERE n.id=%s AND i.expression_role='primary'""", (doc,))
        rows = cur.fetchall()
    if len(rows) != 1 or rows[0][1] != obs:
        sys.exit(f"{doc}: active instruments {rows} are not one single tree on observation {obs}")
    inst = rows[0][0]
    todo = []
    for x, e in zip(plan["expressions"], spec["expressions"]):
        start = x["spans"][0]["start_block_id"]
        if start == first:
            continue
        facts = e.get("source_facts") or []
        if not facts:
            sys.exit(f"expression {x['ordinal']} (block {start}) has no source_facts in the spec")
        page = page_of[start]
        render = f"{REL}/doc{doc}-p{page}.png"
        if not (ROOT / render).is_file():
            sys.exit(f"no render {render}")
        sha = hashlib.sha256((ROOT / render).read_bytes()).hexdigest()
        todo.append((x, start, page, facts, render, sha))
    if not todo:
        sys.exit("nothing to anchor: every span starts at the first block")
    reviewed = [p["page"] for p in plan.get("reviewed_pages", [])]
    for x, start, page, facts, render, sha in todo:
        evidence = {"reviewer_type": "assistant", "plan": plan_path, "owner_decision": owner,
                    "source_facts": facts, "reviewed_pages": reviewed,
                    "render_artifact": render, "render_sha256": sha}
        cur.execute("""INSERT INTO segmentation_boundary_candidate (
                         instrument_id,source_observation_id,document_id,start_block_id,source_page,
                         detected_title,detected_kind,detected_year,detected_number,confidence,method,evidence)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1.0,%s,%s::jsonb)
                       ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING RETURNING id""",
                    (inst, obs, doc, start, page, x["title"], x["kind"], x["year"], x["number"], METHOD,
                     json.dumps(evidence, ensure_ascii=False)))
        got = cur.fetchone()
        if got is None:
            cur.execute("""SELECT id FROM segmentation_boundary_candidate
                            WHERE instrument_id=%s AND start_block_id=%s AND method=%s""", (inst, start, METHOD))
            got = cur.fetchone()
        cid = got[0]
        rationale = (f"Block {start} (p{page}) begins {x['title']} -- a separate law bound into the same PDF, "
                     f"an embedded expression of the reviewed plan {plan_path} (owner policy q1 'split', 22 Oct 2026).")
        cur.execute("""INSERT INTO segmentation_boundary_adjudication (
                         candidate_id,resolution,review_basis,method,rationale,evidence,decided_by)
                       SELECT %s,'confirmed_split','source_verified',%s,%s,%s::jsonb,%s
                        WHERE NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                                           WHERE a.candidate_id=%s AND a.resolution='confirmed_split')""",
                    (cid, METHOD, rationale,
                     json.dumps({"reviewer_type": "assistant", "source_start_block_id": start, "plan": plan_path,
                                 "owner_decision": owner}), METHOD, cid))
        print(f"  ordinal {x['ordinal']} block {start} p{page} candidate {cid} adjudicated={cur.rowcount} :: {x['title']}")
    if apply:
        print("applied")
    else:
        conn.rollback()
        print("dry run (rolled back); --apply to commit")
