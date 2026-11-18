"""Build and keep the chunk table: offsets into every released provision version (D-095; docs/03 §3, docs/02 §5.3).

    python -m nizam.workers.chunk            # dry run: what would be added and removed
    python -m nizam.workers.chunk --apply    # write
    python -m nizam.workers.chunk --apply --rebuild   # TRUNCATE and build from nothing (a chunker or model change)
    ./nz chunk [--apply] [--rebuild]

The boundary is the release (docs/04 corpus boundary): chunks are made only from v_release_provision_version, and a
chunk whose version left the release (a replay retires versions), whose chunker is not the current one, or whose
context prefix no longer matches the tree (a corrected title or heading) is removed and, if its version is still
released, rebuilt. Idempotent: a second run with nothing changed writes nothing. Spans come from
nizam.storage.chunking (pure, tested); the bounds trigger on chunk refuses a span past its version's text.
"""
from __future__ import annotations

import argparse
import collections
import time

from nizam.storage.chunking import CHUNKER, Node, context_prefix, spans
from nizam.storage.db import connect

_DIVISIONS = ("chapter", "part")
_QUALIFIES = ("proviso", "explanation", "illustration", "exception")


def _tree(cur) -> tuple[dict, dict]:
    """released provisions {id: (parent_id, kind, label, heading, instrument_id)}, instrument titles {id: title}"""
    cur.execute("""SELECT p.id, p.parent_id, p.kind::text, p.label, p.heading, p.instrument_id
                     FROM v_release_provision p""")
    prov = {r[0]: r[1:] for r in cur.fetchall()}
    cur.execute("""SELECT id, coalesce(nullif(display_title, ''), short_title) FROM v_release_instrument""")
    titles = {r[0]: r[1] or "" for r in cur.fetchall()}
    return prov, titles


def _qualified_openings(cur, prov: dict) -> dict:
    """{parent provision id: its text's opening words} for the parents of provisos, Explanations, illustrations and
    exceptions -- the rule each qualifies (docs/02 §5.3). The parent's newest released version; context only."""
    parents = {v[0] for v in prov.values() if v[1] in _QUALIFIES and v[0] is not None}
    if not parents:
        return {}
    cur.execute("""SELECT DISTINCT ON (provision_id) provision_id, left(text_normalised, 160)
                     FROM v_release_provision_version WHERE provision_id = ANY(%s)
                    ORDER BY provision_id, lower(validity) DESC NULLS LAST""", (list(parents),))
    return {r[0]: r[1] for r in cur.fetchall()}


def _prefix(pid, prov: dict, titles: dict, openings: dict, memo: dict) -> str:
    if pid in memo:
        return memo[pid]
    chain, division, cur_id = [], None, pid
    while cur_id is not None and cur_id in prov:
        parent, kind, label, heading, inst = prov[cur_id]
        if kind in _DIVISIONS:
            division = division or heading
        chain.append(Node(kind, label or "", heading))
        cur_id = parent
    chain.reverse()
    parent, kind, _l, _h, inst = prov[pid]
    p = context_prefix(titles.get(inst, ""), division, chain,
                       qualifies=openings.get(parent) if kind in _QUALIFIES else None)
    memo[pid] = p
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rebuild", action="store_true", help="TRUNCATE chunk first (with --apply)")
    a = ap.parse_args()
    t0 = time.time()
    stats = collections.Counter()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET max_parallel_workers_per_gather = 2")
        prov, titles = _tree(cur)
        openings = _qualified_openings(cur, prov)
        memo: dict = {}
        if a.rebuild and a.apply:
            cur.execute("TRUNCATE chunk")
        elif a.rebuild:
            print("  --rebuild without --apply: a dry run does not truncate, so it shows only today's increment")
        # what exists: per version, its chunker and its seq-0 prefix
        cur.execute("SELECT version_id, chunker, context_prefix FROM chunk WHERE seq = 0")
        existing = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        cur.execute("SELECT id, provision_id FROM v_release_provision_version")
        released = dict(cur.fetchall())
        stale = [v for v, (chunker, pfx) in existing.items()
                 if v not in released or chunker != CHUNKER
                 or pfx != _prefix(released[v], prov, titles, openings, memo)]
        stats["versions released"] = len(released)
        stats["versions chunked before"] = len(existing)
        stats["versions removed (left release, old chunker, or stale context)"] = len(stale)
        if stale and a.apply:
            for i in range(0, len(stale), 20000):
                cur.execute("DELETE FROM chunk WHERE version_id = ANY(%s)", (stale[i:i + 20000],))
        stale_set = set(stale)
        todo = [v for v in released if v not in existing or v in stale_set]
        stats["versions to chunk"] = len(todo)
        # spans are computed from the text, read in batches; each batch is read first, then copied (a connection
        # cannot run a query while a COPY is open on it)
        for i in range(0, len(todo), 20000):
            cur.execute("SELECT id, provision_id, text_normalised FROM provision_version WHERE id = ANY(%s)",
                        (todo[i:i + 20000],))
            rows = []
            for vid, pid, text in cur.fetchall():
                sp = spans(text or "")
                if not sp:
                    stats["versions with no text (no chunk)"] += 1
                    continue
                pfx = _prefix(pid, prov, titles, openings, memo)
                rows.extend((vid, seq, s.start, s.end, pfx, CHUNKER) for seq, s in enumerate(sp))
                stats["versions in more than one chunk"] += len(sp) > 1
            stats["chunks written"] += len(rows)
            if a.apply and rows:
                with cur.copy("COPY chunk (version_id, seq, char_start, char_end, context_prefix, chunker) "
                              "FROM STDIN") as cp:
                    for row in rows:
                        cp.write_row(row)
        if not a.apply:
            conn.rollback()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"{'applied' if a.apply else 'dry run (nothing written); pass --apply'} in {time.time() - t0:.0f}s "
          f"({CHUNKER})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
