"""retire_ids.py DOC REASON [--apply] : list (dry run) or retire every active curation patch of DOC's observation recorded
today -- for a patch set whose replay failed (the tree is unchanged) and is being re-recorded corrected (writes with
--apply). Nothing is deleted: retired_at and the reason go on the row (append-only evidence)."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, reason, apply = int(sys.argv[1]), sys.argv[2], "--apply" in sys.argv
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT p.id, p.page_no, left(p.match_text, 60), p.created_at FROM segmentation_curation_patch p
                    WHERE p.retired_at IS NULL AND p.created_at::date = current_date AND p.source_observation_id IN
                          (SELECT o.id FROM source_observation o JOIN document d ON d.sha256=o.sha256 WHERE d.id=%s)
                    ORDER BY p.page_no""", (doc,))
    rows = cur.fetchall()
    for r in rows:
        print("patch", r[0], f"p{r[1]}", repr(r[2]), r[3])
        if apply:
            cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                             evidence = evidence || jsonb_build_object('retired_reason', %s::text, 'retired_by', 'claude.recrawl-queue/1')
                           WHERE id=%s""", (reason, r[0]))
    if apply:
        conn.commit()
    print(len(rows), "patch(es)", "retired" if apply else "(dry run)")
