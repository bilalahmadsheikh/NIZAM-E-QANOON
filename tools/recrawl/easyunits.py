"""easyunits.py OUT.json : pending S7 units of held docs whose DEMOTED text looks like non-provision matter (read-only).
Classes: tariff (PCT code), rate (Rs./per cent/% amounts), field (short line ending ':' or a form label),
decimal (bare 'N.N' paragraph number), head (Gazette running head), short (<= 25 chars of text).
Only units the stub guard would accept (demoted < 500 chars or kept >= half of it) are listed."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
SQL = r"""
SELECT c.id::text, c.document_id, c.printed_label, c.source_page, c.canonical_source_page,
       (SELECT coalesce(sum(length(t.text)),0) FROM provision_block pb JOIN text_block t ON t.id=pb.block_id WHERE pb.provision_id=c.candidate_provision_id),
       (SELECT coalesce(sum(length(t.text)),0) FROM provision_block pb JOIN text_block t ON t.id=pb.block_id WHERE pb.provision_id=c.canonical_provision_id),
       (SELECT t.text FROM text_block t WHERE t.id=c.source_block_id)
  FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id
 WHERE NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=c.instrument_id)"""
rx = [("tariff", re.compile(r"^\W*\d{4}\.\d{2,4}")), ("rate", re.compile(r"(?i)\bRs\.?\s*\d|per\s*cent|\d\s*%|ad\s*val")),
      ("head", re.compile(r"(?i)GAZETTE\s+OF|GOVT\.?\s*GAZETTE")), ("decimal", re.compile(r"^\W*\d{1,2}\.\d{1,2}\W*$")),
      ("field", re.compile(r"^.{3,70}:\s*$"))]
out = []
with connect() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    for cid, doc, lab, dp, kp, dlen, klen, text in cur.fetchall():
        t = re.sub(r"\s+", " ", text or "").strip()
        if not (dlen < 500 or klen >= dlen / 2):
            continue
        cls = next((n for n, r in rx if r.search(t)), "short" if len(t) <= 25 else None)
        if cls:
            out.append({"cid": cid, "doc": doc, "label": lab, "page": dp, "kept_page": kp, "cls": cls, "text": t[:100]})
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
import collections
print(len(out), "units in", len({x["doc"] for x in out}), "docs", dict(collections.Counter(x["cls"] for x in out)))
