"""carry_s7.py OLD NEW [--apply] : carry the page-read S7 decisions of a superseded revision onto its OCR re-read.

A promotion creates a new document whose structural candidates are fresh; the earlier decisions -- readings of the
PRINTED page -- no longer point at them (tools/reattach_orphaned_adjudications.py keys on document and block, both
new). For every pending candidate of NEW, the source-verified decision of OLD on the same printed label and source
page (exactly one distinct resolution) is re-recorded through tools/adjudicate_s7_from_source.py with the reader's
own observation and a fresh render of NEW's page. Machine decisions are not carried: re-run the machine adjudicators
instead. Writes a readings file and records with --apply."""
import hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = pathlib.Path("/mnt/e/Nizam_e_Qanoon")
old, new, apply = int(sys.argv[1]), int(sys.argv[2]), "--apply" in sys.argv
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT c.printed_label, c.source_page FROM v_structural_adjudication_pending p
                    JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=%s""", (new,))
    pending = cur.fetchall()
    readings = []
    for label, page in pending:
        cur.execute("""SELECT DISTINCT a.resolution, a.rationale FROM segmentation_structural_candidate c
                         JOIN segmentation_structural_adjudication a ON a.candidate_id=c.id
                        WHERE c.document_id=%s AND c.printed_label=%s AND c.source_page=%s
                          AND a.review_basis='source_verified' AND a.decided_by='claude.s7-source-review/1'""",
                    (old, label, page))
        rows = cur.fetchall()
        if len({r[0] for r in rows}) != 1:
            print(f"  label {label} p{page}: {len(rows)} page-read decision(s) on {old} -- left for a reader"); continue
        res, observed = rows[0]
        subprocess.run(["bash", str(ROOT / ".artifacts/recrawl-queue/render_pages.sh"), str(new), "90", str(page)],
                       check=True, capture_output=True)
        render = f".artifacts/release-work-2026-09-24/claude/renders/doc{new}-p{page}.png"
        readings.append({"document_id": new, "printed_label": label, "resolution": res, "observed": observed,
                         "render": render, "render_sha256": hashlib.sha256((ROOT / render).read_bytes()).hexdigest()})
        print(f"  label {label} p{page}: {res} (carried from {old})")
out = ROOT / f".artifacts/recrawl-queue/s7carry-{new}.json"
out.write_text(json.dumps(readings, ensure_ascii=False, indent=1), encoding="utf-8")
if readings:
    r = subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "tools/adjudicate_s7_from_source.py"), "--readings", str(out)]
                       + (["--apply"] if apply else []), capture_output=True, text=True, cwd=ROOT,
                       env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    print((r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "")
