"""s7_pending.py DOC... : each pending S7 unit of the documents -- the kept and the demoted provision side by side
(path, page, text head and length), for a page read (read-only)."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
Q = """SELECT p.subpath_txt, p.first_page, coalesce(p.heading,''), coalesce(v.text_en,''),
              (SELECT coalesce(sum(length(pv.text_en)),0) FROM provision x JOIN provision_version pv ON pv.provision_id=x.id
                WHERE x.instrument_id=p.instrument_id AND x.is_active AND x.path <@ p.path)
         FROM (SELECT id, instrument_id, path, subpath(path, 3)::text AS subpath_txt, first_page, heading FROM provision WHERE id=%s) p
         LEFT JOIN provision_version v ON v.provision_id=p.id"""
with connect() as conn, conn.cursor() as cur:
    for d in map(int, sys.argv[1:]):
        cur.execute("""SELECT s.printed_label, s.decision_kind, s.canonical_provision_id, s.candidate_provision_id,
                              s.source_page, s.canonical_source_page FROM v_structural_adjudication_pending s
                         JOIN instrument i ON i.id=s.instrument_id WHERE i.document_id=%s""", (d,))
        for lab, kind, kept, dem, dp, kp in cur.fetchall():
            print(f"=== doc {d} label {lab!r} {kind}  kept p{kp} | demoted p{dp}")
            for tag, pid in (("KEPT", kept), ("DEM ", dem)):
                cur.execute(Q, (pid,))
                r = cur.fetchone()
                if r:
                    print(f"  {tag} {r[0]} p{r[1]} ({r[4]} chars): {(r[2] + ' :: ' + r[3])[:260]!r}")
