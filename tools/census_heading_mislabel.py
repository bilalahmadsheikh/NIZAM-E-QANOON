"""Provisions whose OWN printed opener names one section and whose tree heading names another.

The source settles this without any contents list.  Pakistani drafting prints a
section as ``37. Penalty for obstructing inspector.-- Whoever wilfully ...``:
the number, the section's own name, then a dash or full stop, then the enacted
text.  Where the provision's first block opens that way and the heading the tree
carries is a DIFFERENT name, the citation resolves to mis-labelled text -- the
user asks for section 37 and is handed the right words under the wrong name, or
reads the name and takes the neighbouring section's words for it.

This is invisible to the contents-gap queue.  A gap needs an unmatched entry; a
swapped heading has a matched entry for every section, which is exactly why a
constant contents-to-body offset produces no gaps at all.

Reads only unless ``--record`` is supplied. A recorded census carries a digest
of the exact active provision population it measured, so the audit reports it
as stale after any subsequent replay rather than presenting an obsolete pass.
"""
from __future__ import annotations

import argparse
import collections
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nizam.storage.db import connect

OUT = os.environ.get("NIZAM_CENSUS_OUT", "")
SEGMENT_LOCK_KEY = 0x4E495A414D534547


# label, then the section's own printed name, then the dash or stop that ends it
OPENER = re.compile(
    r"^\s*(?:\d{0,3}\s*\[\s*)?"
    r"(?P<label>[0-9]{1,4}[A-Za-z]{0,3}(?:-[A-Za-z0-9]{1,3})?)\s*[.)]\s*"
    r"(?P<name>[A-Z][^.—]{6,90}?)\s*"
    r"(?:\.\s*[—–-]{1,2}|\.\s*_{2}|[—–]{1,2}|\.\s+(?=[A-Z(]))")

OPERATIVE = re.compile(
    r"\b(shall|may|must|means?|includes?|is|are|was|were|has|have|had|be|been|"
    r"appl(?:y|ies|ied)|extends?|comes?|said|this|these|whoever|nothing|no|"
    r"any|every|where|when|unless|if|subject|notwithstanding|provided|"
    r"following|hereby|such|there)\b", re.I)

# A heading names the section; it never opens with a preposition.  Every Sindh
# and Punjab Finance Act in the corpus prints its amending sections as "2. In
# the Stamp Act, 1899, in its application to Sindh, ..." with the real heading
# -- "Amendment of Act II of 1899." -- in the margin.  Reading that operative
# opener as a competing NAME put twenty-odd Finance Act sections on a list that
# is supposed to mean a citation resolves to the wrong text, and a list with
# known false positives cannot carry a gate.
PREPOSITION = re.compile(
    r"^(?:in|of|for|to|on|at|by|from|under|upon|after|before|throughout|"
    r"where|when|while|if|save|except|with|without|during|against|"
    r"notwithstanding|subject|provided|according|pursuant|whenever|whereas)\b",
    re.I)

# Editorial apparatus is not a section's name.  Doc 1382's section 2 prints
# "Clause (d) omitted by Khyber Pakhtunkhwa Ordinance ..." where the genuine
# marginal note is "Definitions." -- a footnote standing at the head of the
# provision, which is A10's defect, counted there, not a swapped heading.
APPARATUS = re.compile(
    r"^\s*(?:clause|sub-?section|sub-?rule|proviso|words?|figures?|letters?|"
    r"brackets?|commas?|entry|entries|schedule)\b[^\n]{0,80}?"
    r"\b(?:omitted|substituted|subs\.|ins\.|inserted|added|deleted|rep\.)\b"
    r"|^\s*(?:subs\.|ins\.|added|omitted|substituted|inserted)\b", re.I)

_STOP = {"the", "of", "a", "an", "and", "or", "to", "for", "in", "on", "by",
         "at", "its", "his", "her", "their", "etc", "not"}


def _tokens(name: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (name or "").lower())
            if t not in _STOP and len(t) > 1]


