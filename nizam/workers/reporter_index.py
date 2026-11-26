"""The law-report index (D-150, migration 0139): reporter citations the Supreme Court publishes for its own judgments.

    python -m nizam.workers.reporter_index [--search ROWS.jsonl] [--latest LISTING.jsonl] [--apply]

The court's judgment search (search/rows.jsonl, D-148) and its "Last 25" listing (scp_site_judgments/listing.jsonl,
D-144) print, beside each file, the citation under which the judgment was reported ('2026 SCMR 715',
'PLD 2016 SC 1') and the court's own citation. Each citation is read with the judgment linker's own grammar
(judgment_linking.case_citations) and keyed by reporter_key, so a citing judgment and the listing agree by
construction. The listed file is found among the Supreme Court's sources by its name, and the citation is tied to
that file's released judgment -- the shown decision when the file is a second copy -- and its case. An identifier
only: no headnote or reporter text is stored (D-120).

Derived: the table is rebuilt in one transaction from the listings and the current release (audit A32). A listed
file that is not released (held, a scan) adds no row; a citation two different judgments claim is dropped and
reported, never guessed between. Without --apply nothing is written.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import zipfile
from pathlib import Path

from nizam.storage import judgment_linking as JL
from nizam.storage.db import connect

BUILDER = "nizam.reporter_index/2"   # /2: the IHC listing's citations and the LHC's neutral citations too (D-162)
ACQ = Path("/mnt/e/nizam-data/acquire/scp")
IHC_ARCHIVE = Path("/mnt/e/nizam-data/acquire/ihc/ihc_judgments.zip")


def listed(search: Path, latest: Path) -> list[tuple[str, str, str, str]]:
    """[(court, file name lower, printed citation, source)] from both Supreme Court listings, each pair once."""
    out, seen = [], set()
    for path, source in ((search, "scp-search"), (latest, "scp-latest")):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            f = r["filename"].lower()
            for col in ("citation", "sc_citation"):
                v = (r.get(col) or "").strip()
                if v and (f, v) not in seen:
                    seen.add((f, v))
                    out.append(("SC", f, v, source))
    return out


def ihc_listed(archive: Path = IHC_ARCHIVE) -> list[tuple[str, str, str, str]]:
    """the Islamabad High Court's listing (D-156) prints, for each judgment it lists, the citation under which it was
    reported (O_CITATION: '2023 PTD 603', 'Citation Awaited'); the archive member is '<O_ID>_<name>'"""
    if not archive.exists():
        return []
    with zipfile.ZipFile(archive) as z:
        names = {n.split("/")[-1].split("_", 1)[0]: n.split("/")[-1].lower() for n in z.namelist()
                 if n.lower().endswith(".pdf")}
        lines = z.read("ihc_judgments/listing.jsonl").decode("utf-8").splitlines()
    out = []
    for line in lines:
        r = json.loads(line)
        f = names.get(str(r["O_ID"]))
        v = (r.get("O_CITATION") or "").strip()
        if f and v:
            out.append(("IHC", f, v, "ihc-listing"))
    return out


def lhc_named(cur) -> list[tuple[str, str, str, str]]:
    """the Lahore High Court's site names each judgment file by its neutral citation ('2021LHC3320.pdf' is
    '2021 LHC 3320', the form its judgments cite: '(2015 LHC 3623)'); only names of exactly that form are read"""
    cur.execute("SELECT DISTINCT lower(regexp_replace(member, '^.*/', '')) FROM judgment_source WHERE court_code = 'LHC'")
    out = []
    for (f,) in cur.fetchall():
        m = re.fullmatch(r"((?:19|20)\d{2})lhc(\d{1,6})\.pdf", f)
        if m:
            out.append(("LHC", f, f"{m.group(1)} LHC {int(m.group(2))}", "lhc-file-name"))
    return out


def build(cur, rows: list[tuple[str, str, str, str]]) -> tuple[list[tuple], collections.Counter]:
    tally = collections.Counter()
    # the file's released judgment: by its member name among its court's sources; a second copy's citation goes to
    # the decision shown (v_shown_judgment), else to the released reading itself
    cur.execute("""
        SELECT DISTINCT s.court_code, lower(regexp_replace(s.member, '^.*/', '')), j.id, j.decided_on,
               EXISTS (SELECT 1 FROM v_shown_judgment v WHERE v.id = j.id AND v.decided_on = j.decided_on),
               (SELECT min(c.case_key) FROM judgment_case c
                 WHERE c.judgment_id = j.id AND c.decided_on = j.decided_on AND c.role = 'lead'),
               (SELECT array_agg(c.case_key) FROM judgment_case c
                 WHERE c.judgment_id = j.id AND c.decided_on = j.decided_on)
          FROM judgment_source s
          JOIN judgment_document d ON d.sha256 = s.sha256 AND d.court_code = s.court_code AND d.is_active
          JOIN v_release_judgment j ON j.document_id = d.id
         WHERE s.court_code IN ('SC', 'IHC', 'LHC')""")
    by_file = collections.defaultdict(list)
    for court, f, jid, day, shown, lead, keys in cur.fetchall():
        by_file[(court, f)].append((not shown, str(jid), day, lead, frozenset(keys or ())))
    claims = collections.defaultdict(list)
    out = []
    for court, f, printed, source in rows:
        cites = [c for c in JL.case_citations(printed) if JL.reporter_key(c)]
        if not cites:
            tally[f"{source}: citation not read ('NA', 'Citation Awaited')"] += 1
            continue
        if (court, f) not in by_file:
            tally[f"{source}: file not released"] += 1
            continue
        tally[f"{source}: indexed"] += 1
        _copy, jid, day, lead, keys = sorted(by_file[(court, f)], key=lambda x: x[:3])[0]
        # a cell may print the judgment in several reports ('2026 SCMR 42 2026 PLC (CS) 247'): each is indexed
        for c in cites:
            k = JL.reporter_key(c)
            claims[k].append((lead, keys))
            out.append((*k, printed[:200], jid, day, lead, source, f, BUILDER))
    # one reported decision is often listed under several files: its short order and its reasons (one lead case), or
    # connected cases decided together (one judgment's case line holds every claimant's lead). A citation is kept
    # when one claimant's cases cover every claimant's lead; otherwise two decisions claim it and it is dropped.
    chosen = {}
    for k, cl in claims.items():
        leads = {ld for ld, _ks in cl}
        chosen[k] = next((ld0 for ld0, ks in sorted(cl, key=lambda x: str(x[0])) if leads <= ks | {ld0}), None)
    contested = {k for k, ld in chosen.items() if ld is None}
    tally["citations claimed by two decisions (dropped)"] = len(contested)
    tally["citations listed under several files of one decision (kept)"] = sum(
        1 for k, cl in claims.items() if k not in contested and len({ld for ld, _ in cl}) > 1)
    # every row of a citation names the one case it reports (the covering judgment's lead)
    out = [(*r[:7], chosen[tuple(r[:4])], *r[8:]) for r in out if tuple(r[:4]) not in contested]
    tally["rows"] = len({(r[:4], r[5]) for r in out})
    return out, tally


def main() -> int:
    ap = argparse.ArgumentParser(description="the law-report index (D-150)")
    ap.add_argument("--search", type=Path, default=ACQ / "search" / "rows.jsonl")
    ap.add_argument("--latest", type=Path, default=ACQ / "scp_site_judgments" / "listing.jsonl")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    with connect() as conn, conn.cursor() as cur:
        rows, tally = build(cur, listed(a.search, a.latest) + ihc_listed() + lhc_named(cur))
        cur.execute("DELETE FROM reporter_citation")
        cur.executemany("""INSERT INTO reporter_citation (series, year, court, page, printed, judgment_id, decided_on,
                                                          case_key, source, source_ref, builder)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (series, year, court, page, judgment_id) DO NOTHING""", rows)
        cur.execute("SELECT series, count(*) FROM reporter_citation GROUP BY 1 ORDER BY 2 DESC")
        for k, n in tally.items():
            print(f"  {k:<55} {n:>7,}")
        print("  by series:", dict(cur.fetchall()))
        if a.apply:
            conn.commit()
            print(f"applied ({BUILDER})")
        else:
            conn.rollback()
            print("dry run: nothing written (add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
