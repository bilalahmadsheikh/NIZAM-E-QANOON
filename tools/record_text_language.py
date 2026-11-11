"""Record the language of each released expression's text, measured from that text (migration 0070, text_language).

WHY. The segmenter writes every provision's text to provision_version.text_en whatever its language, and
document.language is unreliable both ways (doc 4304 is 89% Urdu but tagged 'en'; 9627, 9653, 9677 are tagged 'ur'
and are English). Retrieval and rendering need to know which text is Urdu, so it is measured here, per expression,
from the released text itself.

THE RULE. Over all active provision versions of the instrument, count Latin letters and Arabic-script letters.
  * Arabic-script share >= 0.60  -> 'ur', or 'sd' when Sindhi-only letters are >= 2% of the Arabic-script letters;
  * Arabic-script share <= 0.10  -> 'en';
  * anything between, or fewer than 20 letters in all -> no assertion; reported for a person to read.
The counts are kept in the evidence. Nothing about which language version governs is asserted (docs/03b §3,
authentic_language is a legal question).

Idempotent: an expression whose standing value already equals the measurement is skipped.

    python tools/record_text_language.py            # report
    python tools/record_text_language.py --apply    # write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METHOD = "nizam.text_language_from_script/1"
SINDHI = "ٻڄڃڇڏڌڊڍڙڪڳڱڻٺٽٿڦڀ"
MEASURE = f"""
SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.document_id,
       coalesce(sum(length(regexp_replace(v.text_en, '[^A-Za-z]', '', 'g'))), 0)          AS latin,
       coalesce(sum(length(regexp_replace(v.text_en, '[^؀-ۿ]', '', 'g'))), 0)  AS arabic,
       coalesce(sum(length(regexp_replace(v.text_en, '[^{SINDHI}]', '', 'g'))), 0)       AS sindhi
  FROM v_release_instrument i
  JOIN provision p ON p.instrument_id = i.id AND p.is_active
  JOIN provision_version v ON v.provision_id = p.id
 GROUP BY 1, 2, 3, 4
"""


def classify(latin: int, arabic: int, sindhi: int) -> str | None:
    total = latin + arabic
    if total < 20:
        return None
    share = arabic / total
    if share >= 0.60:
        return "sd" if arabic and sindhi / arabic >= 0.02 else "ur"
    if share <= 0.10:
        return "en"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    from nizam.storage.db import connect
    counts: dict[str, int] = {}
    undecided = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute(MEASURE)
        measured = cur.fetchall()
        cur.execute("""SELECT source_observation_id, expression_ordinal, value FROM v_instrument_metadata_current
                        WHERE field = 'text_language'""")
        standing = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        for iid, obs, ordinal, doc, latin, arabic, sindhi in measured:
            lang = classify(latin, arabic, sindhi)
            if lang is None:
                undecided.append((doc, iid, latin, arabic)); counts["undecided"] = counts.get("undecided", 0) + 1
                continue
            counts[lang] = counts.get(lang, 0) + 1
            if standing.get((obs, ordinal)) == lang:
                counts["unchanged"] = counts.get("unchanged", 0) + 1
                continue
            evidence = dict(reviewer_type="tool", latin_letters=latin, arabic_script_letters=arabic,
                            sindhi_only_letters=sindhi,
                            arabic_share=round(arabic / (latin + arabic), 4),
                            measured_over="all active provision_version.text_en of the instrument")
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis, method,
                              evidence, recorded_by)
                           VALUES (%s, %s, 'text_language', %s, 'asserted', 'measured_script_share', %s,
                                   %s::jsonb, 'claude')""",
                        (obs, ordinal, lang, METHOD, json.dumps(evidence)))
            counts["recorded"] = counts.get("recorded", 0) + 1
        if not args.apply:
            conn.rollback()
    print(json.dumps(counts, indent=1))
    for doc, iid, latin, arabic in sorted(undecided):
        print(f"undecided: doc {doc} instrument {iid} latin={latin} arabic={arabic}")
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
