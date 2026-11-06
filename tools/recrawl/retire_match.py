"""retire_match.py DOC REASON MATCH_TEXT... [--apply] : retire the active curation patches of DOC's observation whose
match_text is one of MATCH_TEXT (dry run without --apply) -- for a reading being re-recorded merged into another
record. Nothing is deleted: retired_at and the reason go on the row (append-only evidence), as retire_ids.py does."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
args = [a for a in sys.argv[1:] if a != "--apply"]
doc, reason, matches, apply = int(args[0]), args[1], args[2:], "--apply" in sys.argv
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT p.id, p.page_no, p.match_text FROM segmentation_curation_patch p
                    WHERE p.retired_at IS NULL AND p.match_text = ANY(%s) AND p.source_observation_id IN
                          (SELECT o.id FROM source_observation o JOIN document d ON d.sha256=o.sha256 WHERE d.id=%s)
                    ORDER BY p.page_no""", (matches, doc))
    rows = cur.fetchall()
    assert len(rows) == len(set(matches)), f"expected {len(set(matches))} active patches, found {len(rows)}"
    for r in rows:
        print("patch", r[0], f"p{r[1]}", repr(r[2]))
        if apply:
            cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                             evidence = evidence || jsonb_build_object('retired_reason', %s::text, 'retired_by', 'claude.recrawl-queue/1')
                           WHERE id=%s""", (reason, r[0]))
    if apply:
        conn.commit()
    print(len(rows), "patch(es)", "retired" if apply else "(dry run)")
