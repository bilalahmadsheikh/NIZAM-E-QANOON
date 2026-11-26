"""What a court above did with a judgment, as the court below's own listing records it (D-159; 0144).

    uv run python -m nizam.workers.recorded_outcomes [--archive PATH] [--apply]

The Islamabad High Court's listing (listing.jsonl inside the landed ihc_judgments.zip, D-156) records, for some of
its judgments, the Supreme Court's later outcome: O_SC_STATUS 'Upheld' / 'Set Aside' / 'Remanded Back' and
O_SC_DDATE ('/Date(<ms>)/', epoch milliseconds; read as a date in Pakistan time, UTC+5, which is how the listing's
own midnight values fall). Each record is tied to the released judgment read from the file it lists (the archive
member '<O_ID>_<name>'). Rebuilt in one transaction; nothing else is inferred.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path

from nizam.storage.db import connect

BUILDER = "nizam.recorded_outcomes/1"
SOURCE = "pk-ihc-judgments"
ARCHIVE = Path("/mnt/e/nizam-data/acquire/ihc/ihc_judgments.zip")
OUTCOMES = {"upheld": "affirmed", "set aside": "set_aside", "remanded back": "remanded", "remanded": "remanded"}
PKT = dt.timezone(dt.timedelta(hours=5))


def listed_date(v) -> dt.date | None:
    m = re.match(r"/Date\((-?\d+)\)/", str(v or ""))
    return dt.datetime.fromtimestamp(int(m.group(1)) / 1000, PKT).date() if m else None


def records(archive: Path) -> list[dict]:
    with zipfile.ZipFile(archive) as z:
        lines = z.read("ihc_judgments/listing.jsonl").decode("utf-8").splitlines()
    out = []
    for line in lines:
        r = json.loads(line)
        status = " ".join((r.get("O_SC_STATUS") or "").split())
        if not status:
            continue
        att = re.search(r'href="([^"]+)"', r.get("O_SC_ATTACHMENTS") or "")
        out.append(dict(ref=str(r["O_ID"]), printed=status, outcome=OUTCOMES.get(status.lower()),
                        day=listed_date(r.get("O_SC_DDATE")),
                        url=("https://mis.ihc.gov.pk" + att.group(1)) if att else None))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, default=ARCHIVE)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    recs = records(a.archive)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT DISTINCT split_part(split_part(s.member, '/', 2), '_', 1), j.id, j.decided_on
                         FROM v_release_judgment j JOIN judgment_document d ON d.id = j.document_id
                         JOIN judgment_source s ON s.sha256 = d.sha256 AND s.source_id = %s""", (SOURCE,))
        held = {}
        for ref, jid, day in cur.fetchall():
            held.setdefault(ref, []).append((jid, day))
        cur.execute("DELETE FROM judgment_recorded_outcome WHERE source_id = %s", (SOURCE,))
        n = unknown = not_held = 0
        for r in recs:
            if r["outcome"] is None:
                unknown += 1
                continue
            for jid, day in held.get(r["ref"], []):
                cur.execute("""INSERT INTO judgment_recorded_outcome (judgment_id, decided_on, source_id, listing_ref,
                                   upper_court_code, outcome, outcome_printed, upper_decided_on, upper_file_url, builder)
                               VALUES (%s, %s, %s, %s, 'SC', %s, %s, %s, %s, %s)""",
                            (jid, day, SOURCE, r["ref"], r["outcome"], r["printed"], r["day"], r["url"], BUILDER))
                n += 1
            if r["ref"] not in held:
                not_held += 1
        print(f"listed outcomes {len(recs)}: recorded {n}; status not read {unknown}; judgment not released {not_held}")
        if a.apply:
            conn.commit()
            print(f"applied ({BUILDER})")
        else:
            conn.rollback()
            print("dry run: nothing written (add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
