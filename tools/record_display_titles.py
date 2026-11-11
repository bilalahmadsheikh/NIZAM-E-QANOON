"""Record each released instrument's display title from the reviewed names table (migration 0070, field display_title).

Input: .artifacts/instrument-names-2026-11-11/instrument-names.csv (built 11 Nov 2026 from each instrument's own
first pages; README.md beside it explains every column). Only rows whose name was VERIFIED or NEAR-MATCHED in the
instrument's printed text and that need no review are recorded. The 636 rows marked needs_review=yes are not
recorded: they keep rendering short_title until a person has read their page.

Refused, whatever the CSV says: an instrument that is no longer active and canonical; a name carrying a catalogue
artefact ('NA-', 'Baln', 'official website', 'under review', '.docx', '.pdf'); a name with no letters.

Idempotent: an expression whose standing display title already equals the name is skipped.

--reviewed FILE (12 Nov 2026): a person's decision on needs_review rows (.artifacts/instrument-names-2026-11-11/
reviewed-2026-11-12.json, built by reviewed-2026-11-12.py beside it): 'accept' records the cleaned name (basis
reviewed_printed_name), 'fix' records the corrected name given in full (basis reviewed_corrected_name), 'reject'
records nothing. An Urdu-script name is recorded only for an instrument whose text_language is 'ur'.

    python tools/record_display_titles.py            # report
    python tools/record_display_titles.py --apply    # write
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CSV = ROOT / ".artifacts/instrument-names-2026-11-11/instrument-names.csv"
METHOD = "nizam.display_title_from_printed_text/1"
ACCEPT = {"verified_in_printed_text", "near_match_in_printed_text"}
ARTEFACT = re.compile(r"^\s*NA\s*-|\bBaln\b|official website|under review|\.docx|\.pdf", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reviewed", help="JSON of reviewer decisions on needs_review rows (see above)")
    args = ap.parse_args()
    decisions = json.loads(Path(args.reviewed).read_text(encoding="utf-8")) if args.reviewed else {}
    with CSV.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    from nizam.storage.db import connect
    counts = dict(rows=len(rows), review=0, not_verified=0, artefact=0, inactive=0, unchanged=0, recorded=0)
    refused: list[str] = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id::text, source_observation_id, expression_ordinal FROM instrument
                        WHERE is_active AND duplicate_of IS NULL""")
        active = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        cur.execute("""SELECT source_observation_id, expression_ordinal, value FROM v_instrument_metadata_current
                        WHERE field = 'display_title'""")
        standing = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        cur.execute("SELECT id::text, text_language FROM instrument WHERE is_active AND duplicate_of IS NULL")
        language = dict(cur.fetchall())
        seen: set = set()
        for row in rows:
            basis, reviewer, decision = row["name_check"], "tool", None
            if row["needs_review"].strip().lower() != "no":
                decision = decisions.get(f"{row['document_id']}:{row['expression_ordinal']}")
                if decision is None or decision["action"] == "reject"                         or decision.get("instrument_id") != row["instrument_id"]:
                    counts["review"] += 1; continue
                if decision.get("urdu_only_if_text_is_urdu") and language.get(row["instrument_id"]) != "ur":
                    counts["urdu_name_on_non_urdu_text"] = counts.get("urdu_name_on_non_urdu_text", 0) + 1
                    continue
                basis = "reviewed_printed_name" if decision["action"] == "accept" else "reviewed_corrected_name"
                reviewer = "claude"
            if row["name_check"] not in ACCEPT:
                counts["not_verified"] += 1; continue
            name = (decision["name"] if decision else row["actual_name"]).strip()
            if not name or ARTEFACT.search(name) or not re.search(r"[A-Za-z؀-ۿ]", name):
                counts["artefact"] += 1; refused.append(f"{row['instrument_id']}: {name!r}"); continue
            key = active.get(row["instrument_id"])
            if key is None:
                counts["inactive"] += 1; continue
            if key in seen:
                continue
            seen.add(key)
            if standing.get(key) == name:
                counts["unchanged"] += 1; continue
            evidence = {
                "reviewer_type": reviewer,
                **({"review_decision": decision["action"], "review_flags": row["review_flags"],
                    "reviewed_file": str(Path(args.reviewed).as_posix()),
                    **({"corrected_from": decision["was"]} if decision["action"] == "fix" else {})}
                   if decision else {}),
                "names_table": str(CSV.relative_to(ROOT)).replace("\\", "/"),
                "name_check": row["name_check"],
                "basis_detail": row["basis"],
                "catalogue_name_original": row["catalogue_name_original"],
                "short_title_at_recording": None,
            }
            cur.execute("SELECT short_title FROM instrument WHERE id = %s", (row["instrument_id"],))
            evidence["short_title_at_recording"] = cur.fetchone()[0]
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis, method,
                              evidence, recorded_by)
                           VALUES (%s, %s, 'display_title', %s, 'asserted', %s, %s, %s::jsonb, 'claude')""",
                        (key[0], key[1], name, basis, METHOD, json.dumps(evidence, ensure_ascii=False)))
            counts["recorded"] += 1
        if not args.apply:
            conn.rollback()
    print(json.dumps(counts, indent=1))
    for r in refused[:20]:
        print("refused:", r)
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
