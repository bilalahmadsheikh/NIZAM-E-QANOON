"""ocr_policy.py DOC [DOC ...] [--apply] : owner decision q4 (24 Oct 2026) -- accept a Surya page reading without
page-by-page review where it agrees closely with the document's existing reading of that page.

Per page: word-sequence agreement = difflib ratio over lower-case alphanumeric tokens of the Surya candidate and the
active document's text on that page. >= 0.85 (and the Surya page non-empty) -> 'accepted', decided_by the owner's
policy, evidence carrying the ratio. Pages below go to an owner review pack. Prints per document how many pages pass;
a document is promotable only when every page is accepted. Writes only with --apply."""
import difflib, json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE
POLICY = ".artifacts/decision-review/exports/owner-decision-2026-10-24-q4-ocr-agreement.json"
TH = 0.85
apply = "--apply" in sys.argv
docs = [int(a) for a in sys.argv[1:] if a.isdigit()]
tok = lambda s: re.findall(r"[a-z0-9]+", (s or "").lower())
with connect() as conn, conn.cursor() as cur:
    for d in docs:
        cur.execute("SELECT page_no, string_agg(text, ' ' ORDER BY reading_order) FROM text_block WHERE document_id=%s GROUP BY 1", (d,))
        old = dict(cur.fetchall())
        cur.execute("""SELECT c.id, c.page_no, c.text FROM page_ocr_candidate c WHERE c.document_id=%s AND c.engine=%s
                        AND NOT EXISTS (SELECT 1 FROM page_ocr_adjudication a WHERE a.candidate_id=c.id)""", (d, ENGINE))
        rows = cur.fetchall()
        ok, low = [], []
        for cid, p, text in rows:
            a, b = tok(text), tok(old.get(p))
            r = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0
            (ok if r >= TH else low).append((p, cid, round(r, 3)))
        cur.execute("SELECT count(*) FROM page_ocr_candidate WHERE document_id=%s AND engine=%s", (d, ENGINE))
        total = cur.fetchone()[0]
        print(f"doc {d}: {len(ok)}/{len(rows)} undecided pages agree (>= {TH}); total candidate pages {total}; "
              f"below: {sorted((p, r) for p, _, r in low)[:12]}")
        if apply:
            for p, cid, r in ok:
                cur.execute("""INSERT INTO page_ocr_adjudication (candidate_id, decision, reason, evidence, decided_by)
                               VALUES (%s, 'accepted', %s, %s, %s) ON CONFLICT DO NOTHING""",
                            (cid, f"Owner policy q4 (24 Oct 2026): the Surya reading agrees with the existing reading of "
                                  f"this page (word-sequence ratio {r} >= {TH}); accepted without page-by-page review.",
                             json.dumps({"policy": POLICY, "agreement_ratio": r, "threshold": TH, "page_no": p,
                                         "document_id": d, "method": "difflib ratio over lower-case alphanumeric tokens"}),
                             "bilalahmadsheikh (owner policy q4, applied by the lead)"))
    if apply:
        conn.commit()
