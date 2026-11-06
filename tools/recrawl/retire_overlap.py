"""retire_overlap.py SPEC.json [--apply] : before a blockfix spec's whole-block transcriptions are recorded (or after,
when a replay fails 'matched 0 blocks'), retire the document's OLDER active text patches whose locator lies inside a
block the spec replaces -- an earlier side-note cut or OCR fix on a block now re-transcribed whole would find its
text gone. Patches recorded from this spec's own patch file (same match_text and after_text) are kept. Nothing is
deleted: retired_at and the reason go on the row."""
import json, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
spec = json.load(open(sys.argv[1], encoding="utf-8"))
apply = "--apply" in sys.argv
doc = spec["document_id"]
rep = {int(i): t for pg in spec["pages"].values() for i, t in (pg.get("replace") or {}).items()}
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE id = ANY(%s)", (list(rep),))
    blocks = cur.fetchall()
    cur.execute("""SELECT id, page_no, match_text, before_text, after_text FROM segmentation_curation_patch
                    WHERE retired_at IS NULL AND match_text <> after_text AND source_observation_id IN
                          (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active AND duplicate_of IS NULL)""",
                (doc,))
    pats = cur.fetchall()
    gone = []
    for pid, page, m, before, after in pats:
        for bid, bp, text in blocks:
            # a piece of this spec's own record of the block (before inside the block, after inside its transcription)
            # is kept: blockfix counts it as already recorded and will not record it again (doc 9198 p2, 3 Nov)
            if (bp == page and m.casefold() in (text or "").casefold() and not (before == text and after == rep[bid])
                    and not (before in (text or "") and after in rep[bid])):
                # a whole-block record of this spec has before == the block and after == its transcription
                if not (m == text or text.startswith(m)) or after != rep[bid]:
                    gone.append((pid, page, m[:60]))
                break
    # a text patch on a block the spec now sets aside (a page re-read with a different block layout, doc 9164 p3):
    # its replacement would sit in a set-aside block and its text would block the spec's locators -- retire it too
    aside = {int(i) for pg in spec["pages"].values() for i in (pg.get("set_aside") or [])}
    cur.execute("SELECT id, page_no, text FROM text_block WHERE id = ANY(%s)", (list(aside),))
    ablocks = cur.fetchall()
    have = {g[0] for g in gone}
    for pid, page, m, before, after in pats:
        if pid in have:
            continue
        if any(bp == page and m.casefold() in (text or "").casefold() for _b, bp, text in ablocks):
            gone.append((pid, page, m[:60])); have.add(pid)
    # a record whose page set-asides include a block the spec now transcribes (doc 9722 p6, 3 Nov): the united
    # set-asides would hide the new text -- retire it; blockfix records the page's set-asides afresh
    cur.execute("""SELECT id, page_no, match_text FROM segmentation_curation_patch
                    WHERE retired_at IS NULL AND source_observation_id IN
                          (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active AND duplicate_of IS NULL)
                      AND EXISTS (SELECT 1 FROM jsonb_array_elements_text(
                                    coalesce(evidence->'structural_overrides'->'source_apparatus_blocks', '[]'::jsonb)) x
                                  WHERE x::bigint = ANY(%s))""", (doc, list(rep)))
    for pid, page, m in cur.fetchall():
        if pid not in have:
            gone.append((pid, page, m[:60])); have.add(pid)
    for g in gone:
        print("  retire", g)
    if apply and gone:
        cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                         evidence = evidence || jsonb_build_object('retired_reason', 'superseded: the block was re-transcribed whole from the page (blockfix spec)', 'retired_by', 'claude.recrawl-queue/1')
                        WHERE id = ANY(%s::uuid[])""", ([g[0] for g in gone],))
        conn.commit()
    print(len(gone), "patch(es)", "retired" if apply else "(dry run)")
