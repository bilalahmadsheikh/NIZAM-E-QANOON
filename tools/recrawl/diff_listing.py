"""Compare a portal listing with the catalogue (read-only). Lead, 20 Oct 2026.

    python tools/recrawl/diff_listing.py LISTING.jsonl OUT_MISSING.jsonl

Every listed item is classified:
  held:url    the exact URL is already an observation of that source (detail page = referring_url, or the PDF
              = canonical_url), whatever its outcome;
  held:title  the same law by folded title and year is already catalogued under another URL (a rotated federal
              link, a Gazette original of a law held in its codified Sindh Code form, an Assembly copy of a law held
              from the Balochistan Code). NOT re-landed: a second file of a held law would put it in the corpus
              twice;
  missing     neither -- written to OUT_MISSING for tools/recrawl/land_missing.py.
Titles fold case, punctuation, footnote markers, the article, 'Sind'->'Sindh', 'Bal'->'Balochistan', act numbers
('Act II of 2016') and, for provincial sources, the province's own name (portals print it inconsistently).
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nizam.storage.db import connect  # noqa: E402

PROVINCE_WORDS = {"pk-sindh": r"sindh", "pk-punjab": r"punjab", "pk-kp": r"khyber pakhtunkhwa|nwfp|n w f p|north west frontier province",
                  "pk-balochistan": r"balochistan|baluchistan"}


def url_key(u: str | None) -> str | None:
    if not u:
        return None
    u = unquote(u.strip()).lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")


def title_key(t: str | None, source_id: str) -> str:
    t = (t or "").split("\n")[0]                                       # held Sindh titles carry '\nSINDH ACT NO. ..'
    t = re.sub(r"\((?:codified|amendment-\d{4})\)", " ", t, flags=re.I)
    t = re.sub(r"\d{1,2}\[", "", t).replace("’", "'").replace("‘", "'").replace("_", "'").lower()
    t = re.sub(r"\bbaln\b\.?", "balochistan", t)
    t = re.sub(r"\.pdf$", "", t)
    t = re.sub(r"\b\d{1,2}(?=[a-z])", "", t)
    t = re.sub(r"\bsind\b", "sindh", t)
    t = re.sub(r"^\s*bal\b|\bbal\b(?=\s)", "balochistan", t)
    t = re.sub(r"\b(act|ordinance|regulations?|order|rules)\s+(no\.?\s*)?[ivxlcdm\d]+\s+of\s+(\d{4})", r"\1 \3", t)
    t = re.sub(r"\((?:act|ordinance)?\s*(no\.?\s*)?[ivxlcdm\d]+\s+of\s+\d{4}\)", " ", t)
    if source_id in PROVINCE_WORDS:
        t = re.sub(r"\b(" + PROVINCE_WORDS[source_id] + r")\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t.replace("'", ""))
    t = re.sub(r"\bthe\b", " ", t)
    return " ".join(t.split())


def year_of(t: str | None) -> int | None:
    ys = re.findall(r"\b(1[789]\d\d|20\d\d)\b", t or "")
    return int(ys[-1]) if ys else None


def main() -> int:
    listing = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
    if not listing:
        print("empty listing"); return 1
    source_id = next(i["source_id"] for i in listing if i["source_id"])
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT canonical_url, referring_url, source_metadata->>'title', source_metadata->>'archive_path',
                              coalesce(source_metadata->>'year', source_metadata->>'year_or_dept')
                         FROM source_observation WHERE source_id=%s""", (source_id,))
        rows = cur.fetchall()
        cur.execute("""SELECT i.short_title, i.year FROM instrument i JOIN source_observation o ON o.id=i.source_observation_id
                        WHERE o.source_id=%s AND i.is_active""", (source_id,))
        inst = cur.fetchall()
    urls = set()
    titles = collections.defaultdict(set)
    for can, ref, title, path, year in rows:
        urls.update(k for k in (url_key(can), url_key(ref)) if k)
        for t in (title, Path(path).name if path else None):
            if t:
                titles[title_key(t, source_id)].add(year_of(t) or (int(year) if (year or "").isdigit() else None))
    for t, y in inst:
        titles[title_key(t, source_id)].add(y or year_of(t))
    stats = collections.Counter()
    missing, probable = [], []
    by_year = collections.defaultdict(list)
    for key, years in titles.items():
        for yy in years:
            by_year[yy].append(key)

    def near_match(k, y, _titles):
        import difflib
        pool = by_year.get(y, []) if y is not None else []
        best = max(((difflib.SequenceMatcher(None, k, c).ratio(), c) for c in pool), default=(0, None))
        return best[1] if best[0] >= 0.9 else None
    for it in listing:
        if not it.get("title") and not it.get("pdf_url"):
            stats["unlisted/error"] += 1; continue
        if url_key(it.get("detail_url")) in urls or url_key(it.get("pdf_url")) in urls:
            stats["held:url"] += 1; continue
        k, y = title_key(it.get("title"), source_id), year_of(it.get("title")) or it.get("year")
        if k in titles and (y is None or y in titles[k] or None in titles[k]):
            stats["held:title"] += 1; continue
        near = near_match(k, y, titles)
        if near:
            stats["held:probable (near title, same year; listed for review, not landed)"] += 1
            probable.append({**it, "near": near}); continue
        if source_id == "pk-sindh" and it["listing"] == "sindhlaws:gazette" and not it.get("pdf_url"):
            stats["no pdf"] += 1; continue
        if source_id == "pk-sindh" and it["listing"] == "sindhlaws:code" and not it.get("pdf_url"):
            stats["missing but no English PDF listed"] += 1; continue
        stats["missing"] += 1
        missing.append(it)
    # one entry per law: the same law listed twice (codified and Gazette, or Code and Assembly) is landed once
    seen, unique = set(), []
    for it in sorted(missing, key=lambda i: (i["listing"] != "sindhlaws:code", i["listing"] == "pabalochistan:acts")):
        k = (title_key(it.get("title"), source_id), year_of(it.get("title")) or it.get("year"))
        if k in seen:
            stats["missing (second listing of one law)"] += 1; continue
        seen.add(k); unique.append(it)
    stats["missing unique"] = len(unique)
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        for it in unique:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    with open(sys.argv[2].replace("missing-", "probable-"), "w", encoding="utf-8") as fh:
        for it in probable:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    by = collections.Counter((it["listing"], it.get("kind")) for it in unique)
    print(source_id, json.dumps(stats))
    for (l, k), n in by.most_common():
        print(f"   {n:5d}  {l}  {k}")
    recent = sorted((it for it in unique if (it.get("year") or 0) >= 2024), key=lambda i: -(i.get("year") or 0))
    for it in recent[:25]:
        print("   NEW", it.get("year"), it.get("kind"), (it.get("title") or "")[:90])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
