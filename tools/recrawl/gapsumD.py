"""Agent D (read-only): per doc in the list, pending gap count and how many gap headings look like omissions."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
docs = [int(x) for x in open("/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/list-opusD.txt").read().split()]
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT g.document_id, count(*),
                          count(*) FILTER (WHERE g.printed_heading ~* 'omitted|repealed|^\[?\s*\*'),
                          (SELECT count(*) FROM v_structural_adjudication_pending s WHERE s.instrument_id=g.instrument_id),
                          string_agg(g.printed_label||':'||left(coalesce(g.printed_heading,''),25), ' | ' ORDER BY g.ordinal)
                     FROM v_toc_gap_pending g WHERE g.document_id = ANY(%s)
                    GROUP BY g.document_id, g.instrument_id ORDER BY 2""", (docs,))
    for r in cur.fetchall():
        print(f"{r[0]}\t{r[1]}\tomit={r[2]}\ts7={r[3]}\t{r[4][:160]}")
