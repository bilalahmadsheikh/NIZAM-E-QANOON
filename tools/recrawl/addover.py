"""addover.py DOC SUFFIX PAGE BLOCK 'OVERRIDES_JSON' 'WHAT' [--apply] : add reviewed structural overrides to an already
recorded page, riding on a re-record of one block of that page (doc 9809, 30 Oct: a body start added after release).

The block's active whole-block records (before_text == its OCR text) are retired, the block's transcription from
specs/spec-DOC.json is re-recorded under a fresh locator with the overrides attached (blockfix --only), and the
patch file patches/patch-DOC{SUFFIX}.json is written for rec.sh. Dry run without --apply (prints what it retires)."""
import json, subprocess, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
args = [a for a in sys.argv[1:] if a != "--apply"]
doc, sfx, page, block, over, what = int(args[0]), args[1], args[2], int(args[3]), json.loads(args[4]), args[5]
apply = "--apply" in sys.argv
Q = "/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue"
spec = json.load(open(f"{Q}/specs/spec-{doc}.json", encoding="utf-8"))
assert str(block) in spec["pages"][page]["replace"], (block, "not a transcribed block of page", page)
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT text FROM text_block WHERE id=%s AND document_id=%s", (block, doc))
    text = cur.fetchone()[0]
    # the block's records: one whole-block record, or the pieces of a long block (before a piece of its OCR text,
    # after a piece of its transcription)
    new = spec["pages"][page]["replace"][str(block)]
    cur.execute("""SELECT id, left(match_text, 40), before_text, after_text FROM segmentation_curation_patch
                    WHERE retired_at IS NULL AND page_no=%s AND after_text <> before_text AND source_observation_id IN
                    (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (int(page), doc))
    rows = [(r[0], r[1]) for r in cur.fetchall() if r[2] in text and r[3] in new]
    print("retire", rows)
    if not apply:
        sys.exit(0)
    for rid, _m in rows:
        cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(), evidence = evidence ||
                        jsonb_build_object('retired_reason', %s::text, 'retired_by', 'claude.recrawl-queue/1'::text)
                        WHERE id=%s""", (f"re-recorded to carry reviewed structural overrides: {what}", rid))
    conn.commit()
spec["pages"][page].setdefault("overrides", {}).update(over)
spec["pages"][page]["overrides_fix"] = what
json.dump(spec, open(f"{Q}/specs/spec-{doc}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
subprocess.run([".venv/bin/python", "tools/recrawl/blockfix.py", f"{Q}/specs/spec-{doc}.json",
                f"{Q}/patches/patch-{doc}{sfx}.json", f"--only={block}", "--keep-aside"], check=True, cwd="/mnt/e/Nizam_e_Qanoon")
