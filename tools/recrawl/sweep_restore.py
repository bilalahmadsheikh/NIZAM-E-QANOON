"""sweep_restore.py MAP.json : undo a sweep set-aside that took law text with a running head (sweep.py's head rule
before the 29 Oct fix took any short block holding 'GAZETTE', law words and all -- doc 9749 p3 lost section 7).
MAP: {"block_id": "the law text the block prints after the head"}. For each document: the active patches carrying
those blocks in their set-asides are retired (reason recorded), and a blockfix spec is written re-setting-aside the
page's other blocks and replacing each named block's text with its law words. Prints the spec paths; recording and
the replay are left to sweep_restore.sh. Writes to the DB only the retirements."""
import json, sys
from collections import defaultdict
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
fix = {int(k): v for k, v in json.load(open(sys.argv[1], encoding="utf-8")).items()}
R = "/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/specs/"
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, document_id, page_no FROM text_block WHERE id = ANY(%s)", (list(fix),))
    where = {i: (d, p) for i, d, p in cur.fetchall()}
    specs = defaultdict(lambda: {"pages": {}})
    for b, (d, p) in where.items():
        cur.execute("""SELECT id, evidence->'structural_overrides'->'source_apparatus_blocks' FROM segmentation_curation_patch
                        WHERE retired_at IS NULL AND evidence->'structural_overrides'->'source_apparatus_blocks' @> %s::jsonb
                          AND source_observation_id IN (SELECT source_observation_id FROM instrument
                                                         WHERE document_id=%s AND is_active AND duplicate_of IS NULL)""",
                    (json.dumps([b]), d))
        rows = cur.fetchall()
        pg = specs[d]["pages"].setdefault(str(p), {"set_aside": [], "replace": {},
            "observed": "the running head at the top of the page and, in the same block, the law text that follows it"})
        for pid, aside in rows:
            pg["set_aside"] += [x for x in aside if x not in fix and x not in pg["set_aside"]]
            cur.execute("""UPDATE segmentation_curation_patch SET retired_at=now(),
                             evidence = evidence || jsonb_build_object('retired_reason', %s::text, 'retired_by', 'claude.recrawl-queue/1')
                            WHERE id=%s""", (f"the set-aside took block {b}, which holds law text after the running head "
                                             "(sweep.py head rule before the 29 Oct fix); re-recorded without it", pid))
        pg["replace"][str(b)] = fix[b]
    conn.commit()
for d, s in specs.items():
    s["document_id"] = d
    json.dump(s, open(f"{R}restore-{d}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(d, " ".join(s["pages"]))
