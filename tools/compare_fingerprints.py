"""Compare two fingerprint passes and rule on whether the change is safe.

The session's costliest mistake was measuring the wrong thing: `seg.missing` is
the segmenter's own view of unmatched labels, while the RELEASE GATE counts
contents rows left without a provision. A change once measured "zero
regressions" on the first and cost 56 release instruments on the second. Both
are reported here, and `unlinked` is the one that decides.
"""
from __future__ import annotations

import csv
import sys

FIELDS = ("sections", "provisions", "missing_toc", "stranded", "stranded_chars",
          "demoted", "footnote_blocks", "unlinked")


def load(path: str) -> dict[int, dict]:
    rows = {}
    for row in csv.DictReader(open(path, encoding="utf-8"), delimiter="\t"):
        doc = row.get("document")
        if not doc or not doc.isdigit():
            continue
        if not all(str(row.get(f, "")).lstrip("-").isdigit() for f in FIELDS):
            continue
        rows[int(doc)] = {f: int(row[f]) for f in FIELDS}
    return rows


def main() -> int:
    before = load(sys.argv[1])   # guard OFF
    after = load(sys.argv[2])    # guard ON
    shared = sorted(set(before) & set(after))
    print(f"documents compared      : {len(shared)}")
    print(f"only in one pass (error): "
          f"{len(set(before) ^ set(after))}")

    totals = {f: [0, 0] for f in FIELDS}
    moved, better, worse = [], [], []
    for doc in shared:
        b, a = before[doc], after[doc]
        for f in FIELDS:
            totals[f][0] += b[f]
            totals[f][1] += a[f]
        if b == a:
            continue
        moved.append(doc)
        # The gate counts unlinked contents rows; fewer is better.
        if a["unlinked"] < b["unlinked"] or (a["unlinked"] == b["unlinked"]
                                             and a["demoted"] < b["demoted"]):
            better.append((doc, b, a))
        elif a["unlinked"] > b["unlinked"] or a["stranded"] > b["stranded"]:
            worse.append((doc, b, a))

    print(f"documents whose output moved: {len(moved)}")
    print(f"  improved : {len(better)}")
    print(f"  REGRESSED: {len(worse)}")
    print()
    print(f"{'field':<16}{'before':>12}{'after':>12}{'delta':>12}")
    for f in FIELDS:
        b, a = totals[f]
        mark = "" if b == a else ("  <-- " + ("better" if (
            (f in ("missing_toc", "stranded", "stranded_chars", "demoted",
                   "unlinked") and a < b)
            or (f in ("sections", "provisions") and a > b)) else "CHECK"))
        print(f"{f:<16}{b:>12}{a:>12}{a - b:>12}{mark}")

    if worse:
        print("\nregressions (document, field: before -> after):")
        for doc, b, a in worse[:25]:
            delta = ", ".join(f"{f} {b[f]}->{a[f]}"
                              for f in FIELDS if b[f] != a[f])
            print(f"  doc {doc:<6} {delta}")
        with open(".probe_regressed.txt", "w", encoding="utf-8") as fh:
            fh.write(",".join(str(d) for d, _b, _a in worse))
        print(f"\n  wrote .probe_regressed.txt ({len(worse)} documents)")

    if better:
        print("\ntop improvements:")
        for doc, b, a in sorted(
                better, key=lambda t: t[1]["unlinked"] - t[2]["unlinked"],
                reverse=True)[:15]:
            delta = ", ".join(f"{f} {b[f]}->{a[f]}"
                              for f in FIELDS if b[f] != a[f])
            print(f"  doc {doc:<6} {delta}")
        with open(".probe_improved.txt", "w", encoding="utf-8") as fh:
            fh.write(",".join(str(d) for d, _b, _a in better))
        print(f"\n  wrote .probe_improved.txt ({len(better)} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
