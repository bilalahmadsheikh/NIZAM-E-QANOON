"""retire_stale.py NEWDOC [--apply] : retire active curation patches of NEWDOC's observation whose match text no longer
occurs in exactly one block of its page in NEWDOC's (re-read) text -- they were written for the replaced text layer (writes with --apply)."""
import json, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc = int(sys.argv[1]); apply = "--apply" in sys.argv
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT page_no, text FROM text_block WHERE document_id=%s", (doc,))
    bypage = {}
    for pg, t in cur.fetchall():
        bypage.setdefault(pg, []).append(t or "")
    cur.execute("""SELECT p.id, p.page_no, p.match_text FROM segmentation_curation_patch p
                    WHERE p.retired_at IS NULL AND p.source_observation_id IN
                          (SELECT o.id FROM source_observation o JOIN document d ON d.sha256=o.sha256 WHERE d.id=%s)""", (doc,))
    stale = [(i, pg, m) for i, pg, m in cur.fetchall()
             if sum((m or "") in t for t in bypage.get(pg, [])) != 1]
    for i, pg, m in stale:
        print("stale", i, f"p{pg}", repr((m or "")[:60]))
        if apply:
            cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                             evidence = evidence || jsonb_build_object('retired_reason', %s::text, 'retired_by', 'claude.recrawl-queue/1')
                           WHERE id=%s""", (f"written for the replaced text layer; document {doc} now carries the owner-accepted OCR reading", i))
    if apply:
        conn.commit()
    print(len(stale), "stale", "retired" if apply else "(dry run)")
