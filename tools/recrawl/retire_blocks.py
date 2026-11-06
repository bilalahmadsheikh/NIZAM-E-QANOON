"""retire_blocks.py DOC REASON BLOCK_ID... [--apply] : retire the active curation patches of DOC's observation whose
match_text is the whole current text of one of the blocks named -- the whole-block records blockfix.py wrote -- so a
corrected transcription of those blocks can be recorded (dry run without --apply). Nothing is deleted: retired_at
and the reason go on the row, as retire_match.py does."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
args = [a for a in sys.argv[1:] if a != "--apply"]
doc, reason, ids, apply = int(args[0]), args[1], [int(a) for a in args[2:]], "--apply" in sys.argv
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT text FROM text_block WHERE document_id=%s AND id = ANY(%s)", (doc, ids))
    texts = [r[0] for r in cur.fetchall()]
    assert len(texts) == len(ids), "a block is not on the document"
    cur.execute("""SELECT p.id, p.page_no, left(p.match_text, 50),
                          p.evidence->'structural_overrides' ? 'source_apparatus_blocks'
                     FROM segmentation_curation_patch p
                    WHERE p.retired_at IS NULL AND p.match_text = ANY(%s) AND p.source_observation_id IN
                          (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (texts, doc))
    rows = cur.fetchall()
    for r in rows:
        print(r[:3])
        if r[3]:
            # blockfix.py hangs a page's set-asides on its first record: retiring it brings them back (doc 9662 p9)
            print(f"   WARNING: patch {r[0]} also carries page {r[1]}'s set-aside blocks -- re-record them "
                  "(a blockfix spec of that page's set_aside only)")
    if apply and rows:
        cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                         evidence = evidence || jsonb_build_object('retired_reason', %s::text, 'retired_by', 'claude.recrawl-queue/1')
                        WHERE id = ANY(%s::uuid[])""", (reason, [r[0] for r in rows]))
        conn.commit()
    print(len(rows), "patch(es)", "retired" if apply else "(dry run)")
