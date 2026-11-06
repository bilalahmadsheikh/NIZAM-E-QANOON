"""pt_trial.py DOC [PAGE ...] : would promoting the Surya re-read of PAGE(s) improve DOC's tree? (read-only)

Segments the document twice in memory with its recorded inputs -- as stored, and with each named page's blocks
replaced by its latest Surya candidate's blocks (as tools/promote_ocr_adjudicated.py would) -- and prints both
outcomes: contents found, rows matched / missing, repeated labels demoted, sections. Exit 0 = not worse
(no new missing row, no more demotions, contents still found), 1 = worse or failed. Pages default to every page
with an undecided Surya candidate. A re-read of p6 of doc 9563 lost its whole contents region (24 Oct)."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.corpus import segment as S
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE
from nizam.workers.segment import reviewed_structural_overrides
doc = int(sys.argv[1]); pages = [int(x) for x in sys.argv[2:]]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active LIMIT 1", (doc,))
    obs = cur.fetchone()[0]
    if not pages:
        cur.execute("""SELECT DISTINCT page_no FROM page_ocr_candidate c WHERE document_id=%s AND engine=%s
                        AND NOT EXISTS (SELECT 1 FROM page_ocr_adjudication a WHERE a.candidate_id=c.id)""", (doc, ENGINE))
        pages = [r[0] for r in cur.fetchall()]
    cand = {}
    for p in pages:
        cur.execute("SELECT blocks FROM page_ocr_candidate WHERE document_id=%s AND page_no=%s AND engine=%s ORDER BY id DESC LIMIT 1", (doc, p, ENGINE))
        cand[p] = cur.fetchone()[0]
        cur.execute("SELECT height FROM page WHERE document_id=%s AND page_no=%s", (doc, p)); cand[p] = (cand[p], float(cur.fetchone()[0] or 792))
        if not cand[p][0]:
            # the engine read nothing (doc 5610 pp2-3, one upside down): the page keeps its stored text in the trial,
            # and ocr_trial_accept.py does not accept the empty reading
            print(f"  page {p}: empty re-read, stored text kept"); del cand[p]
prof = legal_write.segmentation_profile_for(obs)
blocks = legal_write.blocks_for(doc)
patches = legal_write.segmentation_patches_for(obs)
tocd = legal_write.toc_dispositions_for(obs)
res = legal_write.structural_resolutions_for(doc)
over = reviewed_structural_overrides(res, patches) or None
kw = {} if prof == "default" else {"profile": prof}
def run(bl):
    try:
        s = S.segment(bl, curation_patches=patches, toc_dispositions=tocd, structural_resolutions=res, structural_overrides=over, **kw)
    except Exception as x:
        return None, f"FAILED {type(x).__name__}: {str(x)[:120]}"
    secs = sum(1 for n in s.flatten() if n.kind in ("section", "article"))
    return s, f"toc_found={s.toc_found} matched={s.matched} missing={len(s.missing)} demoted={s.repeated_labels_demoted} sections={secs}"
new = []; fake = -1
for b in blocks:
    if b["page_no"] in cand:
        if not any(x["page_no"] == b["page_no"] for x in new):
            bl, h = cand[b["page_no"]]
            for c in bl:
                x0, y0, x1, y1 = c["bbox"]
                new.append({"id": fake, "text": c["text"], "page_no": b["page_no"], "y0": float(y0), "page_height": h, "x0": float(x0), "x1": float(x1)}); fake -= 1
        continue
    new.append(b)
a, sa = run(blocks)
import os
if os.environ.get("STALE") == "drop":
    # A patch written for the replaced text layer of a re-read page no longer finds its anchor there;
    # tools/recrawl/retire_stale.py retires it after promotion. The re-read is judged without it (named here).
    texts = {}
    for x in new:
        texts.setdefault(x["page_no"], []).append(x["text"] or "")
    keep = []
    for pt in patches:
        if pt.get("page_no") in cand and sum((pt.get("match_text") or "") in t for t in texts.get(pt["page_no"], [])) != 1:
            print(f"  stale patch dropped for the re-read: {pt.get('id')} p{pt.get('page_no')} {(pt.get('match_text') or '')[:50]!r}")
            continue
        keep.append(pt)
    patches = keep
    over = reviewed_structural_overrides(res, patches) or None
b_, sb = run(new)
print(f"doc {doc} pages {pages} profile {prof}\n  stored : {sa}\n  re-read: {sb}")
import os
if os.environ.get("SHOW"):            # SHOW=1 prints both section trees (label, first words) to compare the text
    for name, s in (("stored", a), ("re-read", b_)):
        print(f"  -- {name}")
        top = {id(c) for c in (s.root.children if s else [])}
        for n in (s.flatten() if s else []):
            # a top-level clause is a demoted repeat of a section label -- shown so its cause can be read
            if n.kind in ("section", "article", "part", "chapter", "schedule") or (n.kind == "clause" and id(n) in top):
                print(f"    {n.kind:8} {n.label!s:8} {' '.join((n.text or '').split())[:110]}")
ok = (a is not None and b_ is not None and (b_.toc_found or not a.toc_found)
      and len(b_.missing) <= len(a.missing) and b_.repeated_labels_demoted <= a.repeated_labels_demoted)
print("  verdict:", "NOT WORSE" if ok else "WORSE -- do not promote")
sys.exit(0 if ok else 1)
