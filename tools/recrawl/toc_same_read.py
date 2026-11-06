"""toc_same_read.py DOC "observed" [LABEL=PAGE ...] : page-read 'found_elsewhere' readings for DOC's pending contents
rows whose printed label is exactly one section of the instrument (read-only; writes the readings JSON to stdout).
For a contents row the parser took from a fragment of the number column (doc 9713 p1: '10.' and '16. / VA' sit
apart from their headings) when the body prints that section. LABEL=PAGE names the body page that prints it; every
page of the document must have its render. Record with tools/adjudicate_toc_from_source.py --readings."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
REL = ".artifacts/release-work-2026-09-24/claude/renders"
doc, obs = int(sys.argv[1]), sys.argv[2]
pages = dict(a.split("=") for a in sys.argv[3:])
out = []
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT g.toc_entry_id, g.printed_label, g.printed_heading, g.source_page FROM v_toc_gap_pending g
                     JOIN instrument i ON i.id=g.instrument_id WHERE i.document_id=%s""", (doc,))
    for tid, label, heading, tpage in cur.fetchall():
        cur.execute("""SELECT p.id, p.first_page FROM provision p JOIN instrument i ON i.id=p.instrument_id
                        WHERE i.document_id=%s AND i.is_active AND p.is_active AND p.kind='section'
                          AND p.label=%s""", (doc, label))
        hits = cur.fetchall()
        if len(hits) != 1 or label not in pages:
            print(f"skip {label!r}: {len(hits)} sections" + ("" if label in pages else ", no page named"), file=sys.stderr)
            continue
        pid, first = hits[0]
        rs = [{"path": f"{REL}/doc{doc}-p{p}.png",
               "sha256": hashlib.sha256((ROOT / f"{REL}/doc{doc}-p{p}.png").read_bytes()).hexdigest()}
              for p in sorted({int(tpage), int(pages[label])})]
        out.append({"document_id": doc, "toc_entry_id": tid, "resolution": "found_elsewhere",
                    "found_provision_id": str(pid), "source_page": int(pages[label]),
                    "observed": f"Contents row {label!r} (read from page {tpage} as {heading!r}): " + obs
                                + f" Page {pages[label]} prints section {label}.", "renders": rs})
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
