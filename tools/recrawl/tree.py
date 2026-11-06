"""Print an instrument's active section-level tree (read-only): python tools/recrawl/tree.py DOC [kinds]"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc = int(sys.argv[1]); kinds = (sys.argv[2] if len(sys.argv) > 2 else "section,article,part,chapter,clause").split(",")
with connect() as conn, conn.cursor() as cur:
    cur.execute(r"""SELECT p.first_page, p.kind::text, subpath(p.path,3)::text, p.label, coalesce(p.heading,''),
                          left(regexp_replace(coalesce(v.text_en,''),'\s+',' ','g'),110), length(coalesce(v.text_en,''))
                     FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
                     LEFT JOIN provision_version v ON v.provision_id=p.id
                    WHERE i.document_id=%s AND p.is_active AND p.kind::text = ANY(%s) AND nlevel(p.path) > 3
                    ORDER BY p.first_page, p.path""", (doc, kinds))
    for r in cur.fetchall():
        print(f"p{r[0]} {r[1]:8} {r[2]:28} [{r[6]}c] {r[4][:30]!r} :: {r[5]}")
