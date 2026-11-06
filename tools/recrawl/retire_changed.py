"""retire_changed.py SPEC.json [--apply] : before re-recording a spec, retire the document's active whole-block records
(before_text = the block's stored text) whose replacement differs from the spec's new text for that block -- a block
re-transcribed a second time would otherwise carry two records, the older one leaving the newer matching nothing (or
two blocks). Also retires records on blocks the spec now sets aside. Nothing is deleted: retired_at and the reason."""
import json, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
spec = json.load(open(sys.argv[1], encoding="utf-8"))
apply = "--apply" in sys.argv
doc = spec["document_id"]
rep = {int(i): t for pg in spec["pages"].values() for i, t in (pg.get("replace") or {}).items()}
aside = {int(i) for pg in spec["pages"].values() for i in (pg.get("set_aside") or [])}
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT p.id, b.id, p.after_text FROM segmentation_curation_patch p
                     JOIN text_block b ON b.document_id=%s AND b.page_no=p.page_no AND p.before_text=b.text
                    WHERE p.retired_at IS NULL AND p.after_text <> p.before_text AND p.source_observation_id IN
                          (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (doc, doc))
    gone = []
    for pid, bid, after in cur.fetchall():
        if bid in rep and after not in rep[bid] and rep[bid] != after:
            gone.append((pid, bid, "re-transcribed"))
        elif bid in aside:
            gone.append((pid, bid, "now set aside"))
    for g in gone:
        print("  retire", g)
    if apply and gone:
        cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                         evidence = evidence || jsonb_build_object('retired_reason', 'superseded: the block was transcribed again from the page (retire_changed.py)'::text, 'retired_by', 'claude.recrawl-queue/1'::text)
                        WHERE id = ANY(%s::uuid[])""", ([g[0] for g in gone],))
        conn.commit()
    print(len(gone), "record(s)", "retired" if apply else "(dry run)")
