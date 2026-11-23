"""The register of everything not added: laws and judgments, each with why and what it needs (D-130).

    python tools/pending_register.py [--out docs]

Writes, never edited by hand:
  docs/pending/laws.csv        every law-side item not released, from the database and the staging lists on disk
  docs/pending/judgments.csv   every judgment file not released, per court, and released judgments with no date
  docs/PENDING-REGISTER.md     counts by area, category and what each needs

Law-side sources:
  - acquisition exceptions (v_acquisition_exception_latest): catalogued, never fetched;
  - open incompleteness (v_source_incompleteness_open): a partial copy with no complete one;
  - the staging lists on disk (territories-2026-11-14/excluded-ajk.csv, drops-2026-11-21/<drop>/*excluded*.csv):
    scans, texts blocked at structuring, and items set aside by rule. A row whose file has since landed (its sha256
    is a landed source observation) is dropped, so the register never lists what is already in the corpus;
  - set aside as not law (v_source_not_law_current).
Judgment-side: judgment_document readings that are not 'parsed' (needs_ocr, held, reporter_reprint), per court;
released judgments marked undated (D-124); and the sources not yet acquired (the Sindh recrawl, courts not held).
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nizam.storage.db import connect  # noqa: E402

ACQ = Path("/mnt/e/nizam-data/acquire")
STAGING = [("ajk", ACQ / "territories-2026-11-14" / "excluded-ajk.csv")] + [
    (drop, ACQ / "drops-2026-11-21" / drop / name)
    for drop in ("fbr_code", "fbr_sro", "secp", "psx", "gb")
    for name in ("excluded.csv", "select-excluded.csv", "select-nu-excluded.csv")]

FIELDS = ["area", "category", "needs", "source", "kind", "title", "file", "sha256", "url", "reason"]


def law_need(why: str) -> tuple[str, str]:
    """(category, what it needs) for a staging list's 'why'."""
    w = why.lower()
    if "needs ocr" in w or "grade scan" in w or "grade urdu" in w or "grade partial" in w:
        return "scan", "OCR (D-114: Document AI + Tesseract, page agreement)"
    if "did not download" in w or "grade error" in w:
        return "not downloaded", "fetch again"
    if w.startswith("preflight blocked") or "evidence" in w or "s7" in w:
        return "text, not structurable yet", "a per-document reading (repeated labels, contents, mastheads)"
    if w.startswith("held"):
        return "set aside: already held", "nothing (or the newer-consolidation rule for dated versions)"
    if "draft" in w:
        return "set aside: draft", "nothing (a draft is not law)"
    if "not a law" in w or "guidance" in w or "notice" in w or "form" in w or "policy" in w or "press" in w:
        return "set aside: not law", "nothing"
    if ("reprinted" in w or "compiled code" in w or "older copy" in w or "docx" in w or w.startswith("version:")
            or "older consolidation" in w):
        return "set aside: a copy or compilation", "nothing (or the newer-consolidation rule for dated versions)"
    if w.startswith("not_pdf"):
        return "not a PDF", "open the file (a .docx or web page) and read it by hand"
    return "other", "read the reason"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs"))
    a = ap.parse_args()
    out = Path(a.out)
    (out / "pending").mkdir(parents=True, exist_ok=True)
    laws: list[dict] = []
    judgments: list[dict] = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT sha256 FROM source_observation WHERE outcome = 'landed' AND sha256 IS NOT NULL")
        landed = {r[0] for r in cur.fetchall()}
        cur.execute("""SELECT o.source_id, e.evidence->>'title', o.canonical_url, e.reason, e.observed_error
                         FROM v_acquisition_exception_latest e JOIN source_observation o ON o.id = e.source_observation_id
                        ORDER BY 1, 2""")
        for src, title, url, reason, err in cur.fetchall():
            laws.append(dict(area="law", category="not acquired", needs="find another source, or retry the portal",
                             source=src, kind="", title=title or "", file="", sha256="", url=url or "",
                             reason=f"{reason}: {err or ''}"))
        cur.execute("""SELECT source_id, title, canonical_url, resolution, body_stops_at, promised_top
                         FROM v_source_incompleteness_open ORDER BY 1, 2""")
        for src, title, url, res, stops, top in cur.fetchall():
            laws.append(dict(area="law", category="partial copy", needs="a complete copy of the law",
                             source=src, kind="", title=title or "", file="", sha256="", url=url or "",
                             reason=f"{res}: body stops at {stops}, contents promise {top}"))
        cur.execute("""SELECT o.source_id, coalesce(o.source_metadata->>'title', ''), o.canonical_url,
                              n.kind || ': ' || coalesce(left(n.quote, 120), '')
                         FROM v_source_not_law_current n JOIN source_observation o ON o.id = n.source_observation_id""")
        for src, title, url, reason in cur.fetchall():
            laws.append(dict(area="law", category="set aside: not law", needs="nothing", source=src, kind="",
                             title=title, file="", sha256="", url=url or "", reason=reason or ""))
        seen = set()
        for source, path in STAGING:
            if not path.exists():
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for r in csv.DictReader(f):
                    sha = (r.get("sha256") or "").strip()
                    key = (source, sha or r.get("pdf_url"), r.get("title"))
                    if key in seen or (sha and sha in landed):
                        continue
                    seen.add(key)
                    cat, needs = law_need(r.get("why") or "")
                    laws.append(dict(area="law", category=cat, needs=needs, source=r.get("portal") or source,
                                     kind=r.get("kind") or "", title=r.get("title") or "", file=path.name,
                                     sha256=sha, url=r.get("pdf_url") or "", reason=r.get("why") or ""))

        cur.execute("""SELECT d.court_code, d.outcome, coalesce(d.hold_reason, ''), s.archive, s.member, d.sha256
                         FROM judgment_document d
                         JOIN LATERAL (SELECT archive, member FROM judgment_source x WHERE x.sha256 = d.sha256
                                        ORDER BY x.id LIMIT 1) s ON true
                        WHERE d.is_active AND d.outcome IN ('needs_ocr', 'held', 'reporter_reprint')
                        ORDER BY 1, 2, 5""")
        need_of = {"needs_ocr": ("scan", "OCR (D-114)"),
                   "held": ("held by a gate", "a parser rule or a person's reading (see reason)"),
                   "reporter_reprint": ("law-report reprint", "the court's own copy (portal recrawl); D-120")}
        for court, outcome, reason, archive, member, sha in cur.fetchall():
            cat, needs = need_of[outcome]
            judgments.append(dict(area="judgment", category=cat, needs=needs, source=court, kind=outcome,
                                  title=member.split("/")[-1], file=f"{archive}:{member}", sha256=sha, url="",
                                  reason=reason))
        cur.execute("""SELECT j.court_code, j.case_no_printed, s.archive, s.member, j.undated_reason, d.sha256
                         FROM v_release_judgment j JOIN judgment_document d ON d.id = j.document_id
                         JOIN LATERAL (SELECT archive, member FROM judgment_source x WHERE x.sha256 = d.sha256
                                        ORDER BY x.id LIMIT 1) s ON true
                        WHERE j.decided_on_basis = 'undated' ORDER BY 1, 4""")
        for court, case, archive, member, why, sha in cur.fetchall():
            judgments.append(dict(area="judgment", category="released, date not printed",
                                  needs="the court's decision date (portal recrawl with metadata)", source=court,
                                  kind="undated", title=case[:200], file=f"{archive}:{member}", sha256=sha, url="",
                                  reason=why or ""))
        # released before gate J9 (D-130) whose text layer falls below it: kept released, listed for an OCR re-read
        from nizam.corpus.judgment import PLAUSIBLE_MIN, plausibility
        cur.execute("""SELECT j.id, j.court_code, j.case_no_printed, string_agg(p.text, ' ' ORDER BY p.ordinal)
                         FROM v_release_judgment j
                         JOIN judgment_paragraph p ON p.judgment_id = j.id AND p.decided_on = j.decided_on
                        WHERE p.kind IN ('header', 'body', 'closing')
                        GROUP BY 1, 2, 3""")
        for jid, court, case, text in cur.fetchall():
            score, counted = plausibility(text or "")
            if score is not None and score < PLAUSIBLE_MIN:
                judgments.append(dict(area="judgment", category="released, text layer below J9",
                                      needs="an OCR re-read (D-114); released before the gate", source=court,
                                      kind="released", title=case[:200], file=str(jid), sha256="", url="",
                                      reason=f"{score:.2f} of {counted} words known"))
    # sources not yet acquired or not yet readable as judgments
    judgments.append(dict(area="judgment", category="source to recrawl", needs="recrawl the Sindh High Court portal",
                          source="SHC", kind="archive", title="judgments_sorted/<year>/*.html (55,123 files)",
                          file="judgments_sorted", sha256="", url="",
                          reason="the files are empty search-result pages: only the filename carries facts"))
    for code, name in (("FCC", "Federal Constitutional Court"), ("IHC", "Islamabad High Court"),
                       ("BHC", "Balochistan High Court"), ("FSC", "Federal Shariat Court"),
                       ("AJK", "AJK Supreme Court and High Court"), ("GB", "GB Supreme Appellate Court and Chief Court")):
        judgments.append(dict(area="judgment", category="court not held", needs="acquire the court's judgments",
                              source=code, kind="court", title=name, file="", sha256="", url="",
                              reason="no archive held (PRECEDENT-MODEL §0)"))

    for name, rows in (("laws", laws), ("judgments", judgments)):
        with open(out / "pending" / f"{name}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)

    def table(rows, by):
        c = collections.Counter(tuple(r[k] for k in by) for r in rows)
        lines = ["| " + " | ".join(by) + " | items |", "|" + "---|" * len(by) + "---:|"]
        for k, n in sorted(c.items(), key=lambda x: (x[0][0], -x[1])):
            lines.append("| " + " | ".join(k) + f" | {n:,} |")
        return "\n".join(lines)

    actionable = [r for r in laws if not r["category"].startswith("set aside")]
    md = f"""# What is not added yet — laws and judgments

Generated {dt.date.today().isoformat()} by `tools/pending_register.py` from the database and the staging lists; never
edited by hand (D-130). Every row, with its file, URL and reason, is in `docs/pending/laws.csv` and
`docs/pending/judgments.csv`. Rerun the tool after any landing.

## Laws: {len(actionable):,} items to work on ({len(laws) - len(actionable):,} more set aside by rule)

What each needs:

{table(actionable, ["category", "needs"])}

By source:

{table(actionable, ["source", "category"])}

Set aside by rule (listed for review, nothing to do unless a rule changes):

{table([r for r in laws if r["category"].startswith("set aside")], ["category"])}

## Judgments

{table(judgments, ["source", "category"])}

What each needs:

{table(judgments, ["category", "needs"])}

## Order of work (recommended)

1. **OCR**: law scans and judgment scans share one route (D-114). It needs the owner's choice: Google billing for
   Document AI, or the card-free Kaggle GPU route.
2. **Texts not structurable yet**: per-document readings, the established repair batches.
3. **Judgments held by a gate**: read the reasons; most are one parser rule each.
4. **Recrawls**: the Sindh High Court portal; the court's own copy for each law-report reprint; decision dates for
   judgments released undated.
5. **Not acquired / partial copies**: another source for each, or a dated retry.
6. **Courts not held**: acquire, then the same pipeline.
"""
    (out / "PENDING-REGISTER.md").write_text(md, encoding="utf-8")
    print(f"laws: {len(laws):,} rows ({len(actionable):,} to work on); judgments: {len(judgments):,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
