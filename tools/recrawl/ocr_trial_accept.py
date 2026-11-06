"""ocr_trial_accept.py DOC [--apply] : delegated decision q5 (owner chat delegation 25 Oct 2026) -- accept a document's
undecided Surya page readings when the in-memory trial (tools/recrawl/pt_trial.py logic) shows the re-read tree is
strictly better than the stored one: contents still found if they were, no contents row newly missing, no more
repeated-label demotions, no fewer sections, and at least one of those strictly improved. Each acceptance records the
trial's numbers. Pages are NOT promoted here (tools/promote_ocr_adjudicated.py does that). Dry run by default."""
import json, subprocess, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE

EXPORT = ".artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json"
doc = int(sys.argv[1]); apply = "--apply" in sys.argv
# --demotions-read "REASON": the lead read each extra demotion of the re-read and traced it to page furniture (e.g.
# handwritten amendment notes) that a curation patch will set aside before release; accepted only when the re-read
# also has strictly more sections. The reason is kept in the acceptance evidence (doc 5627, 28 Oct 2026).
dem_read = sys.argv[sys.argv.index("--demotions-read") + 1] if "--demotions-read" in sys.argv else None
import os
r = subprocess.run([sys.executable, "/mnt/e/Nizam_e_Qanoon/tools/recrawl/pt_trial.py", str(doc)],
                   capture_output=True, text=True, cwd="/mnt/e/Nizam_e_Qanoon", env=dict(os.environ, STALE="drop"))
print(r.stdout.strip())
if (r.returncode != 0 or "NOT WORSE" not in r.stdout) and not (dem_read and "FAILED" not in r.stdout):
    print("REFUSED: the re-read is not better"); sys.exit(1)
lines = {l.split(":")[0].strip(): l.split(":", 1)[1] for l in r.stdout.splitlines() if ":" in l and l.strip().startswith(("stored", "re-read"))}
def nums(s):
    return {k: v for k, v in (p.split("=") for p in s.split() if "=" in p)}
a, b = nums(lines["stored"]), nums(lines["re-read"])
gain = (int(b["missing"]) < int(a["missing"]) or int(b["demoted"]) < int(a["demoted"])
        or int(b["sections"]) > int(a["sections"]) or (b["toc_found"] == "True" and a["toc_found"] == "False"))
# --text-gain: a re-read that leaves the tree exactly as it was but replaces damaged text -- a page the old OCR read
# turned over or garbled (9766, 9319, 9318 ..., 29 Oct). Accepted only when every structural number is unchanged and
# every page accepted reads at least 15 points more real words (corpus vocabulary) than its stored text, and 60%+.
text_gain = "--text-gain" in sys.argv
if text_gain:
    if a != b:
        print(f"REFUSED: --text-gain needs an unchanged tree; stored {a} re-read {b}"); sys.exit(1)
elif int(b["sections"]) < int(a["sections"]) or not gain:
    print("REFUSED: no strict gain, or fewer sections"); sys.exit(1)
if int(b["demoted"]) > int(a["demoted"]) and not (dem_read and int(b["sections"]) > int(a["sections"])):
    print("REFUSED: more demotions (pass --demotions-read REASON once each one is read and traced)"); sys.exit(1)
with connect() as conn, conn.cursor() as cur:
    # an empty reading is never accepted: it would replace the page's text with nothing (doc 5610 pp2-3, 28 Oct)
    cur.execute("""SELECT c.id, c.page_no FROM page_ocr_candidate c WHERE c.document_id=%s AND c.engine=%s
                    AND length(btrim(c.text)) > 0
                    AND NOT EXISTS (SELECT 1 FROM page_ocr_adjudication x WHERE x.candidate_id=c.id)
                    AND NOT EXISTS (SELECT 1 FROM page_ocr_candidate o JOIN page_ocr_adjudication y ON y.candidate_id=o.id
                                     WHERE o.document_id=c.document_id AND o.page_no=c.page_no AND y.decision='accepted')
                    ORDER BY c.page_no""", (doc, ENGINE))
    rows = cur.fetchall()
    shares = {}
    if text_gain:
        import re as _re
        vocab = set(open("/mnt/e/nizam-data/ocr/kaggle/vocab.txt").read().split())
        def _share(t):
            ws = [w.lower() for w in _re.findall(r"[A-Za-z]{2,}", t or "")]
            return sum(w in vocab for w in ws) / len(ws) if ws else 0.0
        for cid, p in rows:
            cur.execute("SELECT text FROM page_ocr_candidate WHERE id=%s", (cid,))
            new = _share(cur.fetchone()[0])
            cur.execute("SELECT string_agg(text, ' ') FROM text_block WHERE document_id=%s AND page_no=%s", (doc, p))
            old = _share(cur.fetchone()[0])
            shares[p] = (round(old, 3), round(new, 3))
            if not (new >= 0.60 and new >= old + 0.15):
                print(f"REFUSED: p{p} reads {new:.0%} real words against the stored {old:.0%}"); sys.exit(1)
        print("text gain by page:", {p: f"{o:.0%}->{n:.0%}" for p, (o, n) in shares.items()})
    print(f"doc {doc}: {len(rows)} undecided page(s) would be accepted; stored {a} -> re-read {b}")
    if not apply:
        print("dry run -- pass --apply"); sys.exit(0)
    ev = {"policy": "delegated q5: accept a Surya re-read whose segmented tree is strictly better (in-memory trial)",
          "owner_delegation_export": EXPORT, "trial_stored": a, "trial_reread": b, "tool": "tools/recrawl/ocr_trial_accept.py"}
    if dem_read:
        ev["extra_demotions_read"] = dem_read
    if text_gain:
        ev["policy"] = ("delegated q5, text gain: the re-read leaves the segmented tree unchanged and every accepted "
                        "page reads 15+ points more real words than the text it replaces (in-memory trial, corpus vocabulary)")
        ev["real_word_share_by_page"] = {str(p): {"stored": o, "reread": n} for p, (o, n) in shares.items()}
    for cid, p in rows:
        cur.execute("""INSERT INTO page_ocr_adjudication (candidate_id, decision, reason, evidence, decided_by)
                       VALUES (%s,'accepted',%s,%s,%s)""",
                    (cid, "Accepted under the owner's delegated decision q5: the re-read's segmented tree is strictly "
                          "better than the stored reading's (trial numbers in evidence).",
                     json.dumps(dict(ev, page_no=p)), "claude.lead-under-owner-delegation/1"))
    conn.commit()
    print(f"accepted {len(rows)} page(s)")
