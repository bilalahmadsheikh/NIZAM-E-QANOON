"""tocread.py LINES OUT.json : contents-gap readings for tools/adjudicate_toc_from_source.py (read-only on the DB).
Lines: FE|doc|label|path|page|render_pages(comma)|observed   -> found_elsewhere at the active provision on that ltree path
       AB|doc|label||page|render_pages(comma)|observed         -> absent_in_source (the promised unit is printed nowhere)
The pending entry is the one gap of the doc with that printed label (refuses when 0 or >1)."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
R = Path("/mnt/e/Nizam_e_Qanoon/.artifacts/release-work-2026-09-24/claude/renders")
out = []
with connect() as conn, conn.cursor() as cur:
    for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"): continue
        kind, doc, label, path, page, pages, obs = line.split("|", 6)
        cur.execute("SELECT toc_entry_id FROM v_toc_gap_pending WHERE document_id=%s AND printed_label=%s AND toc_entry_id IS NOT NULL", (int(doc), label))
        e = cur.fetchall(); assert len(e) == 1, (doc, label, e)
        r = {"document_id": int(doc), "toc_entry_id": e[0][0], "source_page": int(page), "observed": obs}
        if kind == "AB":
            r["resolution"] = "absent_in_source"
        else:
          cur.execute("""SELECT p.id::text FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active
                        WHERE i.document_id=%s AND p.is_active AND p.path::text LIKE '%%.' || %s""", (int(doc), path))
          p = cur.fetchall(); assert len(p) == 1, (doc, path, p)
          r.update(resolution="found_elsewhere", found_provision_id=p[0][0])
        renders = []
        for pg in pages.split(","):
            f = R / f"doc{doc}-p{pg}.png"
            renders.append({"path": str(f.relative_to("/mnt/e/Nizam_e_Qanoon")), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
        r["renders"] = renders
        out.append(r)
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(out), "reading(s) ->", sys.argv[2])
