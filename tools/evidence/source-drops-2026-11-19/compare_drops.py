"""Compare the 16 Nov source drops in /mnt/e/nizam-data against the corpus: exact bytes held, same law in a different
file, or new. Read-only: zips are streamed for hashing only; nothing is extracted or executed."""
import base64
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect  # noqa: E402

D = Path("/mnt/e/nizam-data")
OUT = Path(sys.argv[1])
STOP = {"the", "of", "a", "an", "and", "for", "in", "on", "to", "pdf", "docx"}
CUT = re.compile(r"\b(as amended|amended up ?to|updated|as on|as of|upto|up to)\b.*$", re.I)


def norm(t):
    t = (t or "").lower().replace("&", " and ").replace("–", " ").replace("—", " ")
    t = CUT.sub("", t)
    years = set(int(y) for y in re.findall(r"\b(1[89]\d\d|20[0-2]\d)\b", t))
    toks = {w for w in re.findall(r"[a-z0-9]+", t) if w not in STOP and not re.fullmatch(r"\d{4}", w)}
    return toks, years


def gb_title(name):
    m = re.search(r"meta([A-Za-z0-9+/=_-]+?)-?(?: \(\d\))?\.pdf$", name)
    if not m:
        return name
    s = m.group(1)
    try:
        return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")
    except Exception:
        return name


