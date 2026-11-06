"""Write a structural reading naming every block of a page span (a schedule/appendix that holds no provision).

    python tools/recrawl/span_patch.py SPEC.json
SPEC: {"document_id", "page_no" (the cited render's page), "from_page", "to_page", "keys": ["table_row_blocks",
"no_cut_blocks"], "defect", "fixes", "observed", "out"}. Read-only on the database; fill_patch.py adds the locator."""
import json, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
s = json.loads(open(sys.argv[1], encoding="utf-8-sig").read())
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT page_no, array_agg(id ORDER BY id) FROM text_block WHERE document_id=%s AND page_no BETWEEN %s AND %s "
                "GROUP BY page_no ORDER BY page_no", (s["document_id"], s["from_page"], s["to_page"]))
    pages = cur.fetchall()
out = []
for page, ids in pages:
    r = {"document_id": s["document_id"], "page_no": page}
    for k in s["keys"]:
        r["source_" + k] = ids
    r["defect"], r["fixes"] = s["defect"], s["fixes"]
    r["observed"] = s["observed"] if page == s["page_no"] else s["observed_other"].replace("{page}", str(page))
    out.append(r)
json.dump(out, open(s["out"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "page readings ->", s["out"])
