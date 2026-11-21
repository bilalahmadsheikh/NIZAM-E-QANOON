"""stage_drops.py OUT_DIR [--drops fbr_code,fbr_sro,secp,psx] : stage the September source drops for landing (no DB writes).

DECISION-LOG D-113 (21 Nov 2026, owner: "add data of these all as much as u can"). The drops in E:/nizam-data are zips
a scraper fetched from the regulators' own sites in September 2026, each with a manifest naming every file's official
URL. This writes, per drop, OUT_DIR/<drop>/files/<sha256>.pdf (its mtime set to the zip member's own time: the day
the scraper fetched it, which land_missing.py records as fetched_at) and OUT_DIR/<drop>/staged.csv in
stage_candidates.py's format plus a `drop` column (zip, member, scraper run, manifest row), ready for
preflight_segment.py -> select_landing.py -> land_missing.py --staged. Files left out are written to excluded.csv with
the rule that left them out:

  guidance     SECP circulars, guidelines and directives; every PSX file but the Rule Book: regulator guidance,
               notices, forms and policies, not legislation (docs/DEFERRED-SOURCES.md items 3-4)
  draft        a draft is not law
  held         the 19 Nov comparison (tools/evidence/source-drops-2026-11-19/drops-compare.csv) found the same file,
               or the same law in another file, already released; a "possible match" counts as held unless the
               title amends something (an amending instrument is a different instrument from the one it amends)
  version      an older dated consolidation of a law, or a second copy of one instrument in the drop: the newest
               is staged (whole-law snapshots as dated versions need a rule docs/03 does not have yet)
  not_pdf      a .docx or other non-PDF member
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import requests  # noqa: F401  (stage_candidates fetches with it; staging a drop fetches nothing)
except ImportError:
    import types
    sys.modules["requests"] = types.ModuleType("requests")
from stage_candidates import FIELDS, grade  # noqa: E402

DATA = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
COMPARE = Path(__file__).resolve().parents[2] / "tools/evidence/source-drops-2026-11-19/drops-compare.csv"

DROPS = {
    "fbr_code": dict(zip="fbr_code.zip", manifest="fbr_code/manifest.csv", path="filepath", url=("final_url", "url"),
                     group="subcategory", log="fbr_code/scraper.log"),
    "fbr_sro": dict(zip="judgments_peshawar_high_court.zip", manifest="fbr_sro_orders_code/manifest.csv",
                    path="filepath", url=("url",), group=None, log="fbr_sro_orders_code/scraper.log"),
    "secp": dict(zip="secp_code.zip", manifest="secp_code/manifest.csv", path="filepath", url=("url",), group=None,
                 log="secp_code/scraper.log"),
    "psx": dict(zip="psx_legal_framework.zip", manifest="psx_legal_framework/manifest.csv", path="saved_as",
                url=("url",), group=None, log=None),
    # GB_code.zip has no manifest. Its two text-layer laws were fetched live from the Government of Gilgit-Baltistan's
    # site on 21 Nov 2026 and are byte-identical to the zip members (sha256 9d60d032..., 3b4f9b0f...), so their
    # official URLs are known. Its other files are scans (OCR) or the federal PEC Act, held.
    "gb": dict(zip="GB_code.zip", manifest=None, path="filepath", url=("url",), group=None, log=None, rows=[
        {"category": "Acts", "title": "The Gilgit-Baltistan Civil Servants Act, 2011", "year": "2011",
         "filepath": "GB_code/Civil Servants Act 2011.pdf", "status": "success",
         "url": "https://gilgitbaltistan.gov.pk/storage/downloads/Civil%20Servants%20Act%202011.pdf"},
        {"category": "Order", "title": "The Government of Gilgit-Baltistan Order, 2018", "year": "2018",
         "filepath": "GB_code/GB Order 2018.pdf", "status": "success",
         "url": "https://gilgitbaltistan.gov.pk/storage/downloads/GB%20Order%202018.pdf"}]),
}
KIND = {"acts": "act", "order": "order", "ordinance": "ordinance", "ordinances": "ordinance", "rules": "rules",
        "regulations": "regulation", "notifications": "notification", "customs": "sro", "sros": "sro"}
GUIDANCE = {"circulars", "guidelines", "directives"}
PSX_RULE_BOOK = re.compile(r"^English Version \(Updated on")          # #12: the PSX Rule Book in force
DRAFT = re.compile(r"\bdraft\b", re.I)
# an amending instrument ('(Amendment) Act', 'Amendments in ... Regulations', 'amending'), never a consolidation's
# 'Amended upto 8th September, 2020' tail
AMENDS = re.compile(r"\bamendments?\b|\bamending\b|\bamends?\b", re.I)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"], 1)}


def as_of_key(title: str) -> tuple:
    """a sortable date from 'as amended up to 30th June, 2026', '30.06.2024', 'June 2025' or a bare year"""
    t = title.lower()
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?[\s.\-/]*([a-z]{3})[a-z]*[\s.,\-/]*(\d{4})", t)
    if m and m.group(2) in MONTHS:
        return int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", t)
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    m = re.search(r"\b([a-z]{3})[a-z]*[\s,]+(\d{4})", t)
    if m and m.group(1) in MONTHS:
        return int(m.group(2)), MONTHS[m.group(1)], 0
    y = re.findall(r"\b(19\d\d|20\d\d)\b", t)
    return (int(y[-1]), 0, 0) if y else (0, 0, 0)


def law_key(title: str) -> str:
    """one instrument's identity within a drop: the title without SRO numbers, dates, 'amended up to' tails, case"""
    t = title.lower()
    t = re.sub(r"\(?\s*(?:as\s+)?(?:amended|updated)\b.*$", "", t)
    t = re.sub(r"\bs\.?\s?r\.?\s?o\.?\s*(?:no\.?)?\s*[\d()i/\s\-.]+", " ", t)
    t = re.sub(r"\bdated\b.*$", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(w for w in t.split() if w not in {"the", "of", "and", "s", "no"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--drops", default=",".join(DROPS))
    a = ap.parse_args()
    verdict = {r["sha256"]: r for r in csv.DictReader(open(COMPARE, encoding="utf-8-sig"))}
    for name in a.drops.split(","):
        cfg = DROPS[name]
        out = a.out / name
        (out / "files").mkdir(parents=True, exist_ok=True)
        staged, excluded = [], []
        with zipfile.ZipFile(DATA / cfg["zip"]) as z:
            members = {n.replace("\\", "/"): n for n in z.namelist()}
            run = None
            if cfg["log"] and cfg["log"] in members:
                head = z.read(cfg["log"])[:200].decode("utf-8", "replace")
                run = head[:19] if re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", head) else None
            rows = cfg.get("rows") or list(csv.DictReader(io.TextIOWrapper(z.open(cfg["manifest"]), encoding="utf-8",
                                                                            errors="replace")))
            cands = []
            for r in rows:
                title = " ".join((r.get("title") or "").split())
                member = (r.get(cfg["path"]) or "").replace("\\", "/")
                url = next((r[k] for k in cfg["url"] if r.get(k)), "")
                # 'skipped' = the scraper found the file already fetched by an earlier run: it is in the zip too. A
                # long path was cut short in the manifest: the member it begins is the file (one match only)
                if r.get("status", "").lower() not in ("success", "ok", "skipped"):
                    continue
                if member not in members:
                    hits = [m for m in members if member and m.startswith(member) and not m.endswith("/")]
                    if len(hits) != 1:
                        continue
                    member = hits[0]
                cat = (r.get("category") or ("PSX" if name == "psx" else "")).strip()
                kind = KIND.get(cat.lower(), "regulation" if name == "psx" else cat.lower())
                why = None
                if not member.lower().endswith(".pdf"):
                    why = "not_pdf"
                elif cat.lower() in GUIDANCE or (name == "psx" and not PSX_RULE_BOOK.match(title)):
                    why = "guidance: regulator guidance, notices, forms or policies, not legislation"
                elif DRAFT.search(title):
                    why = "draft: a draft is not law"
                data = z.read(members[member]) if not why else b""
                sha = hashlib.sha256(data).hexdigest() if data else ""
                v = verdict.get(sha, {}).get("verdict", "")
                if not why and v in ("same file already held", "same law, different file"):
                    why = f"held: {v} ({verdict[sha].get('corpus_title', '')[:80]})"
                elif not why and v.startswith("possible") and not AMENDS.search(title):
                    why = f"held: possible match, not an amendment ({verdict[sha].get('corpus_title', '')[:80]})"
                if name == "psx" and not why:
                    title = f"PSX Rule Book ({title.split('(', 1)[-1].rstrip(')')})"
                info = z.getinfo(members[member])
                base = {"portal": name, "kind": kind, "year_or_dept": r.get("year") or r.get(cfg["group"] or "", ""),
                        "title": title, "detail_url": "", "pdf_url": url, "status": "staged", "sha256": sha,
                        "drop": json.dumps({"zip": cfg["zip"], "member": member, "scraper_run": run,
                                            "member_time": datetime(*info.date_time).isoformat(),
                                            "manifest": cfg["manifest"]}, ensure_ascii=False)}
                if why:
                    excluded.append({**base, "why": why})
                    continue
                cands.append((base, data, info, r))
            # the newest of each instrument; for FBR codes the manifest's subcategory names the law
            groups: dict = {}
            for base, data, info, r in cands:
                key = (r.get(cfg["group"]) if cfg["group"] else None) or law_key(base["title"])
                if name == "fbr_code" and AMENDS.search(base["title"]) or name in ("fbr_sro", "secp") and \
                        base["kind"] in ("notification", "sro"):
                    key = base["sha256"]         # each amending Act and each SRO is its own instrument
                groups.setdefault(key, []).append((base, data, info, r))
            for key, items in groups.items():
                items.sort(key=lambda x: (as_of_key(x[0]["title"]), x[0]["year_or_dept"] or ""), reverse=True)
                for base, data, info, r in items[1:]:
                    excluded.append({**base, "why": f"version: an older consolidation or second copy of "
                                                    f"'{items[0][0]['title'][:70]}'"})
                base, data, info, r = items[0]
                p = out / "files" / f"{base['sha256']}.pdf"
                if not p.exists():
                    p.write_bytes(data)
                t = datetime(*info.date_time).timestamp()
                os.utime(p, (t, t))
                g = grade(p)
                staged.append({**{k: base.get(k, "") for k in FIELDS}, **g, "bytes": len(data), "http_status": 200,
                               "content_type": "application/pdf", "drop": base["drop"]})
        with open(out / "staged.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS + ["drop"])
            w.writeheader(); w.writerows(staged)
        with open(out / "excluded.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["portal", "kind", "title", "sha256", "pdf_url", "why"],
                               extrasaction="ignore")
            w.writeheader(); w.writerows(excluded)
        from collections import Counter
        print(f"== {name}: staged {len(staged)} {dict(Counter(s['grade'] for s in staged))}; excluded {len(excluded)} "
              f"{dict(Counter(e['why'].split(':')[0] for e in excluded))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
