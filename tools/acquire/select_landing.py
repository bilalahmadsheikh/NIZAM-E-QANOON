"""select_landing.py STAGED.csv PREFLIGHT.csv SOURCE_ID OUT.jsonl [--excluded EXCLUDED.csv] : choose what to land.

Lead, 14 Nov 2026. The owner's rule for the territories (ICT, AJK, GB taken into scope that day): land only laws that
need no OCR and no held structural work -- "database should not have any held all released". A staged file is
selected only when ALL of these hold, and every file left out is written to --excluded with the rule that left it:

  grade      stage_candidates.py graded its text layer 'text'          (scans, Urdu and partial layers need OCR)
  verdict    preflight_segment.py predicted 'clean' or 'leaky'         ('blocked' would sit held; 'rejected' is unread)
  a law      not a compiled volume, index, judgment, report, challan, manual or policy (NOT_A_LAW / VOLUME below)
  its own    not a federal or other province's code the site reprints: on law.gok.pk /publications/ only titles naming
             Azad Jammu and Kashmir are AJK's own (the Pakistan Penal Code, CrPC, Qanun-e-Shahadat, Hudood Ordinances,
             Punjab PEEDA printed there are held from their own portals under their own jurisdiction)
  once       one row per file: a file listed on a page and again in the media library keeps the page row (its link
             text is the printed title; the media title is a file name)

The output is tools/recrawl/land_missing.py's input (one JSON object per line). Landing still refuses bytes the
corpus already holds, and every landed file still passes every release gate in the ordinary lane.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys

NOT_A_LAW = re.compile(r"(?i)challan|privacy breach|\bS\.?\s?C\.?\s?M\.?\s?R\b|\bPLD\b|^res\s+\d|\bmanual\b|"
                       r"judicial policy|tabular statement|\bindex\b")
VOLUME = re.compile(r"(?i)^\s*(final\s+)?vol(ume)?\.?\s*[ivxl\d]+\b|^vol\d|^act\s+\d{4}$")
KIND_ORDER = {"act": 0, "revised": 1, "ordinance": 2, "adopted": 3, "publication": 4, "regulation": 5, "media": 9}
ROMAN = re.compile(r"(?i)\(\s*(?:act|ordinance|regulation)\s+(?:no\.?\s*)?([ivxlcdm]+|\d+)\s+of\s+(\d{4})\s*\)")
YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def exclusion(r: dict, pf: dict | None) -> str | None:
    title = r["title"]
    if r.get("grade") != "text":
        return f"grade {r.get('grade') or r.get('status')}: needs OCR or did not download"
    if NOT_A_LAW.search(title):
        return "not a law (judgment, report, challan, manual, policy or index)"
    if VOLUME.search(title) or (r["kind"] == "media" and int(r.get("pages") or 0) >= 250):
        return "compiled code volume: its laws are listed one by one"
    if r["kind"] == "publication" and not re.search(r"(?i)azad\s+jammu", title):
        return "a federal or provincial code reprinted by the site: held from its own portal"
    if pf is None:
        return "not preflighted"
    if pf["verdict"] not in ("clean", "leaky"):
        why = pf.get("error") or f"s7 {pf.get('s7')} toc_pending {pf.get('toc_pending')} quality {pf.get('quality')} " \
                                 f"sections {pf.get('sections')}"
        return f"preflight {pf['verdict']}: {why}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("staged"); ap.add_argument("preflight"); ap.add_argument("source_id"); ap.add_argument("out")
    ap.add_argument("--excluded")
    a = ap.parse_args()
    if not re.fullmatch(r"pk-[a-z]+", a.source_id):
        ap.error("source_id reads pk-<name>")
    pf = {p["sha256"]: p for p in csv.DictReader(open(a.preflight, encoding="utf-8"))}
    rows = list(csv.DictReader(open(a.staged, encoding="utf-8")))
    rows.sort(key=lambda r: KIND_ORDER.get(r["kind"], 8))       # page rows before media rows of the same file
    seen, chosen, excluded = set(), [], []
    for r in rows:
        key = r.get("sha256") or r["pdf_url"]
        if key in seen:
            continue
        seen.add(key)
        why = exclusion(r, pf.get(r.get("sha256")))
        if why:
            excluded.append({"kind": r["kind"], "title": r["title"], "pages": r.get("pages"), "sha256": r.get("sha256"),
                             "pdf_url": r["pdf_url"], "why": why})
            continue
        m = ROMAN.search(r["title"])
        y = YEAR.findall(r["title"])
        chosen.append({"source_id": a.source_id, "title": r["title"], "year": int(y[-1]) if y else None,
                       "kind": r["kind"], "listing": f"{r['portal']}:{r['kind']}", "detail_url": r["detail_url"],
                       "pdf_url": r["pdf_url"], "number": m.group(1).upper() if m else None,
                       "staged_sha256": r["sha256"], "preflight": pf[r["sha256"]]["verdict"]})
    with open(a.out, "w", encoding="utf-8") as f:
        for c in chosen:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    if a.excluded:
        with open(a.excluded, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["kind", "title", "pages", "sha256", "pdf_url", "why"])
            w.writeheader(); w.writerows(excluded)
    from collections import Counter
    print(f"selected {len(chosen)} ({dict(Counter(c['preflight'] for c in chosen))}); excluded {len(excluded)}")
    for why, n in Counter(re.sub(r":.*", "", e["why"]) for e in excluded).most_common():
        print(f"  {n:5}  {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
