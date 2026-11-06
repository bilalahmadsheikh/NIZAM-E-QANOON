"""Export the blocked queue: one row per held instrument (read-only). queue_export.py OUT.tsv"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute(r"""
      SELECT i.document_id, coalesce(i.year,0), d.lane, d.page_count, q.overall_outcome,
             (SELECT count(*) FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id),
             (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id),
             (SELECT count(*) FROM v_boundary_adjudication_pending b WHERE b.instrument_id=i.id),
             split_part(b.object_key,'/',2), regexp_replace(left(i.short_title,70),'\s+',' ','g')
        FROM instrument i JOIN document d ON d.id=i.document_id AND d.is_active
        JOIN blob b ON b.sha256=d.sha256 JOIN v_document_quality_status q ON q.document_id=d.id
       WHERE i.is_active AND i.duplicate_of IS NULL
         AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
       ORDER BY 2 DESC, 1""")
    rows = cur.fetchall()
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    fh.write("doc\tyear\tlane\tpages\tquality\ts7\ttoc\tboundary\tsource\ttitle\n")
    for r in rows:
        fh.write("\t".join(str(x) for x in r) + "\n")
print(len(rows), "held instruments")