def _initialism_of(short: list[str], long: list[str]) -> bool:
    """Is a token in `short` the initials of consecutive words in `long`?

    Doc 2582 prints "Functions of the Agriculture Pesticide Technical Advisory
    Committee" where the contents calls it "Function of the APTA Committee".
    One name, abbreviated -- not two names.
    """
    for tok in short:
        if len(tok) < 3 or tok in long:
            continue
        initials = "".join(w[0] for w in long)
        if tok in initials:
            return True
    return False


def _same_name(printed: str, heading: str) -> bool:
    """One name written two ways: abbreviated, truncated at either end, or mis-spelt.

    Prefix comparison alone is not enough.  Doc 2511 prints "Welfare Fund"
    against a carried "Punjab Employees Welfare Fund" -- a truncation at the
    FRONT.  Doc 3068 prints "Duties of Suprintendent of vaccination" against
    "Duties of Superintendent of vaccination No..." -- one dropped letter.
    Both are the same section's name and neither is a mis-citation.
    """
    a, b = _tokens(printed), _tokens(heading)
    if not a or not b:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    matched = 0
    for tok in short:
        if any(tok == other
               # >= 4, not > 4: the Court Fees Act prints "Rules as to costs of
               # processes" against a carried "Rules as to cost of processes",
               # and a four-letter singular was the whole difference.
               or (len(tok) >= 4 and len(other) >= 4
                   and difflib.SequenceMatcher(None, tok, other).ratio() >= 0.8)
               for other in long):
            matched += 1
    if matched / len(short) >= 0.8:
        return True
    if _initialism_of(short, long) and matched / len(short) >= 0.5:
        return True
    return False


SQL = """
SELECT i.document_id, left(i.short_title,46), p.id::text, p.label, p.first_page,
       i.id::text, p.kind::text, p.heading, tb.text,
       (SELECT count(*) FROM instrument_toc_entry e WHERE e.provision_id=p.id)
  FROM provision p
  JOIN instrument i ON i.id=p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
  JOIN text_block tb ON tb.id=p.first_block
 WHERE p.is_active AND p.heading IS NOT NULL AND btrim(p.heading) <> ''
   AND p.kind::text IN ('section','article','rule','regulation','paragraph')
"""


def nk(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_hits(rows) -> list[dict]:
    hits = []
    for (doc, title, pid, label, page, instrument_id, kind, heading,
         text, linked) in rows:
        flat = " ".join((text or "").split())
        m = OPENER.match(flat)
        if not m:
            continue
        if nk(m.group("label")) != nk(label):
            continue          # the block does not open with THIS provision's label
        printed = m.group("name").strip(" .—-")
        # A heading names the section; it does not enact anything.  Without this
        # guard the Canal and Drainage Act's "3. In this Act unless there be
        # something repugnant in the subject or context,--" reads as a printed
        # name disagreeing with the genuine marginal note "Interpretation
        # clause.", and every marginal-note statute in the corpus joins the
        # list.  Operative text is not a name, however it is punctuated.
        if PREPOSITION.match(printed) or APPARATUS.match(printed):
            continue
        if OPERATIVE.search(printed) or not (2 <= len(printed.split()) <= 14):
            continue
        pk, hk = nk(printed), nk(heading)
        if len(pk) < 10 or len(hk) < 10:
            continue
        if pk.startswith(hk) or hk.startswith(pk):
            continue          # same name, differently truncated
        if _same_name(printed, heading):
            continue
        # The Code of Criminal Procedure decides the shape of this test.  Its
        # contents list prints "Issues of process" where its body prints "Issus
        # of process", and "Special Judicial Magistrates" where the body carries
        # the amendment markers "Special Judicial 2[* * *] Magistrate".  Those
        # are one section's name spelt two ways, not two sections' names, and
        # calling them mis-citations would have put 62 CrPC sections on a list
        # that is supposed to mean a citation resolves to the wrong text.
        ratio = difflib.SequenceMatcher(None, pk, hk).ratio()
        hits.append({"doc": doc, "title": title, "pid": pid,
                     "instrument_id": instrument_id, "label": label,
                     "page": page, "kind": kind,
                     "tree_heading": heading, "printed_name": printed,
                     "toc_linked": bool(linked), "ratio": round(ratio, 3),
                     "class": "variant_spelling" if ratio >= 0.62 else "different_name",
                     "block": flat[:120]})
    return hits


def segmentation_lock_is_held(cur) -> bool:
    """Is `nizam.workers.segment`'s advisory lock held right now?

    A single-bigint advisory lock is not stored as one 64-bit column. Postgres
    splits it: the high 32 bits land in `classid`, the low 32 in `objid`, and
    `objsubid` is 1 (a two-int lock uses 2). Comparing the whole key to `objid`
    raises "OID out of range" -- `objid` is an oid, so anything above 2^32 is
    not merely wrong, it fails to parse as a value of that type.
    """
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' "
        "AND classid=%s AND objid=%s AND granted AND objsubid=1)",
        (SEGMENT_LOCK_KEY >> 32, SEGMENT_LOCK_KEY & 0xFFFFFFFF),
    )
    return bool(cur.fetchone()[0])


