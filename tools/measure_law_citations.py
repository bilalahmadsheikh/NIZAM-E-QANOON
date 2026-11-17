"""measure_law_citations.py [--apply] : how many OTHER released laws cite each released law by title (D-075).

Reads every released law's served text once (provision_version of active provisions in released instruments) and
finds citations by title. A citation ends at a type word -- Act, Ordinance, Code, Order, Rules, Regulation(s) -- so
only those positions are examined: the longest known law name ending there is the cited law. A year printed after
it (', 1898' or '(V of 1898)') chooses between laws of one name, then the citing law's own jurisdiction, then the
federal law; a name still ambiguous is not counted. 'the Constitution' counts for the Constitution of 1973
(document 4419) when the citing law is not of AJK or Gilgit-Baltistan, which have their own. Self-citation is not
counted. legal_edge links into a law (amends, repeals, empowers) are added as edges_in.

Without --apply it prints the top laws and writes nothing. With --apply it replaces law_citation_count whole."""
from __future__ import annotations

import argparse
import collections
import re
import time

from nizam.storage.db import connect

METHOD = "nizam.measure_law_citations/1"
TYPE = {"act", "ordinance", "code", "order", "rules", "regulation", "regulations"}
WORD = re.compile(r"[a-z0-9]+")
YEAR = re.compile(r"^(1[6-9]\d\d|20\d\d)$")
CONSTITUTION_DOC = 4419


def name_key(title: str) -> tuple[str, int | None]:
    """A law title as the name others cite it by, and the year it prints: 'The Code of Criminal Procedure, 1898' ->
    ('code of criminal procedure', 1898)."""
    t = title.lower()
    year = None
    m = re.search(r"(1[6-9]\d\d|20\d\d)\s*\)?\s*$", t)
    if m:
        year = int(m.group(1))
        t = t[:m.start()]
    t = re.sub(r"\((?:[^()]*\bof\s+)?(?:1[6-9]\d\d|20\d\d)\)", " ", t)       # '(act v of 1898)'
    words = WORD.findall(t)
    if words and words[0] == "the":
        words = words[1:]
    return " ".join(words), year


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    started = time.time()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT r.id, r.document_id, r.expression_ordinal, r.jurisdiction::text,
                              coalesce(r.display_title, r.short_title), r.year
                         FROM v_release_instrument r""")
        laws = cur.fetchall()
        by_id = {}
        names: dict[str, list] = collections.defaultdict(list)
        forward: set = set()
        for iid, doc, expr, jur, title, year in laws:
            key, printed = name_key(title or "")
            words = key.split()
            by_id[iid] = (doc, expr, jur)
            # a name others can cite: ends in a type word ('Pakistan Penal Code') or opens with one ('Code of
            # Criminal Procedure'), and says more than the type word
            if len(words) >= 2 and words[-1] in TYPE:
                names[key].append((doc, expr, jur, printed or year))
            elif len(words) >= 3 and words[0] in TYPE and words[1] == "of":
                names[key].append((doc, expr, jur, printed or year))
                forward.add(key)
        longest = max(len(k.split()) for k in names)

        def resolve(key, year, citing_jur, citing_doc):
            cands = names[key]
            if year is not None and any(c[3] == year for c in cands):
                cands = [c for c in cands if c[3] == year]
            if len(cands) > 1:
                same = [c for c in cands if c[2] == citing_jur]
                fed = [c for c in cands if c[2] == "fed"]
                cands = same or fed or cands
            if len({(c[0], c[1]) for c in cands}) != 1:
                return None
            c = cands[0]
            return None if c[0] == citing_doc else (c[0], c[1])

        cited_by: dict[tuple, set] = collections.defaultdict(set)
        count: collections.Counter = collections.Counter()
        texts = 0
        with conn.cursor(name="law_texts") as stream:
            stream.itersize = 20000
            stream.execute("""SELECT p.instrument_id, v.text_en
                                FROM provision p JOIN provision_version v ON v.provision_id = p.id
                               WHERE p.is_active AND v.text_en IS NOT NULL
                                 AND p.instrument_id IN (SELECT id FROM v_release_instrument)""")
            for iid, text in stream:
                texts += 1
                citing_doc, _e, citing_jur = by_id[iid]
                words = WORD.findall(text.lower())
                for i, w in enumerate(words):
                    hit = None
                    if w in TYPE:
                        for n in range(min(longest, i + 1), 1, -1):
                            key = " ".join(words[i - n + 1:i + 1])
                            if key in names and key not in forward:
                                year = next((int(x) for x in words[i + 1:i + 7] if YEAR.match(x)), None)
                                hit = resolve(key, year, citing_jur, citing_doc)
                                break
                        # a name that opens with the type word: 'Code of Criminal Procedure, 1898'
                        if hit is None and i + 2 < len(words) and words[i + 1] == "of":
                            for n in range(min(longest, len(words) - i), 2, -1):
                                key = " ".join(words[i:i + n])
                                if key in forward:
                                    year = next((int(x) for x in words[i + n:i + n + 6] if YEAR.match(x)), None)
                                    hit = resolve(key, year, citing_jur, citing_doc)
                                    break
                    elif (w == "constitution" and i > 0 and words[i - 1] == "the"
                          and citing_jur not in ("ajk", "gb") and citing_doc != CONSTITUTION_DOC):
                        hit = (CONSTITUTION_DOC, 0)
                    if hit:
                        cited_by[hit].add(citing_doc)
                        count[hit] += 1
        cur.execute("""SELECT r.document_id, r.expression_ordinal, count(DISTINCT e.src_instrument)
                         FROM legal_edge e JOIN v_release_instrument r ON r.id = e.dst_instrument
                        WHERE e.src_instrument IS DISTINCT FROM e.dst_instrument GROUP BY 1, 2""")
        edges = {(d, x): n for d, x, n in cur.fetchall()}
        rows = []
        for iid, doc, expr, *_ in laws:
            k = (doc, expr)
            rows.append((doc, expr, len(cited_by.get(k, ())), count.get(k, 0), edges.get(k, 0)))
        rows = list({(r[0], r[1]): r for r in rows}.values())
        top = sorted(rows, key=lambda r: (-r[2], -r[4]))[:25]
        titles = {(d, x): t for _i, d, x, _j, t, _y in laws}
        print(f"read {texts} provision texts of {len(laws)} released laws in {time.time() - started:.0f}s; "
              f"{sum(1 for r in rows if r[2])} laws cited by at least one other law")
        for d, x, n, c, e in top:
            print(f"  {n:5d} laws  {c:6d} citations  {e:3d} edges  {titles[(d, x)][:70]}")
        if a.apply:
            cur.execute("DELETE FROM law_citation_count")
            cur.executemany("""INSERT INTO law_citation_count (document_id, expression_ordinal, cited_by_laws,
                                                               citations, edges_in, method)
                               VALUES (%s,%s,%s,%s,%s,%s)""", [r + (METHOD,) for r in rows])
            conn.commit()
            print(f"recorded {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
