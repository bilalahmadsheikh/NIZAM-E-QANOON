"""pintrial5.py DOC [DOC ...] : try profile unreleased-v5 on held documents (writes; guarded).
Kept when the doc releases or its pending total falls; otherwise re-pinned to its PREVIOUS profile and replayed (or v5
kept when that replay comes out worse)."""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ROOT = Path("/mnt/e/Nizam_e_Qanoon")
sh = lambda *a: subprocess.run(["bash", *a], cwd=ROOT, capture_output=True, text=True).stdout
PIN = ["/mnt/e/Nizam_e_Qanoon/.venv/bin/python", "tools/pin_segmentation_profile.py"]
def state(doc):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT bool_and(EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)),
                         (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=%s),
                         (SELECT count(*) FROM v_toc_gap_pending g WHERE g.document_id=%s),
                         max((SELECT profile FROM v_segmentation_profile_latest v WHERE v.source_observation_id=i.source_observation_id))
                         FROM instrument i WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL""", (doc, doc, doc))
        return cur.fetchone()
def pin(doc, prof):
    subprocess.run(PIN + ["--documents", str(doc), "--profile", prof, "--reason",
                          f"recrawl queue 2026-10-24: v5 trial -> {prof}", "--apply"], cwd=ROOT, capture_output=True,
                   env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"})
    return sh("tools/recrawl/replay.sh", str(doc))
for doc in map(int, sys.argv[1:]):
    b = state(doc)
    if b[0]:
        print(doc, "already released"); continue
    prev = b[3] or "default"
    if prev == "unreleased-v5":
        print(doc, "already v5"); continue
    pin(doc, "unreleased-v5"); a = state(doc)
    if a[0] or (a[1] + a[2]) < (b[1] + b[2]):
        print(doc, "KEPT v5", b[:3], "->", a[:3], "RELEASED" if a[0] else "", flush=True)
    else:
        pin(doc, prev); c = state(doc)
        if (c[1] + c[2]) > (a[1] + a[2]):
            pin(doc, "unreleased-v5"); print(doc, "v5 again", b[:3], a[:3], c[:3], flush=True)
        else:
            print(doc, "back to", prev, b[:3], "->", a[:3], "->", c[:3], flush=True)
