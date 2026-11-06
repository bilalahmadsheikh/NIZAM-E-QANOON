"""Dump every pending S7 unit with what the page prints for the kept and the demoted occurrence (read-only).

    python tools/recrawl/s7_units.py OUT.jsonl
One JSON per unit: candidate id, document, lane, page(s), label, kept text, demoted text, their lengths, the
instrument's other open units, and s7_triage's verdict."""
import json, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon"); sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools")
from nizam.storage.db import connect
import s7_triage as T
with connect() as conn, conn.cursor() as cur:
    cur.execute("""
      SELECT c.id::text, c.document_id, c.instrument_id::text, c.printed_label, c.source_page, c.canonical_source_page,
             d.lane, cp.kind::text, kp.kind::text,
             coalesce(cv.text_en,''), coalesce(kv.text_en,''), coalesce(cp.heading,''), coalesce(kp.heading,''),
             (SELECT count(*) FROM v_structural_adjudication_pending x WHERE x.instrument_id=c.instrument_id),
             (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=c.instrument_id),
             cp.path::text, kp.path::text
        FROM v_structural_adjudication_pending p
        JOIN segmentation_structural_candidate c ON c.id=p.id
        JOIN document d ON d.id=c.document_id
        JOIN provision cp ON cp.id=c.candidate_provision_id LEFT JOIN provision_version cv ON cv.provision_id=cp.id
        JOIN provision kp ON kp.id=c.canonical_provision_id LEFT JOIN provision_version kv ON kv.provision_id=kp.id""")
    rows = cur.fetchall()
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    for (cid, doc, inst, label, page, kpage, lane, ckind, kkind, ctext, ktext, chead, khead, s7n, tocn, cpath, kpath) in rows:
        fh.write(json.dumps({"candidate_id": cid, "document_id": doc, "instrument_id": inst, "label": label,
                             "demoted_page": page, "kept_page": kpage, "lane": lane, "demoted_kind": ckind,
                             "kept_kind": kkind, "kept_heading": khead, "kept_text": ktext[:600], "kept_len": len(ktext),
                             "demoted_heading": chead, "demoted_text": ctext[:600], "demoted_len": len(ctext),
                             "instrument_s7_open": s7n, "instrument_toc_open": tocn,
                             "demoted_path": cpath, "kept_path": kpath}, ensure_ascii=False) + "\n")
print("units", len(rows))
