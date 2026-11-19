"""The law register: every released law, one row each, with what the database knows about it (docs/law-register/).

    .venv/bin/python tools/law_register.py [--out docs/law-register]

Writes, from the database as it stands (nothing is re-derived here; every column is read from a view):
  laws.csv          one row per law in v_release_instrument (the release boundary), UTF-8 with BOM so Excel shows Urdu
  <place>.md        the same laws as readable tables, one file per jurisdiction
  README.md         counts, the column meanings, and how to regenerate

It replaces, for reading, the 11 Nov names table (.artifacts/instrument-names-2026-11-11/instrument-names.csv, 8,851
laws). That file is left untouched: it is the evidence tools/record_display_titles.py recorded display titles from.

Sources, all read-only:
  v_release_instrument            the released laws (10,342 on 19 Nov 2026)
  mv_instrument_serving           currency, reason, reach, territory exits, superseded-by (10,291: the laws served
                                  directly; the 51 as-made Gazette texts are served through their consolidated twin)
  v_consolidated_twin_current     which consolidated text serves an as-made one (0075)
  v_instrument_metadata_current   the basis recorded for title, status, enacted and commenced dates (0070)
  v_release_provision             provisions per law; v_release_page pages per source document
  mv_provision_text_known_from    the earliest date the held text is known to be the law (0096-0099)
  mv_provision_repeal             units repealed by a later law (0102)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.storage.db import connect  # noqa: E402

PLACES = [("fed", "Federal (incl. Islamabad Capital Territory)", "federal"),
          ("punjab", "Punjab", "punjab"), ("sindh", "Sindh", "sindh"), ("kp", "Khyber Pakhtunkhwa", "khyber-pakhtunkhwa"),
          ("balochistan", "Balochistan", "balochistan"), ("ajk", "Azad Jammu & Kashmir", "azad-jammu-kashmir"),
          ("gb", "Gilgit-Baltistan", "gilgit-baltistan")]

SQL = """
WITH meta AS (
  SELECT DISTINCT ON (instrument_id, field) instrument_id, field, basis
  FROM v_instrument_metadata_current
  WHERE field IN ('display_title', 'status', 'enacted_on', 'commenced_on') AND instrument_id IS NOT NULL
  ORDER BY instrument_id, field, recorded_at DESC, id DESC),
prov AS (SELECT instrument_id, count(*) AS n FROM v_release_provision GROUP BY 1),
pages AS (SELECT document_id, count(*) AS n FROM v_release_page GROUP BY 1),
known AS (SELECT instrument_id, min(text_known_from) AS d FROM mv_provision_text_known_from GROUP BY 1),
rep AS (SELECT instrument_id, count(DISTINCT provision_id) AS n FROM mv_provision_repeal GROUP BY 1),
twin AS (SELECT DISTINCT ON (as_made_instrument_id) as_made_instrument_id, consolidated_instrument_id
         FROM v_consolidated_twin_current ORDER BY as_made_instrument_id, recorded_at DESC)
SELECT r.id::text, r.jurisdiction::text, r.kind::text, r.number, r.year,
       coalesce(r.display_title, r.short_title) AS title, r.short_title, r.long_title,
       mt.basis AS title_basis, r.text_language,
       r.status::text, ms.basis AS status_basis,
       r.enacted_on, me.basis AS enacted_basis, r.commenced_on, mc.basis AS commenced_basis,
       r.repealed_on, coalesce(rb.display_title, rb.short_title) AS repealed_by,
       coalesce(s.currency, st.currency) AS currency, coalesce(s.currency_reason, st.currency_reason) AS currency_reason,
       coalesce(s.not_current_from, st.not_current_from) AS not_current_from,
       array_to_string(coalesce(s.territory_reach, st.territory_reach), ',') AS territory_reach,
       coalesce(s.extent_basis, st.extent_basis) AS extent_basis,
       coalesce(s.territory_exits, st.territory_exits)::text AS territory_exits,
       coalesce(sb.display_title, sb.short_title) AS superseded_by,
       CASE WHEN s.instrument_id IS NOT NULL THEN 'direct'
            WHEN t.consolidated_instrument_id IS NOT NULL THEN 'via_consolidated_twin' ELSE 'not_served' END AS served,
       coalesce(ct.display_title, ct.short_title) AS served_through,
       k.d AS text_known_from, coalesce(p.n, 0) AS provisions, coalesce(rp.n, 0) AS units_repealed,
       r.document_id, coalesce(pg.n, 0) AS document_pages, r.expression_ordinal, r.source_url, r.source_sha256
