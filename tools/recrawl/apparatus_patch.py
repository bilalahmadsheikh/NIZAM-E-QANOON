"""apparatus_patch.py SPEC.json OUT_DIR SUFFIX -- one page-read apparatus patch file per document.

SPEC is a list of {"document_id", "page_no", "blocks": [ids], "what": "the printed thing, in words"}; every block named
must be wholly that thing (a reader checked each one). Writes OUT_DIR/patch-<doc><SUFFIX>.json with one entry per page
(rule reviewed_apparatus_block), renders each page; tools/recrawl/fill_patch.py then adds sha256 and locators."""
import collections, json, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon"); REL = ".artifacts/release-work-2026-09-24/claude/renders"
spec, out_dir, suffix = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]), sys.argv[3]
by_doc = collections.defaultdict(list)
for s in spec:
    by_doc[s["document_id"]].append(s)
with connect() as conn, conn.cursor() as cur:
    for doc, items in by_doc.items():
        cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (doc,))
        pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
        out = []
        for s in sorted(items, key=lambda s: s["page_no"]):
            cur.execute("SELECT id, text FROM text_block WHERE document_id=%s AND page_no=%s AND id = ANY(%s)",
                        (doc, s["page_no"], s["blocks"]))
            found = dict(cur.fetchall())
            assert set(found) == set(s["blocks"]), (doc, s["page_no"], set(s["blocks"]) - set(found))
            render = f"{REL}/doc{doc}-p{s['page_no']}.png"
            if not (ROOT / render).exists():
                pdf[s["page_no"] - 1].get_pixmap(dpi=110).save(ROOT / render)
            first = " ".join(found[s["blocks"][0]].split())
            out.append({"document_id": doc, "page_no": s["page_no"], "source_apparatus_blocks": s["blocks"],
                        "defect": f"{s['what']} was read into a provision's text",
                        "fixes": "rule reviewed_apparatus_block: the block(s) are set aside; no law text changes",
                        "observed": f"Page {s['page_no']} prints {s['what']} ({len(s['blocks'])} block(s), "
                                    f"the first {first[:140]!r})",
                        "render": render})
        f = out_dir / f"patch-{doc}{suffix}.json"
        f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f, len(out), "entries")
