"""colab_bundle.py STATUS.csv OUTDIR : input PDFs for the Colab GPU Surya run, in priority folders (read-only on DB).
  1-pages  page-targeted re-reads still unread (<doc>-page<N>.pdf, incl. the rotated 9665-page3)
  2-small  held-for-quality docs queued for Surya (<= 7 pp)
  3-holes  every held E4 document whose section numbering has holes (whole document, <doc>.pdf)
  4-large  the large deferred quality-held documents
Writes OUTDIR/manifest.json. Stems follow nizam.workers.import_surya_candidates (<doc> or <doc>-page<N>)."""
import csv, json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
Q = Path("/mnt/e/nizam-data/ocr"); out = Path(sys.argv[2]); rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
for k in ("1-pages", "2-small", "3-holes", "4-large"): (out / k).mkdir(parents=True, exist_ok=True)
man = {"1-pages": [], "2-small": [], "3-holes": [], "4-large": []}
done = {d.name for d in (Q / "pt-output").glob("*") if (d / "results.json").exists()}
for f in sorted(Q.glob("pt-in-*/*.pdf")):
    if f.stem in done: continue
    shutil.copy(f, out / "1-pages" / f.name); man["1-pages"].append(f.stem)
def whole(d, k):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (d,))
        shutil.copy(Path("/mnt/e/nizam-data") / cur.fetchone()[0], out / k / f"{d}.pdf")
    man[k].append(str(d))
for r in rows:
    if r["cls"] == "ocr:surya-queued": whole(int(r["doc"]), "2-small")
    elif r["cls"] == "ocr:surya-deferred-large": whole(int(r["doc"]), "4-large")
with connect() as conn, conn.cursor() as cur:
    for r in rows:
        if r["cls"] not in ("s7-only", "gaps-only", "s7+gaps") or r["lane"] != "E4": continue
        cur.execute("""SELECT p.label FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active
                        WHERE i.document_id=%s AND p.is_active AND p.kind IN ('section','article')""", (int(r["doc"]),))
        labs = [int(m.group(1)) for (l,) in cur.fetchall() if (m := re.fullmatch(r"(\d{1,3})", l or ""))]
        if labs and any(x not in set(labs) for x in range(1, max(labs) + 1)):
            whole(int(r["doc"]), "3-holes")
(out / "manifest.json").write_text(json.dumps(man, indent=1))
print({k: len(v) for k, v in man.items()})
