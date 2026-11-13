"""label_triage.py : classify released sections whose label disagrees with the number their first block prints.

Input: the instruments listed by tools/audit/label-disagrees-with-first-block.sql. For each, every released section is
read in PRINTED ORDER (first block's page, reading order) with its label and the number its first block opens with
('printed'). A flagged section is then:

  source_misprint   the printed run repeats a number (3, 3, 4, 5) and the labels continue the sequence through it
                    (3, 4, 5, 6): the source misprints, the label carries the true number. Correct as released per the
                    document-732 precedent (tools/detect_marginal_relabel.py: a misprinted number takes the number the
                    sequence and the contents give it). Needs no tree change -- only the evidence.
  fused_marker      printed = footnote marker (1-9) + label, and another section carries the printed number at its own
                    block: '14.' is marker 1 + section 4 (Land Acquisition Act 1894). Correct as released.
  mislabel          the printed numbers around it run cleanly and agree with their labels, but this section's label is
                    not its printed number, which no other section claims: the label is wrong (INV-1).
  shared_block      the section shares its first block with the section that carries the printed number: a pointer or
                    a split defect -- read.
  read              anything else.

Read-only. Writes OUT.csv (one row per flagged section with its neighbours) and prints the split.

    python tools/audit/label_triage.py DEFECTS.csv OUT.csv
DEFECTS.csv is .artifacts/a1-labels/defects.csv (export.sql beside it).
"""
from __future__ import annotations

import collections
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OPENER = re.compile(r"^\s*(?:\d{1,2}\[)?\s*(\d{1,4}[A-Z]?)\s*[.\]]")  # '1[5.' opens 5; '14.' stays 14


def num(s: str | None) -> int | None:
    m = re.match(r"^(\d+)", s or "")
    return int(m.group(1)) if m else None


def classify(seq: list[dict], i: int) -> str:
    """seq: one instrument's sections in printed order; i: index of the flagged one."""
    me = seq[i]
    L, P = me["label"], me["printed"]
    if "__p" in me.get("path", ""):
        # an owner-reviewed cited label (docs/SCHEMA.md 'Printed number markers', rule owner_cited_label): the label is
        # the number a lawyer cites, the print is on the path and rendered as '(printed N)'. Already adjudicated.
        return "owner_cited_label"
    others_with_P = [s for s in seq if s["label"] == P and s is not me]
    if others_with_P and any(s["first_block"] == me["first_block"] for s in others_with_P):
        return "shared_block"
    if (P and P.endswith(L) and len(P) > len(L) and P[:len(P) - len(L)].isdigit()
            and int(P[:len(P) - len(L)]) <= 9):
        # marker + label; if another section carries P it starts on its own block (shared_block returned above).
        # Without a rival, the original diagnostic's 'correct: fused marker' class (4237: '228.' = marker 2 + 28)
        return "fused_marker"
    # leading digit dropped by the reader: 117 printed '17', 118 printed '18' (9641) -- label continues neighbours
    if P and L.endswith(P) and len(L) > len(P) and others_with_P:
        prev_l = num(seq[i - 1]["label"]) if i > 0 else None
        if prev_l is not None and num(L) == prev_l + 1:
            return "label_fits_print_misread"
    # source misprint: somewhere before me (within 3 sections) the printed number repeats while labels step by one,
    # and from that repeat to me every section's label = printed + 1 (a constant offset of one introduced by the repeat)
    for j in range(max(1, i - 6), i + 1):
        a, b = seq[j - 1], seq[j]
        if (a["printed"] and a["printed"] == b["printed"] and num(b["label"]) is not None
                and num(a["label"]) is not None and num(b["label"]) == num(a["label"]) + 1):
            run = seq[j:i + 1]
            if all(num(s["label"]) is not None and num(s["printed"]) is not None
                   and num(s["label"]) == num(s["printed"]) + 1 for s in run):
                return "source_misprint"
    # offset run: this and an adjacent section both disagree by the SAME offset and their printed numbers are
    # consecutive -- a block of sections relabelled by position (3387: labels 5..9 hold printed 7..11)
    off = (num(L) - num(P)) if num(L) is not None and num(P) is not None else None
    for k in (i - 1, i + 1):
        if off and 0 <= k < len(seq):
            s = seq[k]
            if (num(s["label"]) is not None and num(s["printed"]) is not None and s["label"] != s["printed"]
                    and num(s["label"]) - num(s["printed"]) == off and abs(num(s["printed"]) - num(P)) == 1):
                return "offset_run"
    # mislabel: neighbours agree with their printed numbers, P is claimed by nobody else
    nb = [seq[k] for k in (i - 1, i + 1) if 0 <= k < len(seq)]
    if not others_with_P and nb and all(s["printed"] in (None, s["label"]) for s in nb):
        return "mislabel"
    # isolated misread: the LABEL continues its neighbours' labels (prev + 1 or next - 1) and every neighbour that
    # prints a number prints its own label -- only this block's printed digits disagree (9081: 4,5,6,[7 prints 4],8)
    prev = next((seq[k] for k in range(i - 1, -1, -1) if num(seq[k]["label"]) is not None), None)
    nxt = next((seq[k] for k in range(i + 1, len(seq)) if num(seq[k]["label"]) is not None), None)
    fits = ((prev is not None and num(L) == num(prev["label"]) + 1)
            or (nxt is not None and num(L) == num(nxt["label"]) - 1))
    if fits and all(s["printed"] in (None, s["label"]) for s in nb):
        return "label_fits_print_misread"
    return "read"


def main() -> int:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    flagged = list(csv.DictReader(src.open(encoding="utf-8")))
    inst = sorted({r["instrument_id"] for r in flagged})
    from nizam.storage.db import connect
    seqs = {}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT p.instrument_id::text, p.id::text, p.label, p.heading, p.first_block, tb.page_no, p.path::text,
                              tb.reading_order, tb.text
                         FROM provision p JOIN text_block tb ON tb.id = p.first_block
                        WHERE p.is_active AND p.kind = 'section' AND p.instrument_id = ANY(%s::uuid[])
                        ORDER BY p.instrument_id, tb.page_no, tb.reading_order, p.path""", (inst,))
        for iid, pid, label, heading, fb, page, path, ro, text in cur.fetchall():
            m = OPENER.match(text or "")
            seqs.setdefault(iid, []).append({"id": pid, "label": label, "heading": heading or "", "first_block": fb, "path": path,
                                             "page": page, "printed": m.group(1) if m else None,
                                             "opens": re.sub(r"\s+", " ", (text or ""))[:90]})
    rows, split = [], collections.Counter()
    for r in flagged:
        seq = seqs[r["instrument_id"]]
        i = next(k for k, s in enumerate(seq) if s["id"] == r["provision_id"])
        k = classify(seq, i)
        split[k] += 1
        ctx = " | ".join(f"{s['label']}:{s['printed']}" for s in seq[max(0, i - 3):i + 4])
        rows.append({**r, "class": k, "context_label_printed": ctx})
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for k, v in split.most_common():
        print(f"{v:4} {k}  ({len({r['instrument_id'] for r in rows if r['class'] == k})} instruments)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