def entries():
    """yield (source, zip path, member, title, category, extra)"""
    man = {}
    with zipfile.ZipFile(D / "fbr_code.zip") as z:
        for r in csv.DictReader(io.TextIOWrapper(z.open("fbr_code/manifest.csv"), "utf-8-sig")):
            man[r["filepath"].replace("\\", "/")] = r
        for n in z.namelist():
            if n.lower().endswith((".pdf", ".docx")):
                r = man.get(n, {})
                sub = r.get("subcategory") or Path(n).parent.name
                if sub.lower() in ("acts", "ordinance", "ordinances", "rules", "finance acts", "fbr_code"):
                    sub = r.get("title") or Path(n).stem           # generic folder: the file's own title names the law
                yield "FBR codes", "fbr_code.zip", n, sub, r.get("category", n.split("/")[1]), r.get("title") or Path(n).stem
    man = {}
    with zipfile.ZipFile(D / "secp_code.zip") as z:
        for r in csv.DictReader(io.TextIOWrapper(z.open("secp_code/manifest.csv"), "utf-8-sig")):
            man[r["filepath"].replace("\\", "/")] = r
        for n in z.namelist():
            if n.lower().endswith((".pdf", ".docx")):
                r = man.get(n, {})
                yield "SECP", "secp_code.zip", n, r.get("title") or Path(n).stem, n.split("/")[1], r.get("date", "")
    man = {}
    with zipfile.ZipFile(D / "psx_legal_framework.zip") as z:
        for r in csv.DictReader(io.TextIOWrapper(z.open("psx_legal_framework/manifest.csv"), "utf-8-sig")):
            man[r["saved_as"].replace("\\", "/")] = r
        for n in z.namelist():
            if n.lower().endswith((".pdf", ".docx", ".xlsx", ".zip")) and not n.endswith("/"):
                r = man.get(n, {})
                cat = "rule book archive" if "/rule_book_archive/" in n else "PSX document"
                yield "PSX", "psx_legal_framework.zip", n, r.get("title") or re.sub(r"^\d+ - ", "", Path(n).stem), cat, ""
    with zipfile.ZipFile(D / "fbr_Customs.zip") as z:
        for n in z.namelist():
            if n.lower().endswith(".pdf"):
                yield "FBR Customs SROs", "fbr_Customs.zip", n, Path(n).stem, "Customs SRO/notification", ""
    with zipfile.ZipFile(D / "judgments_peshawar_high_court.zip") as z:
        for n in z.namelist():
            if n.startswith("fbr_sro_orders_code/SROs/") and n.lower().endswith(".pdf"):
                yield "FBR SRO folder (bundle only)", "judgments_peshawar_high_court.zip", n, Path(n).stem, "Customs SRO/notification", ""
    with zipfile.ZipFile(D / "GB_code.zip") as z:
        for n in z.namelist():
            if n.lower().endswith(".pdf"):
                t = gb_title(Path(n).name)
                t = re.sub(r"^\d{4}-\d\d-\d\d \d\d_\d\d_\d\d", "", t).replace("-", " ").replace(".pdf", "")
                yield "GB code (Sep)", "GB_code.zip", n, t, "GB law", ""


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT sha256 FROM blob")
        blobs = {r[0].strip() for r in cur.fetchall()}
        cur.execute("""SELECT i.id::text, coalesce(i.display_title, i.short_title), i.short_title, i.year, i.kind::text,
                              i.jurisdiction::text, s.currency, o.fetched_at::date, i.source_sha256, i.source_url
                       FROM v_release_instrument i LEFT JOIN mv_instrument_serving s ON s.instrument_id = i.id
                       LEFT JOIN source_observation o ON o.id = i.source_observation_id""")
        corpus = cur.fetchall()
        cur.execute("""SELECT i.source_sha256, coalesce(i.display_title, i.short_title) FROM instrument i WHERE i.is_active""")
        by_sha = defaultdict(list)
        for sha, t in cur.fetchall():
            if sha:
                by_sha[sha.strip()].append(t)
    idx = defaultdict(list)
    for row in corpus:
        for t in {row[1], row[2]}:
            toks, years = norm(t)
            ys = years or ({row[3]} if row[3] else set())
            for y in ys or {None}:
                idx[y].append((toks, row))
    rows = []
    zips = {}
    for src, zname, member, title, cat, extra in entries():
        z = zips.get(zname) or zips.setdefault(zname, zipfile.ZipFile(D / zname))
        h = hashlib.sha256()
        with z.open(member) as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        sha = h.hexdigest()
        toks, years = norm(title)
        best, bscore = None, 0.0
        cands = [c for y in years for c in idx.get(y, [])] if years else [c for v in idx.values() for c in v]
        want_j = "gb" if src.startswith("GB") else "fed"      # FBR, SECP, PSX and Customs issue federal law only
        for ctoks, row in cands:
            if not toks or not ctoks or row[5] != want_j:
                continue
            inter = len(toks & ctoks)
            score = inter / len(toks | ctoks)
            if ctoks <= toks or toks <= ctoks:
                score = max(score, inter / max(len(ctoks), len(toks)) + 0.15)
            if score > bscore:
                best, bscore = row, score
        if sha in blobs:
            verdict = "same file already held"
        elif best and bscore >= 0.8 and (not years or best[3] in years):
            verdict = "same law, different file"
        elif best and bscore >= 0.6:
            verdict = "possible match (check)"
        else:
            verdict = "new"
        rows.append({"source": src, "category": cat, "title": title, "version_or_date": extra, "member": member,
                     "sha256": sha, "verdict": verdict, "match_score": round(bscore, 2),
                     "corpus_title": best[1] if best and bscore >= 0.6 else "",
                     "corpus_year": best[3] if best and bscore >= 0.6 else "",
                     "corpus_jurisdiction": best[5] if best and bscore >= 0.6 else "",
                     "corpus_currency": best[6] if best and bscore >= 0.6 else "",
                     "corpus_captured": str(best[7]) if best and bscore >= 0.6 and best[7] else "",
                     "corpus_source_url": best[9] if best and bscore >= 0.6 else "",
                     "held_as": "; ".join(by_sha.get(sha, []))})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    shas = defaultdict(set)
    for r in rows:
        shas[r["source"]].add(r["sha256"])
    summary = {}
    for s in dict.fromkeys(r["source"] for r in rows):
        rs = [r for r in rows if r["source"] == s]
        summary[s] = {"files": len(rs), "distinct_files": len(shas[s]),
                      "verdicts": Counter(r["verdict"] for r in rs),
                      "by_category": {c: dict(Counter(r["verdict"] for r in rs if r["category"] == c))
                                      for c in sorted({r["category"] for r in rs})}}
    summary["sro_folder_vs_customs_zip_same_bytes"] = len(shas["FBR SRO folder (bundle only)"] & shas["FBR Customs SROs"])
    print(json.dumps(summary, indent=1, default=dict))


if __name__ == "__main__":
    main()
