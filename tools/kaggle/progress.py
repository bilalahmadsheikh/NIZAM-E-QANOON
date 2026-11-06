"""progress.py : where the GPU OCR backlog stands (read-only).

Kaggle shows nothing of a running kernel -- no log, no output -- until the run ends, so progress is counted here, from
what came back and what was done with it:

  runs   : every pushed run (E:/nizam-data/ocr/kaggle/runs.tsv, written by kg.sh push) with its Kaggle status and age
  groups : per input group, the documents and pages queued, read (results fetched), imported (Surya candidates in the
           database) and released (the document, or the revision that replaced it, is in the release)

    bash tools/kaggle/kg.sh progress
"""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect  # noqa: E402

OCR = Path("/mnt/e/nizam-data/ocr")
OUT = OCR / "colab" / "output"
KG = OCR / "kaggle"
RUNS = KG / "runs.tsv"


def stems_by_group() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    man = json.loads((OCR / "colab" / "manifest.json").read_text())
    for g, items in man.items():
        groups[g] = [str(x) for x in items]
    for g, z in (("5-extra", KG / "ds-a" / "in-5-extra.zip"), ("6-c", KG / "ds-c" / "in-6-c.zip")):
        if z.exists():
            groups[g] = sorted(Path(n).stem for n in zipfile.ZipFile(z).namelist() if n.endswith(".pdf"))
    return groups


def kaggle_status(name: str) -> str:
    try:
        out = subprocess.run(["bash", "/mnt/e/Nizam_e_Qanoon/tools/kaggle/kg.sh", "status", name],
                             capture_output=True, text=True, timeout=60).stdout
        return out.strip().split('"')[-2].replace("KernelWorkerStatus.", "") if '"' in out else "?"
    except Exception:
        return "?"


def main() -> int:
    groups = stems_by_group()
    docs = {int(s.split("-")[0]) for ss in groups.values() for s in ss}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, page_count FROM document WHERE id = ANY(%s)", (sorted(docs),))
        pages = dict(cur.fetchall())
        cur.execute("""SELECT DISTINCT document_id, page_no FROM page_ocr_candidate
                        WHERE document_id = ANY(%s) AND engine LIKE 'surya%%'""", (sorted(docs),))
        cand = {}
        for d, p in cur.fetchall():
            cand.setdefault(d, set()).add(p)
        # released: the document or any later revision of it (supersedes chain) has a released instrument
        cur.execute("""WITH RECURSIVE chain(root, id) AS (
                           SELECT id, id FROM document WHERE id = ANY(%s)
                           UNION SELECT c.root, d.id FROM chain c JOIN document d ON d.supersedes_document_id = c.id)
                       SELECT DISTINCT c.root FROM chain c JOIN instrument i ON i.document_id = c.id
                         JOIN v_release_instrument r ON r.id = i.id""", (sorted(docs),))
        released = {r[0] for r in cur.fetchall()}

    now = datetime.now(timezone.utc)
    print("RUNS (Kaggle shows a run's results only when it ends)")
    if RUNS.exists():
        for line in RUNS.read_text().splitlines():
            name, grp, ds, pushed, hours = line.split("\t")
            age = (now - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).total_seconds() / 3600
            print(f"  {name:4} {kaggle_status(name):10} groups {grp:24} pushed {pushed}  {age:4.1f} h ago"
                  f"  (stops by {float(hours):.1f} h)")
    print()
    print(f"{'group':10} {'docs':>5} {'pages':>6} | {'read':>11} {'imported':>11} {'released':>11}")
    tot = [0, 0, 0, 0, 0, 0, 0]
    for g in sorted(groups):
        ss = groups[g]
        n = len(ss)
        pg = sum(1 if "-page" in s else (pages.get(int(s.split("-")[0])) or 0) for s in ss)
        read = [s for s in ss if (OUT / s / "results.json").exists()]
        imp = [s for s in ss if (int(s.split("-page")[1]) in cand.get(int(s.split("-")[0]), set())
                                  if "-page" in s else bool(cand.get(int(s.split("-")[0]))))]
        rel = [s for s in ss if int(s.split("-")[0]) in released]
        rd = {int(s.split("-")[0]) for s in rel}
        print(f"{g:10} {n:5} {pg:6} | {len(read):4} ({100 * len(read) / n:3.0f}%) {len(imp):4} ({100 * len(imp) / n:3.0f}%)"
              f" {len(rd):4} docs")
        for i, v in enumerate((n, pg, len(read), len(imp), len(rd))):
            tot[i] += v
    print(f"{'total':10} {tot[0]:5} {tot[1]:6} | {tot[2]:4} ({100 * tot[2] / tot[0]:3.0f}%) {tot[3]:4} "
          f"({100 * tot[3] / tot[0]:3.0f}%) {tot[4]:4} docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
