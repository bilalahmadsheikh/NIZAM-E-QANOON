"""Agent D (read-only): top-level units of each doc + section labels seen twice. rootD.py DOC..."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    for doc in map(int, sys.argv[1:]):
        cur.execute(r"""SELECT p.kind::text, p.label, p.first_page, coalesce(p.heading,''),
                              left(regexp_replace(coalesce(v.text_en,''),'\s+',' ','g'),60), length(coalesce(v.text_en,''))
                         FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
                         LEFT JOIN provision_version v ON v.provision_id=p.id
                        WHERE i.document_id=%s AND p.is_active AND nlevel(p.path)=4 ORDER BY p.first_page, p.path""", (doc,))
        rows = cur.fetchall()
        print(f"=== {doc}: {len(rows)} top-level")
        for r in rows:
            if r[0] not in ("section", "rule", "regulation") or len(rows) < 40:
                print(f"  {r[0]:9} {r[1]!s:8} p{r[2]} [{r[5]}c] {r[3][:30]!r} :: {r[4]}")
        cur.execute(r"""SELECT p.kind::text, p.label, count(*) FROM provision p
                         JOIN instrument i ON i.id=p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
                        WHERE i.document_id=%s AND p.is_active AND p.kind::text IN ('section','article','rule','regulation')
                        GROUP BY 1,2 HAVING count(*)>1""", (doc,))
        for r in cur.fetchall():
            print(f"  DUP {r}")
