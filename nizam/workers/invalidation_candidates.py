"""Provisions a court strikes down or declares repugnant: machine candidates for a lawyer (D-161; 0146;
docs/PRECEDENT-MODEL.md §4.3, §2.2).

    uv run python -m nizam.workers.invalidation_candidates [--apply] [--sheet DIR]

For every resolved statute citation of a released judgment (judgment_statute_reference, resolution 'resolved'), the
sentence holding it is read by nizam.storage.treatment.invalidation_of. A reading is a candidate
(judicial_invalidation_candidate), its status the latest review of its key. The key is the sentence's words, the
citation AS PRINTED and the reading -- stable across a judgment's re-read and a law's re-segmentation, so a
reviewer's decision outlives both. Nothing here changes what is served: only a lawyer_verified review with extent
'whole' does (mv_provision_invalidation, after tools/refresh_serving.py).

--sheet writes the candidates awaiting review, with the evidence, the provision as the linker resolved it and, for a
Federal Shariat Court judgment, the court's own listing entry ('law challenged', remarks: D-157), for
tools/invalidation_review_load.py.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path

from nizam.storage.db import connect
from nizam.storage.treatment import invalidation_of, invalidation_voice, sentence_bounds

BUILDER = "nizam.invalidation_candidates/1"
FSC_ARCHIVE = Path("/mnt/e/nizam-data/acquire/fsc/fsc_judgments.zip")


def key_of(sentence: str, raw: str, reading: str) -> str:
    words = " ".join(sentence.split())
    return hashlib.sha256(f"{words}\x1f{' '.join(raw.split())}\x1f{reading}".encode()).hexdigest()


def fsc_listing() -> dict[str, dict]:
    """archive member name -> the court's listing entry it was fetched for (law challenged, remarks)"""
    if not FSC_ARCHIVE.exists():
        return {}
    with zipfile.ZipFile(FSC_ARCHIVE) as z:
        manifest = list(csv.DictReader(z.read("fsc_judgments/manifest.csv").decode("utf-8").splitlines()))
        listing = [json.loads(x) for x in z.read("fsc_judgments/listing.jsonl").decode("utf-8").splitlines()]
    by_url = {r["url"]: r for r in listing if r.get("law_challenged")}
    return {f"fsc_judgments/{m['filename']}": by_url[m["url"]] for m in manifest if m["filename"] and m["url"] in by_url}


def build(cur):
    cur.execute("""SELECT DISTINCT ON (review_key) review_key, decision FROM judicial_invalidation_review
                    ORDER BY review_key, reviewed_at DESC, id DESC""")
    reviews = dict(cur.fetchall())
    cur.execute("""SELECT r.judgment_id, r.decided_on, r.paragraph_id, r.char_start, r.char_end, r.raw,
                          r.dst_provision_id, r.dst_instrument_id, p.text, j.court_code, j.case_no_printed,
                          i.short_title, pr.label,
                          (SELECT min(s.member) FROM judgment_document d JOIN judgment_source s ON s.sha256 = d.sha256
                            WHERE d.id = j.document_id) AS member
                     FROM judgment_statute_reference r
                     JOIN v_release_judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                     JOIN judgment_paragraph p ON p.id = r.paragraph_id AND p.decided_on = r.decided_on
                     JOIN instrument i ON i.id = r.dst_instrument_id
                     JOIN provision pr ON pr.id = r.dst_provision_id
                    WHERE r.resolution = 'resolved' AND r.dst_provision_id IS NOT NULL
                      -- a Constitution's Article is the measure ('unconstitutional, against Article 25') or the
                      -- jurisdiction ('under Article 199'), never the provision struck down; a constitutional
                      -- amendment is its own Act and is read
                      AND i.short_title !~* '^(the\\s+)?(constitution of the islamic republic|azad jammu and kashmir interim constitution|gilgit.baltistan (governance|government) order)'""")
    rows, tally, sheet, seen = [], collections.Counter(), [], set()
    listing = None
    for (jid, day, pid, s, e, raw, prov, inst, text, court, case, title, label, member) in cur.fetchall():
        a, b = sentence_bounds(text, s, e)
        sentence = text[a:b]
        reading = invalidation_of(sentence)
        if reading is None or (pid, a, prov) in seen:
            continue
        seen.add((pid, a, prov))
        key = key_of(sentence, raw, reading)
        status = reviews.get(key, "machine_candidate")
        rows.append((jid, day, pid, a, b, prov, inst, reading, key, status, BUILDER))
        tally[f"reading:{reading}"] += 1
        tally[f"court:{court}"] += 1
        tally[f"review:{status}"] += 1
        tally[f"voice:{invalidation_voice(sentence)}"] += 1
        if status == "machine_candidate":
            if listing is None:
                listing = fsc_listing()
            entry = listing.get(member or "", {})
            sheet.append(dict(review_key=key, reading=reading, voice=invalidation_voice(sentence),
                              judgment=f"{court} {case} ({day})",
                              provision=f"{title} {label}", provision_id=str(prov), cited_as=raw,
                              sentence=" ".join(sentence.split()),
                              court_listing=(f"law challenged: {entry.get('law_challenged')}; remarks: "
                                             f"{entry.get('remarks')}") if entry else "",
                              decision="", extent="", extent_note="", effective_on="", appeal_state="",
                              reviewer="", note=""))
    return rows, tally, sheet


def main() -> int:
    ap = argparse.ArgumentParser(description="judicial invalidation candidates for a lawyer (D-161)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--sheet", type=Path)
    a = ap.parse_args()
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        rows, tally, sheet = build(cur)
        cur.execute("DELETE FROM judicial_invalidation_candidate")
        with cur.copy("COPY judicial_invalidation_candidate (judgment_id, decided_on, paragraph_id, sentence_start, "
                      "sentence_end, provision_id, instrument_id, reading, review_key, review_status, builder) "
                      "FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)
        for k, v in sorted(tally.items()):
            print(f"  {k:28} {v:7,}")
        if a.sheet:
            a.sheet.mkdir(parents=True, exist_ok=True)
            out = a.sheet / f"invalidation-candidates-{time.strftime('%Y-%m-%d')}.csv"
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(sheet[0]) if sheet else ["review_key"])
                w.writeheader()
                w.writerows(sheet)
            print(f"review sheet: {len(sheet)} candidates -> {out}")
        if a.apply:
            conn.commit()
            print(f"applied {len(rows)} candidates in {time.time() - t0:.0f}s ({BUILDER})")
        else:
            conn.rollback()
            print("dry run: nothing written (add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
