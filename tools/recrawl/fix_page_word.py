"""fix_page_word.py DOC PAGE OLD NEW REASON [--apply] : correct one misread string on a page of an active E4 document.

Builds a corrected page candidate (engine '<surya engine>+owner-correction/1', as
tools/evidence/adjudicate_ocr_review_export.py does) from the page's CURRENT text blocks with OLD replaced by NEW in
exactly one block, and records its acceptance (decided by the lead under the owner's chat delegation, 25 Oct 2026),
so tools/promote_ocr_adjudicated.py --allow-partial can promote it. Refuses unless OLD occurs exactly once on the page.
Dry run by default."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE

doc, page, old, new, reason = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
apply = "--apply" in sys.argv
ENG = ENGINE + "+owner-correction/1"
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT is_active, lane FROM document WHERE id=%s", (doc,))
    active, lane = cur.fetchone()
    assert active and lane == "E4", (active, lane)
    cur.execute("""SELECT block_no, x0, y0, x1, y1, text, script, confidence FROM text_block
                    WHERE document_id=%s AND page_no=%s ORDER BY reading_order""", (doc, page))
    rows = cur.fetchall()
    hits = [i for i, r in enumerate(rows) if old in r[5]]
    assert len(hits) == 1 and rows[hits[0]][5].count(old) == 1, f"{old!r} occurs {len(hits)} block(s)"
    blocks = []
    for n, (bno, x0, y0, x1, y1, text, script, conf) in enumerate(rows):
        blocks.append({"bbox": [float(x0), float(y0), float(x1), float(y1)], "block_no": n, "reading_order": n,
                       "text": text.replace(old, new, 1) if n == hits[0] else text, "html": "", "error": False,
                       "label": "Text", "script": script or "latin", "skipped": False, "raw_label": "OwnerCorrection",
                       "confidence": float(conf) if conf is not None else 1.0})
    text = "\n\n".join(b["text"] for b in blocks)
    words = len(re.findall(r"\w+", text))
    print(f"doc {doc} p{page}: block {hits[0]} {old!r} -> {new!r}; {len(blocks)} blocks, {words} words")
    if not apply:
        print("dry run -- pass --apply"); sys.exit(0)
    cur.execute("""INSERT INTO page_ocr_candidate (document_id, page_no, engine, languages, dpi, text, mean_confidence,
                   word_count, blocks) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (doc, page, ENG, ["en"], 200, text, 1.0, words, json.dumps(blocks, ensure_ascii=False)))
    cid = cur.fetchone()[0]
    cur.execute("""INSERT INTO page_ocr_adjudication (candidate_id, decision, reason, evidence, decided_by)
                   VALUES (%s,'accepted',%s,%s,%s)""",
                (cid, reason, json.dumps({"review": "lead page-image read under owner chat delegation 25 Oct 2026",
                                          "document_id": doc, "page_no": page, "old": old, "new": new}),
                 "claude.lead-under-owner-delegation/1"))
    conn.commit()
    print("candidate", cid, "accepted")
