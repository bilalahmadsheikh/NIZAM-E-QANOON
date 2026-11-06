"""Agent D (read-only): for each pending contents gap of DOC, body blocks that may print it.
findD.py DOC... -- blocks opening with the label, and blocks containing the heading's first words; with role + owner."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    for doc in map(int, sys.argv[1:]):
        cur.execute("""SELECT g.toc_entry_id, g.printed_label, coalesce(g.printed_heading,''), g.source_page
                         FROM v_toc_gap_pending g WHERE g.document_id=%s ORDER BY g.ordinal""", (doc,))
        gaps = cur.fetchall()
        cur.execute("""SELECT t.id, t.page_no, t.text, pb.role::text, p.kind::text, p.label
                         FROM text_block t
                         LEFT JOIN provision_block pb ON pb.block_id=t.id
                              AND pb.assignment_set_id = (SELECT pb2.assignment_set_id FROM provision_block pb2
                                   JOIN provision p2 ON p2.id=pb2.provision_id AND p2.is_active
                                   WHERE pb2.document_id=t.document_id LIMIT 1)
                         LEFT JOIN provision p ON p.id=pb.provision_id
                        WHERE t.document_id=%s ORDER BY t.page_no, t.reading_order""", (doc,))
        blocks = cur.fetchall()
        print(f"=== {doc}: {len(gaps)} gaps")
        for eid, lab, head, sp in gaps:
            print(f" GAP {eid} c.p{sp} {lab!r} {head[:60]!r}")
            words = [w for w in re.findall(r"[A-Za-z]{4,}", head)][:3]
            lab_rx = re.compile(r"^\W{0,4}" + re.escape(lab) + r"\s*[.,:]", re.I)
            shown = 0
            for bid, pg, text, role, pk, pl in blocks:
                if pg == sp:
                    continue
                t = (text or "").strip()
                hit = lab_rx.match(t) or (len(words) >= 2 and all(w.lower() in t.lower()[:200] for w in words[:2]))
                if hit and shown < 6:
                    shown += 1
                    print(f"    blk {bid} p{pg} {role}/{pk} {pl}: {re.sub(r'\s+', ' ', t)[:110]}")
