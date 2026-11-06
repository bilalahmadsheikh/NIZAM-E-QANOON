"""status_all.py OUT.csv : every unreleased active instrument with lane, quality, S7, gaps, pages, and which
pipeline already covers it (read-only). Prints a grouped summary."""
import csv, json, os, re, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
Q = Path("/mnt/e/nizam-data/ocr"); R = Path("/mnt/e/Nizam_e_Qanoon")
pt = {}
for f in list(Q.glob("pt-in-*/*.pdf")) + list(Q.glob("pt-skip-toc/*.pdf")):
    m = re.fullmatch(r"(\d+)-page(\d+)", f.stem)
    if m: pt.setdefault(int(m.group(1)), []).append(f.parent.name)
ptdone = {int(m.group(1)) for d in (Q / "pt-output").glob("*-page*") if (m := re.fullmatch(r"(\d+)-page\d+", d.name))}
q1d = {int(p.name[4:]) for p in (R / ".artifacts/ocr-review-pack-q1d").glob("doc-*")}
exported = {int(re.search(r"(\d+)", p.name).group(1)) for p in (R / ".artifacts/ocr-review-exports").glob("ocr-review-doc-*.json")}
q1r_wait = {int(p.stem) for p in (Q / "q1r-input").glob("*.pdf") if not (Q / "q1r-output" / p.stem / "results.json").exists()}
q1r_later = {int(p.stem) for p in (Q / "q1r-input-later").glob("*.pdf")}
with connect() as conn, conn.cursor() as cur:
    cur.execute("""
      SELECT i.document_id, left(i.short_title,70), d.lane, d.page_count,
        (SELECT q.overall_outcome FROM v_document_quality_status q WHERE q.document_id=i.document_id),
        (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=i.document_id),
        (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id),
        (SELECT count(*) FROM v_boundary_adjudication_pending b WHERE b.instrument_id=i.id),
        (SELECT r.toc_found FROM segmentation_run r WHERE r.instrument_id=i.id ORDER BY r.run_at DESC LIMIT 1),
        (SELECT count(*) FROM provision p WHERE p.instrument_id=i.id AND p.is_active AND p.kind IN ('section','article'))
      FROM instrument i JOIN document d ON d.id=i.document_id
      WHERE i.is_active AND i.duplicate_of IS NULL AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
      ORDER BY i.document_id""")
    rows = cur.fetchall()
    cur.execute("SELECT count(*) FROM v_release_instrument"); rel = cur.fetchone()[0]
out = []
for d, t, lane, pages, qs, s7, gaps, bnd, toc, secs in rows:
    if qs != "passed":
        cls = ("ocr:q1d-exported" if d in exported and d in q1d else "ocr:q1d-awaiting-owner" if d in q1d
               else "ocr:surya-queued" if d in q1r_wait else "ocr:surya-deferred-large" if d in q1r_later else "quality:other")
    elif bnd: cls = "boundary"
    elif s7 and gaps: cls = "s7+gaps"
    elif s7: cls = "s7-only"
    else: cls = "gaps-only"
    cover = ("pt-queued" if d in pt and d not in ptdone else "pt-read" if d in ptdone else "")
    out.append(dict(doc=d, title=t, lane=lane, pages=pages, quality=qs, s7=s7, gaps=gaps, boundary=bnd,
                    toc_found=toc, sections=secs, cls=cls, surya_pages=cover))
with open(sys.argv[1], "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print("released", rel, "| unreleased", len(out))
from collections import Counter, defaultdict
c = Counter(x["cls"] for x in out); print(dict(c))
for k in ("s7-only", "gaps-only", "s7+gaps"):
    xs = [x for x in out if x["cls"] == k]
    lanes = Counter(x["lane"] for x in xs)
    small = sum(1 for x in xs if x["s7"] + x["gaps"] <= 3)
    notoc = sum(1 for x in xs if not x["toc_found"])
    ptq = Counter(x["surya_pages"] for x in xs)
    print(f"{k}: {len(xs)} docs, units {sum(x['s7'] for x in xs)} S7 / {sum(x['gaps'] for x in xs)} gaps; lanes {dict(lanes)}; <=3 blockers {small}; no contents list {notoc}; surya {dict(ptq)}")
qo = [x for x in out if x["cls"].startswith(("ocr", "quality"))]
print("quality-held by lane:", dict(Counter(x["lane"] for x in qo)), "pages:", sum(x["pages"] or 0 for x in qo))
