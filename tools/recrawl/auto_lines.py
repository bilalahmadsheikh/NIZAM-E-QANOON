"""auto_lines.py DOC OBS_TEMPLATE OUT : one C-line per pending S7 unit of DOC; template may use {label} {page} {text} {kpage}"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, tpl, out = int(sys.argv[1]), sys.argv[2], sys.argv[3]
with connect() as conn, conn.cursor() as cur:
    cur.execute(r"""SELECT c.id::text, c.printed_label, c.source_page, c.canonical_source_page,
                          left(regexp_replace(coalesce(v.text_en,''),'\s+',' ','g'),80)
                     FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id
                     LEFT JOIN provision_version v ON v.provision_id=c.candidate_provision_id
                    WHERE c.document_id=%s""", (doc,))
    rows = cur.fetchall()
with open(out, "a", encoding="utf-8") as fh:
    for cid, label, page, kpage, text in rows:
        fh.write(f"C{cid}|{doc}|{label}|{page}|" + tpl.format(label=label, page=page, kpage=kpage, text=text.replace("|", "/")) + "\n")
print(len(rows), "lines")