def record_census(conn, hits: list[dict], measured_by: str) -> int:
    detector_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with conn.cursor() as cur:
        if segmentation_lock_is_held(cur):
            raise RuntimeError(
                "a segmentation run holds the advisory lock; refusing to "
                "record a census of a moving corpus"
            )
        cur.execute(
            "SELECT corpus_digest,scope_provisions,active_instruments "
            "FROM v_heading_mislabel_corpus_state"
        )
        digest, scope, instruments = cur.fetchone()
        cur.execute(
            """INSERT INTO heading_mislabel_census
                   (measured_by,detector,detector_sha256,corpus_digest,
                    scope_provisions,active_instruments)
                 VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (measured_by, "tools/census_heading_mislabel.py/1", detector_sha,
             digest, scope, instruments),
        )
        census_id = int(cur.fetchone()[0])
        cur.executemany(
            """INSERT INTO heading_mislabel_finding
                   (census_id,provision_id,instrument_id,document_id,
                    short_title,kind,label,first_page,tree_heading,printed_name,
                    block_excerpt,finding_class,similarity,toc_linked)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(
                census_id, hit["pid"], hit["instrument_id"], hit["doc"],
                hit["title"], hit["kind"], hit["label"], hit["page"],
                hit["tree_heading"], hit["printed_name"], hit["block"],
                hit["class"], hit["ratio"], hit["toc_linked"],
            ) for hit in hits],
        )
    return census_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true",
                        help="persist this measured census and its corpus digest")
    parser.add_argument("--measured-by", default="nizam.heading_mislabel_census/1")
    parser.add_argument("--json", default=OUT,
                        help="write findings to JSON (also NIZAM_CENSUS_OUT)")
    args = parser.parse_args()

    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        with conn.cursor() as cur:
            cur.execute(SQL)
            rows = cur.fetchall()
        print(f"provisions with a heading and a first block: {len(rows)}",
              flush=True)
        hits = find_hits(rows)
        census_id = record_census(conn, hits, args.measured_by) \
            if args.record else None

    if args.json:
        with open(args.json, "w", encoding="utf-8") as stream:
            json.dump(hits, stream, ensure_ascii=False, indent=1)
    swap = [h for h in hits if h["class"] == "different_name"]
    var = [h for h in hits if h["class"] == "variant_spelling"]
    docs = collections.Counter(h["doc"] for h in swap)
    print(f"\nheading disagrees with the provision's own printed opener: {len(hits)}")
    print(f"  one name spelt two ways (contents vs body typography/markers): "
          f"{len(var)} in {len({h['doc'] for h in var})} documents")
    print(f"  A DIFFERENT NAME -- the citation resolves to mis-labelled text: "
          f"{len(swap)} in {len(docs)} documents")
    print(f"    of those, reachable from a printed contents entry: "
          f"{sum(1 for h in swap if h['toc_linked'])}")
    t = {h["doc"]: h["title"] for h in swap}
    print(f"\n{'n':>4}  doc     title")
    for d, n in docs.most_common(30):
        print(f"{n:>4}  {d:<6}  {t[d]}")
    if census_id is not None:
        print(f"\nrecorded heading census {census_id} ({len(hits)} findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
