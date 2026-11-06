"""toc_incomplete.py DOC SI_ID PAGE "OBSERVED" [LABEL...] : readings closing a document's pending contents gaps as
source_incomplete (tools/adjudicate_toc_from_source.py) -> .artifacts/recrawl-queue/specs/tocinc-DOC.json.

Every pending gap is included unless LABELs are given. Renders: every docDOC-pN.png of the document. The reader must
already have checked that each listed row's unit is one the copy does not print (the declaration names them)."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
d, si, page, obs = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
labels = set(sys.argv[5:])
R = ROOT / ".artifacts/release-work-2026-09-24/claude/renders"
renders = [{"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
           for p in sorted(R.glob(f"doc{d}-p*.png"))]
with connect() as c, c.cursor() as cur:
    cur.execute("""SELECT g.toc_entry_id, g.printed_label, g.printed_heading FROM v_toc_gap_pending g
                     JOIN instrument i ON i.id=g.instrument_id WHERE i.document_id=%s""", (d,))
    rows = [r for r in cur.fetchall() if not labels or r[1] in labels]
out = [{"document_id": d, "toc_entry_id": t, "resolution": "source_incomplete", "source_incompleteness_id": si,
        "source_page": page, "observed": f"Contents row {lab} ('{(h or '')[:80]}'): {obs}", "renders": renders}
       for t, lab, h in rows]
p = ROOT / f".artifacts/recrawl-queue/specs/tocinc-{d}.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(p, len(out), "readings:", ", ".join(r[1] for r in rows))
