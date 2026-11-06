"""pintrial.py DOC [DOC ...] : try profile unreleased-v4 on held documents (writes; guarded).

Before/after = (released?, pending S7 units, pending contents gaps) of the document. The v4 pin is KEPT when the doc
releases or its pending total falls; otherwise the doc is pinned back to 'default' and replayed. Prints one line each."""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
sh = lambda *a: subprocess.run(["bash", *a], cwd=ROOT, capture_output=True, text=True).stdout

def state(doc):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT bool_and(EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)),
                         (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=%s),
                         (SELECT count(*) FROM v_toc_gap_pending g WHERE g.document_id=%s)
                         FROM instrument i WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL""", (doc, doc, doc))
        return cur.fetchone()

for doc in map(int, sys.argv[1:]):
    b = state(doc)
    if b[0]:
        print(doc, "already released"); continue
    out = sh("tools/recrawl/pinv4.sh", str(doc))
    a = state(doc)
    if a[0] or (a[1] + a[2]) < (b[1] + b[2]):
        print(doc, "KEPT v4", b, "->", a, "RELEASED" if a[0] else "")
    else:
        sh("tools/recrawl/pindefault.sh", str(doc))
        c = state(doc)
        if (c[1] + c[2]) > (a[1] + a[2]):     # the default replay lost carried decisions: v4 is the lesser evil
            sh("tools/recrawl/pinv4.sh", str(doc))
            print(doc, "v4 again (default replay worse)", b, "->", a, "->", c, "->", state(doc))
        else:
            print(doc, "back to default", b, "->", a, "->", c)
