"""retire_uuid.py REASON ID... [--apply] : retire the named curation patches (dry run lists them). For an older record
whose structural override a new page read supersedes. Nothing is deleted: retired_at and the reason go on the row."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
apply = "--apply" in sys.argv
args = [a for a in sys.argv[1:] if a != "--apply"]
reason, ids = args[0], args[1:]
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT id, page_no, left(match_text, 50), evidence->'structural_overrides' FROM segmentation_curation_patch
                    WHERE id = ANY(%s::uuid[]) AND retired_at IS NULL""", (ids,))
    rows = cur.fetchall()
    for r in rows:
        print("  retire", r)
    if apply and rows:
        cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                         evidence = evidence || jsonb_build_object('retired_reason', %s::text, 'retired_by', 'claude.recrawl-queue/1')
                        WHERE id = ANY(%s::uuid[]) AND retired_at IS NULL""", (reason, ids))
        conn.commit()
    print(len(rows), "patch(es)", "retired" if apply else "(dry run)")
