"""Print the live pending S7 units and contents gaps of the given documents (read-only).

    python tools/recrawl/units_for.py DOC [DOC ...]"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
docs = [int(x) for x in sys.argv[1:]]
with connect() as conn, conn.cursor() as cur:
    for doc in docs:
        cur.execute("SELECT i.short_title, d.lane, d.page_count FROM instrument i JOIN document d ON d.id=i.document_id "
                    "WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL LIMIT 1", (doc,))
        t = cur.fetchone()
        print(f"=== doc {doc} {t}")
        cur.execute(r"""
          SELECT c.printed_label, c.canonical_source_page, c.source_page, kp.kind::text, cp.kind::text,
                 subpath(kp.path, 3)::text, subpath(cp.path, 3)::text,
                 coalesce(kp.heading,''), left(regexp_replace(coalesce(kv.text_en,''), '\s+', ' ', 'g'), 200), length(coalesce(kv.text_en,'')),
                 coalesce(cp.heading,''), left(regexp_replace(coalesce(cv.text_en,''), '\s+', ' ', 'g'), 200), length(coalesce(cv.text_en,'')), c.id::text
            FROM v_structural_adjudication_pending p
            JOIN segmentation_structural_candidate c ON c.id=p.id
            JOIN provision cp ON cp.id=c.candidate_provision_id LEFT JOIN provision_version cv ON cv.provision_id=cp.id
            JOIN provision kp ON kp.id=c.canonical_provision_id LEFT JOIN provision_version kv ON kv.provision_id=kp.id
           WHERE c.document_id=%s ORDER BY c.source_page""", (doc,))
        for r in cur.fetchall():
            print(f"  S7 label {r[0]!r}: kept p{r[1]} {r[3]} {r[5]} [{r[9]}c] {r[7][:50]!r} :: {r[8]}")
            print(f"   {r[13]}  demoted p{r[2]} {r[4]} {r[6]} [{r[12]}c] {r[10][:50]!r} :: {r[11]}")
        cur.execute("""SELECT g.printed_label, g.printed_heading, g.source_page FROM v_toc_gap_pending g
                        WHERE g.document_id=%s ORDER BY g.source_page, g.printed_label""", (doc,))
        for r in cur.fetchall():
            print(f"  TOC p{r[2]} {r[0]!r} {str(r[1])[:70]!r}")