FROM v_release_instrument r
LEFT JOIN mv_instrument_serving s ON s.instrument_id = r.id
LEFT JOIN twin t ON t.as_made_instrument_id = r.id
LEFT JOIN mv_instrument_serving st ON s.instrument_id IS NULL AND st.instrument_id = t.consolidated_instrument_id
LEFT JOIN instrument ct ON ct.id = t.consolidated_instrument_id AND s.instrument_id IS NULL
LEFT JOIN instrument rb ON rb.id = r.repealed_by_id
LEFT JOIN instrument sb ON sb.id = s.superseded_by_instrument_id
LEFT JOIN meta mt ON mt.instrument_id = r.id AND mt.field = 'display_title'
LEFT JOIN meta ms ON ms.instrument_id = r.id AND ms.field = 'status'
LEFT JOIN meta me ON me.instrument_id = r.id AND me.field = 'enacted_on'
LEFT JOIN meta mc ON mc.instrument_id = r.id AND mc.field = 'commenced_on'
LEFT JOIN prov p ON p.instrument_id = r.id
LEFT JOIN pages pg ON pg.document_id = r.document_id
LEFT JOIN known k ON k.instrument_id = coalesce(s.instrument_id, t.consolidated_instrument_id)
LEFT JOIN rep rp ON rp.instrument_id = r.id
"""

COLUMNS = [
    ("instrument_id", "the law's identity in the corpus (changes when the law is re-segmented)"),
    ("jurisdiction", "fed (federal and ICT) · punjab · sindh · kp · balochistan · ajk · gb"),
    ("kind", "constitution · act · ordinance · order · regulation · rules · sro · notification"),
    ("number", "the instrument's number as printed (Act No. …), where read"),
    ("year", "the year, corrected from the law's own text where the catalogue was wrong (0101)"),
    ("title", "the name rendered to a reader: display_title, else the catalogue short title (INV-1)"),
    ("catalogue_title", "the short title as the source catalogue gave it (never changed: identity keys on it)"),
    ("long_title", "the printed long title, where read"),
    ("title_basis", "the evidence for the title (verified_in_printed_text, near_match_in_printed_text, "
                    "verified_by_short_title_clause, reviewed_printed_name, reviewed_corrected_name, "
                    "printed_short_title_clause); empty = catalogue title"),
    ("text_language", "en · ur · sd, measured from the released text"),
    ("status", "lifecycle status: in_force · repealed · spent · lapsed · not_yet_commenced"),
    ("status_basis", "why that status (e.g. commenced_on_established, statutory_repeal_stands, "
                     "owner_presumption_in_force)"),
    ("enacted_on, enacted_basis", "assent / promulgation / notification date, and where on the page it was read"),
    ("commenced_on, commenced_basis", "commencement date, and its basis"),
    ("repealed_on, repealed_by", "whole-law repeal date and the repealing law"),
    ("currency", "what is served today: current · not_current (repealed, lapsed, replaced, superseded) · historical "
                 "(pre-1947 archive texts, places outside Pakistan)"),
    ("currency_reason, not_current_from", "the reason, and the date the law stopped being served"),
    ("territory_reach", "where the law runs (from its extent clause or its title)"),
    ("extent_basis", "extent_clause or the title reading"),
    ("territory_exits", "territories a later law repealed it in, with dates (JSON)"),
    ("superseded_by", "a later law of the same name that replaced it"),
    ("served", "direct · via_consolidated_twin (an as-made Gazette text served through its consolidated text)"),
    ("served_through", "the consolidated text that serves an as-made one"),
    ("text_known_from", "the earliest date the held text is known to be the law; before it, questions abstain"),
    ("provisions", "released provisions (every section, sub-section, clause, schedule item)"),
    ("units_repealed", "provisions repealed by a later law while the rest of the law stands (0102)"),
    ("document_id, document_pages", "the source document and its released page count"),
    ("expression_ordinal", "which law inside that document (a PDF can hold several)"),
    ("source_url, source_sha256", "where the text came from, and the fingerprint of the bytes"),
]

CSV_HEADER = ["instrument_id", "jurisdiction", "kind", "number", "year", "title", "catalogue_title", "long_title",
              "title_basis", "text_language", "status", "status_basis", "enacted_on", "enacted_basis",
              "commenced_on", "commenced_basis", "repealed_on", "repealed_by", "currency", "currency_reason",
              "not_current_from", "territory_reach", "extent_basis", "territory_exits", "superseded_by", "served",
              "served_through", "text_known_from", "provisions", "units_repealed", "document_id",
              "document_pages", "expression_ordinal", "source_url", "source_sha256"]

ORDER = {p[0]: i for i, p in enumerate(PLACES)}


def cell(v):
    if v is None:
        return ""
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def md(v):
    return " ".join(cell(v).split()).replace("|", "\\|")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs/law-register"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = [dict(zip(CSV_HEADER, r)) for r in cur.fetchall()]
    rows.sort(key=lambda r: (ORDER.get(r["jurisdiction"], 99), r["year"] or 0, (r["title"] or "").lower(),
                             r["instrument_id"]))
    if len({r["instrument_id"] for r in rows}) != len(rows):
        raise SystemExit("a law appears twice: the joins are not one row per law")
    unserved = [r for r in rows if r["served"] == "not_served"]
    if unserved:
        raise SystemExit(f"{len(unserved)} released laws have no serving row: refresh_serving first")

    with open(out / "laws.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow([cell(r[c]) for c in CSV_HEADER])

    stamp = date.today().isoformat()
    by_place = defaultdict(list)
    for r in rows:
        by_place[r["jurisdiction"]].append(r)
    for key, label, slug in PLACES:
        rs = by_place.get(key, [])
        cur_n = Counter(r["currency"] for r in rs)
        lines = [f"# {label}: {len(rs):,} laws", "",
                 f"Generated {stamp} by `tools/law_register.py` from the database; do not edit by hand. "
                 f"{cur_n['current']:,} current, {cur_n['not_current']:,} not current, "
                 f"{cur_n['historical']:,} historical. Every column, and more, is in [laws.csv](laws.csv); "
                 f"the column meanings are in [README.md](README.md).", "",
                 "| # | Title | Kind | No. | Year | Currency | Enacted | Commenced | Provisions | Lang |",
                 "|---:|---|---|---|---:|---|---|---|---:|---|"]
        for i, r in enumerate(rs, 1):
            currency = r["currency"] + (f" from {cell(r['not_current_from'])}" if r["not_current_from"] else "")
            if r["served"] == "via_consolidated_twin":
                currency += " (as made; served via its consolidated text)"
            lines.append(f"| {i} | {md(r['title'])} | {r['kind']} | {md(r['number'])} | {cell(r['year'])} | "
                         f"{md(currency)} | {cell(r['enacted_on'])} | {cell(r['commenced_on'])} | "
                         f"{r['provisions']:,} | {r['text_language'] or ''} |")
        (out / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = readme_text(rows, stamp)
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"laws": len(rows), "out": str(out),
                      "currency": Counter(r["currency"] for r in rows)}, indent=1, default=str))
    return 0


def readme_text(rows, stamp):
    tot = Counter(r["currency"] for r in rows)
    lines = ["# The law register", "",
             f"Every law released in the corpus, **{len(rows):,} laws**, generated {stamp} by "
             "`tools/law_register.py` from the database. Do not edit these files by hand: change the database "
             "(through its recorders and migrations) and regenerate.", "",
             "- [laws.csv](laws.csv): every law, every column below (UTF-8 with BOM; opens in Excel with Urdu intact)",
             *[f"- [{label}]({slug}.md)" for _k, label, slug in PLACES], "",
             "## By place and currency", "",
             "| Place | Laws | Current | Not current | Historical | Provisions | Urdu/Sindhi text |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for key, label, _slug in PLACES:
        rs = [r for r in rows if r["jurisdiction"] == key]
        c = Counter(r["currency"] for r in rs)
        lines.append(f"| {label} | {len(rs):,} | {c['current']:,} | {c['not_current']:,} | {c['historical']:,} | "
                     f"{sum(r['provisions'] for r in rs):,} | "
                     f"{sum(1 for r in rs if r['text_language'] in ('ur', 'sd')):,} |")
    lines.append(f"| **All** | **{len(rows):,}** | **{tot['current']:,}** | **{tot['not_current']:,}** | "
                 f"**{tot['historical']:,}** | **{sum(r['provisions'] for r in rows):,}** | "
                 f"**{sum(1 for r in rows if r['text_language'] in ('ur', 'sd')):,}** |")
    twins = sum(1 for r in rows if r["served"] == "via_consolidated_twin")
    lines += ["", f"Currency counts every released law. {twins} of them are as-made Gazette texts served through "
              "their consolidated twin and carry the twin's currency, so the laws served directly are "
              f"{len(rows) - twins:,}.", "", "## By kind", "", "| Kind | Laws |", "|---|---:|"]
    for k, n in Counter(r["kind"] for r in rows).most_common():
        lines.append(f"| {k} | {n:,} |")
    lines += ["", "## By decade of the law", "", "| Decade | Laws |", "|---|---:|"]
    dec = Counter((f"{r['year'] // 10 * 10}s" if r["year"] else "undated") for r in rows)
    for d in sorted(dec):
        lines.append(f"| {d} | {dec[d]:,} |")
    lines += ["", "## Why laws are not current", "", "| Reason | Laws |", "|---|---:|"]
    for k, n in Counter(r["currency_reason"] for r in rows if r["currency"] != "current").most_common():
        lines.append(f"| {k} | {n:,} |")
    lines += ["", "## Where each title comes from", "", "| Title basis | Laws |", "|---|---:|"]
    for k, n in Counter(r["title_basis"] or "catalogue title (no assertion)" for r in rows).most_common():
        lines.append(f"| {k} | {n:,} |")
    lines += ["", "## Columns of laws.csv", "", "| Column | Meaning |", "|---|---|"]
    lines += [f"| `{c}` | {m} |" for c, m in COLUMNS]
    lines += ["", "## Limits", "",
              "- `current` includes laws presumed in force by owner decision (16 Nov 2026) where no text proved "
              "their status; `status_basis = owner_presumption_in_force` marks them. The presumption never covers a "
              "pre-1947 archive text.",
              "- Titles marked `verified_in_printed_text` were matched against the law's printed pages by machine, "
              "not read by a person; the `reviewed_*` bases were.",
              "- `instrument_id` changes when a law is re-segmented; cite a law by its title, number and year.",
              "- Laws that need OCR (874 AJK and 151 GB scans) are not landed and are not in this register "
              "(owner rule); see docs/CORPUS-STATE-2026-11-17.md.",
              "", "Regenerate: `.venv/bin/python tools/law_register.py` (WSL), after any release or recorder run."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
