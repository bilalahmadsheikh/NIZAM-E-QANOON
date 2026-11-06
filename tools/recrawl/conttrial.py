"""conttrial.py DOC [DOC ...] : record a reviewed contents region (rows 'none') from contfind.json and replay; keep only
if the document releases or its pending total falls, else retire the patch and replay (writes; guarded)."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = Path("/mnt/e/Nizam_e_Qanoon"); Q = ROOT / ".artifacts/recrawl-queue"
props = {x["doc"]: x for x in json.load(open(Q / "contfind.json", encoding="utf-8"))}
sh = lambda *a: subprocess.run(["bash", *a], cwd=ROOT, capture_output=True, text=True).stdout
def state(doc):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT bool_and(EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)),
                         (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=%s),
                         (SELECT count(*) FROM v_toc_gap_pending g WHERE g.document_id=%s)
                         FROM instrument i WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL""", (doc, doc, doc))
        return cur.fetchone()
def text(bid):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT left(regexp_replace(text, '\s+', ' ', 'g'), 90) FROM text_block WHERE id=%s", (bid,))
        return cur.fetchone()[0]
for doc in map(int, sys.argv[1:]):
    x = props[doc]; b = state(doc)
    obs = (f"Pages {x['pages'][0]}-{x['pages'][1]} print the contents list of sections from '{text(x['first'])}' (block {x['first']}) "
           f"to '{text(x['last'])}' (block {x['last']}); the enacted text begins at '{text(x['body'])}' (block {x['body']}). "
           "The contents rows are printed in two columns and the text layer garbles their numbers, so they are read as contents only.")
    L = [{"document_id": doc, "page_no": x["pages"][0],
          "source_contents_region": {"first_block_id": x["first"], "last_block_id": x["last"], "body_start_block_id": x["body"], "rows": __import__("os").environ.get("ROWS", "none")},
          "defect": "the printed contents list was read as the Act's sections (its rows became top-level units) and the real sections in the body were demoted against them",
          "fixes": "rule reviewed_contents_region (rows 'none'): the page-read contents region is contents; the body starts at its preamble/section 1",
          "observed": obs}]
    f = Q / f"patches/patch-{doc}cr{__import__("os").environ.get("ROWS", "")}.json"; f.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")
    sh("tools/recrawl/render.sh", str(doc), str(x["pages"][0]), "70")
    rec = sh("tools/recrawl/recfile.sh", str(f.relative_to(ROOT)))
    rep = sh("tools/recrawl/replay.sh", str(doc))
    if False and "prints no numbered row or range" in rep:  # disabled: rows "sections" turned disputes into contents gaps (9076)
        sh("tools/recrawl/retire_file.sh", str(f.relative_to(ROOT)), "rows 'none' refused (no numbered row or range); re-recorded with rows 'sections'")
        L[0]["source_contents_region"]["rows"] = "sections"
        L[0]["fixes"] = L[0]["fixes"].replace("(rows 'none')", "(rows 'sections')")
        for k in ("match_text", "before_text", "after_text"):
            L[0].pop(k, None)
        f = Q / f"patches/patch-{doc}cr2.json"; f.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")
        rec = sh("tools/recrawl/recfile.sh", str(f.relative_to(ROOT)))
        rep = sh("tools/recrawl/replay.sh", str(doc))
    a = state(doc)
    if a[0] or (a[1] + a[2]) < (b[1] + b[2]):
        print(doc, "KEPT", b, "->", a, "RELEASED" if a[0] else "", rec.strip()[:40])
    else:
        sh("tools/recrawl/retire_file.sh", str(f.relative_to(ROOT)), "contents-region trial reverted: no gain")
        sh("tools/recrawl/replay.sh", str(doc))
        print(doc, "REVERTED", b, "->", a, "->", state(doc), [l for l in rep.splitlines() if "ERROR" in l][:1])
