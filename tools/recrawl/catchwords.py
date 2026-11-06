"""Find pending S7 units whose KEPT unit opens on a printer's catchword (read-only).

A catchword: a short block (<= 40 chars) among the last three blocks of its page, printing 'N.' plus at most two words,
where the DEMOTED unit of the same label opens on the next page. Writes a JSON list for review sheets.
    python tools/recrawl/catchwords.py OUT.json"""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
SQL = r"""
WITH u AS (
  SELECT c.id::text cid, c.document_id doc, c.printed_label lab,
         (SELECT t.id FROM provision_block pb JOIN text_block t ON t.id=pb.block_id WHERE pb.provision_id=c.canonical_provision_id
           ORDER BY t.page_no, t.reading_order LIMIT 1) kb,
         (SELECT t.page_no FROM provision_block pb JOIN text_block t ON t.id=pb.block_id WHERE pb.provision_id=c.candidate_provision_id
           ORDER BY t.page_no, t.reading_order LIMIT 1) dpage
    FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id)
SELECT u.cid, u.doc, u.lab, t.id, t.page_no, t.text, u.dpage,
       (SELECT count(*) FROM text_block x WHERE x.document_id=t.document_id AND x.page_no=t.page_no AND x.reading_order>t.reading_order)
  FROM u JOIN text_block t ON t.id=u.kb"""
out = []
with connect() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    for cid, doc, lab, bid, page, text, dpage, after in cur.fetchall():
        one = re.sub(r"\s+", " ", text or "").strip()
        if len(one) <= 40 and after <= 2 and dpage == page + 1 and re.match(rf"^[:;.'\s]*{re.escape(str(lab))}\s*[.,]?\s*\S*(\s+\S+)?\s*$", one):
            out.append({"cid": cid, "doc": doc, "label": lab, "block": bid, "page": page, "text": one, "next_page": dpage})
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "catchword units in", len({x["doc"] for x in out}), "documents")
for x in out[:40]:
    print(x["doc"], x["label"], f"p{x['page']}", x["block"], repr(x["text"]))
