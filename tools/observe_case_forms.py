"""Observe how a court's headers print each case type, from an archive whose manifest records each file's case number
(D-138; the 0124/0126 practice, made reproducible).

    python tools/observe_case_forms.py ARCHIVE MANIFEST_MEMBER [--every N] [--out FILE]

For each file the manifest lists (matched by sha256), the case number and year the manifest records ('Const. P.
6005/2026 (D.B.)') are looked for in the first page of the file's own text; the words printed just before that
number are the printed form of the case type in this court's headers ('CP No.D-6005 of 2026' gives 'cp'). Forms are
folded as case_type.printed_forms are (lowercase, punctuation to single spaces) and tallied under the manifest's own
type prefix, with the bench letter printed before the number ('D-', 'S-') counted apart. Nothing is written to the
database; the output is the evidence a case-type migration cites.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import re
import sys
import zipfile

import pymupdf


def fold(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split())


def manifest_type(case_no: str) -> tuple[str, str, str] | None:
    """('const p', '6005', '2026') from 'Const. P. 6005/2026 (D.B.) Sindh High Court, Karachi'"""
    m = re.match(r"\s*(.*?)\s*(?:No\.?\s*)?([A-Z]-)?(\d+)\s*/\s*(\d{4})", case_no or "")
    if not m:
        return None
    return fold(re.sub(r"[^A-Za-z() ]", " ", m.group(1))), m.group(3), m.group(4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("manifest")
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--out")
    a = ap.parse_args()
    pymupdf.TOOLS.mupdf_display_errors(False)
    z = zipfile.ZipFile(a.archive)
    rows = list(csv.DictReader(io.StringIO(z.read(a.manifest).decode("utf-8", "replace"))))
    by_sha = {(r.get("sha256") or "").lower(): r for r in rows if r.get("sha256")}
    members = [n for n in z.namelist() if n.lower().endswith(".pdf")][::a.every]
    forms: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    benches: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    seen = found = 0
    for n in members:
        data = z.read(n)
        r = by_sha.get(hashlib.sha256(data).hexdigest())
        mt = manifest_type(r["case_no"]) if r else None
        if not mt:
            continue
        kind, number, year = mt
        try:
            text = pymupdf.open(stream=data, filetype="pdf")[0].get_text()
        except Exception:                                       # noqa: BLE001
            continue
        seen += 1
        t = " ".join(text.split())[:2500]
        # the number as printed, with an optional bench letter, then its year within a few characters
        m = re.search(r"([A-Za-z][A-Za-z.()&,\s/-]{1,70}?)\s*(?:No|NO|no|Nos|NOS)?\s*[.:]?\s*([A-Z])?\s*-?\s*0*"
                      + re.escape(number) + r"(?!\d)\s*(?:of|OF|/|-)\s*" + year[:2] + r"?" + year[2:], t)
        if not m:
            continue
        found += 1
        words = fold(m.group(1)).split()
        form = " ".join(words[-5:])                             # the type's words just before the number
        forms[kind][form] += 1
        benches[kind][m.group(2) or "-"] += 1
    out = {k: dict(forms=v.most_common(25), bench=dict(benches[k])) for k, v in
           sorted(forms.items(), key=lambda kv: -sum(kv[1].values()))}
    print(f"files with a manifest case number: {seen}; the number found printed in the header: {found}")
    for k, v in list(out.items())[:45]:
        print(f"[{k}] bench {v['bench']}")
        for f, c in v["forms"][:8]:
            print(f"     {c:5}  {f}")
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
