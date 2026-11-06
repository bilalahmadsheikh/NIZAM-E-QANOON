"""lead_transcribe.py DOC PAGE LINES.txt REASON [--apply] : record the lead's transcription of a page the engine could not
read (owner chat delegation 25 Oct 2026) as an accepted OCR candidate of the ACTIVE document DOC, for
tools/promote_ocr_adjudicated.py --allow-partial. One block per line, spaced evenly over the page's text area (geometry
approximate, flagged). Refuses a page that already has an accepted candidate on DOC. Dry run by default.

Written for doc 9682 (West Pakistan Entertainments Duty Act 1958): Surya returned nothing for pp2-3 (p3 is printed
upside down) and that empty reading had been accepted with the rest under q5."""
import json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE

doc, page, src, reason = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
apply = "--apply" in sys.argv
lines = [l.strip() for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT height, width FROM page WHERE document_id=%s AND page_no=%s", (doc, page))
    h, w = (float(x or 0) for x in cur.fetchone())
    h, w = h or 792.0, w or 612.0
    cur.execute("""SELECT count(*) FROM page_ocr_candidate c JOIN LATERAL (SELECT decision FROM page_ocr_adjudication a
                    WHERE a.candidate_id=c.id ORDER BY a.decided_at DESC, a.id DESC LIMIT 1) l ON true
                    WHERE c.document_id=%s AND c.page_no=%s AND l.decision='accepted'""", (doc, page))
    if cur.fetchone()[0]:
        sys.exit(f"doc {doc} p{page} already has an accepted reading")
    top, bottom, x0, x1 = 0.06 * h, 0.94 * h, 0.10 * w, 0.90 * w
    step = (bottom - top) / len(lines)
    blocks = [{"bbox": [x0, top + i * step, x1, top + (i + 1) * step], "html": "", "text": t, "error": False,
               "label": "Text", "script": "latin", "skipped": False, "raw_label": "LeadTranscription",
               "confidence": 1.0, "lead_supplied": True, "block_no": i, "reading_order": i,
               "geometry": "approximate: the engine read nothing; lines spaced evenly over the page"}
              for i, t in enumerate(lines)]
    text = "\n\n".join(lines)
    print(f"doc {doc} p{page}: {len(lines)} lines, {len(text.split())} words")
    if not apply:
        print("dry run -- pass --apply"); sys.exit(0)
    cur.execute("""INSERT INTO page_ocr_candidate (document_id, page_no, engine, languages, dpi, text, mean_confidence,
                                                     word_count, blocks)
                   VALUES (%s,%s,%s,'en',0,%s,1.0,%s,%s) RETURNING id""",
                (doc, page, ENGINE + "+lead-transcription/1", text, len(text.split()), json.dumps(blocks)))
    cid = cur.fetchone()[0]
    cur.execute("""INSERT INTO page_ocr_adjudication (candidate_id, decision, reason, evidence, decided_by)
                   VALUES (%s,'accepted',%s,%s,'claude.lead-under-owner-delegation/1')""",
                (cid, "The lead transcribed the printed page from its image under the owner's chat delegation of "
                      "25 Oct 2026: " + reason,
                 json.dumps({"transcription_file": str(src), "owner_delegation_export":
                             ".artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json"})))
    conn.commit()
    print(f"candidate {cid} recorded and accepted")
