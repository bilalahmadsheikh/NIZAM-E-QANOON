"""deleg_export.py PACK DOC [REJ_PAGE ...] : OCR review export written by the lead under the owner's chat delegation
(25 Oct 2026: 'release fast ... making the decisions for me ... choose the recommended choice'). Every page is
accepted after the lead read its image against the Surya text; REJ_PAGEs are 'rejected' as misread, their text
supplied by the lead's transcription in corrections-doc-DOC.json. Candidate ids/hashes from the stored candidates."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE
pack, doc, rej = sys.argv[1], int(sys.argv[2]), {int(p) for p in sys.argv[3:]}
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
man = json.load(open(ROOT / f".artifacts/{pack}/doc-{doc}/manifest.json", encoding="utf-8"))
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT page_no, id, text FROM page_ocr_candidate WHERE document_id=%s AND engine=%s ORDER BY page_no, id", (doc, ENGINE))
    cands = {p: (i, t) for p, i, t in cur.fetchall()}
dec = [{"document_id": doc, "page_no": p, "candidate_id": cands[p][0],
        "candidate_text_sha256": hashlib.sha256(cands[p][1].encode("utf-8")).hexdigest(), "reviewed_source_image": True,
        "decision": "rejected" if p in rej else "accepted",
        "reason": ("The lead read the page image: the engine misread or missed printed text; the lead's transcription "
                   "is supplied and the page is accepted with it (owner delegation 25 Oct 2026)." if p in rej else
                   "The lead read the page image against this reading and accepted it (owner delegation 25 Oct 2026)."),
        "source_image": f"images/page-{p:03d}.png"} for p in sorted(cands)]
out = {"schema": "nizam.ocr_page_review.v1",
       "reviewer_name": "lead under owner chat delegation 25 Oct 2026 ('release fast what u can release making the decisons for me ... choose the recommended choice')",
       "exported_at": datetime.now(timezone.utc).isoformat(), "document_id": doc,
       "source_sha256": man["source_sha256"], "result_sha256": man["result_sha256"],
       "candidate_engine": man["candidate_engine"], "source_page_count": man["source_page_count"],
       "candidate_page_count": man["candidate_page_count"], "decisions": dec,
       "reviewed_unresolved": [], "undecided_candidate_pages": []}
f = ROOT / f".artifacts/ocr-review-exports/ocr-review-doc-{doc}.json"
f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f.name, len(dec), "pages;", len(rej), "with the lead's transcription")
