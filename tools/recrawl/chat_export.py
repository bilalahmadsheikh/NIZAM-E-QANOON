"""chat_export.py DOC [PAGE ...] : write an OCR review export for DOC from the owner's chat answer (24 Oct 2026):
every page accepted except the PAGEs listed, which are 'rejected' as unread by the OCR (the owner supplied their
text; corrections-doc-DOC.json carries it). Candidate ids and text hashes come from the stored Surya candidates."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE
doc, rej = int(sys.argv[1]), {int(p) for p in sys.argv[2:]}
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
man = json.load(open(ROOT / f".artifacts/ocr-review-pack-q1c/doc-{doc}/manifest.json", encoding="utf-8"))
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT page_no, id, text FROM page_ocr_candidate WHERE document_id=%s AND engine=%s ORDER BY page_no", (doc, ENGINE))
    cands = {p: (i, t) for p, i, t in cur.fetchall()}
dec = []
for p in sorted(cands):
    i, t = cands[p]
    dec.append({"document_id": doc, "page_no": p, "candidate_id": i,
                "candidate_text_sha256": hashlib.sha256(t.encode("utf-8")).hexdigest(), "reviewed_source_image": True,
                "decision": "rejected" if p in rej else "accepted",
                "reason": ("Page has text the OCR did not detect; the owner transcribed it in chat (24 Oct 2026) and the "
                           "page is accepted with that text." if p in rej else ""),
                "source_image": f"images/page-{p:03d}.png"})
out = {"schema": "nizam.ocr_page_review.v1",
       "reviewer_name": "Bilal Ahmad (decision given in chat 24 Oct 2026; written to this export by the lead)",
       "exported_at": datetime.now(timezone.utc).isoformat(), "document_id": doc,
       "source_sha256": man["source_sha256"], "result_sha256": man["result_sha256"],
       "candidate_engine": man["candidate_engine"], "source_page_count": man["source_page_count"],
       "candidate_page_count": man["candidate_page_count"], "decisions": dec,
       "reviewed_unresolved": [], "undecided_candidate_pages": []}
f = ROOT / f".artifacts/ocr-review-exports/ocr-review-doc-{doc}.json"
f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f, len(dec), "pages;", len(rej), "rejected with owner text")
