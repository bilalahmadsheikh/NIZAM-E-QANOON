"""textlayer_check.py : score Urdu page readings against the PDF's own text layer (read-only).

The Sindh Code Urdu PDFs (Jameel Noori Nastaleeq) have a text layer whose glyph clusters map to their letters in a
scrambled ORDER ('سندھ' -> 'دنسھ', '2018' -> '8102') but -- this is what the check rests on -- with the right letters.
So the multiset of letters on a page is known exactly from the text layer even though the text is not. A reading
that adds, drops or substitutes letters moves away from that multiset; a reading that matches it letter for letter
can still reorder letters within a word, which only a reader comparing it with the image can catch.

    python tools/urdu/textlayer_check.py PDF READ.json          # one file: per-page, per-reader scores
    python tools/urdu/textlayer_check.py --dir OUT --pdfs DIR   # every read.json under OUT, PDFs found in DIR

Score per page and reader: letter recall and precision against the text layer, F1 of the two, and the digit
multiset agreement (digits are scrambled in order too: '8102' still holds 2, 0, 1, 8).
Letters compared: Arabic-script letters after NFKC (presentation forms folded), with the text layer's own fixed
substitutions folded on both sides (ۃ/ة -> ت: the layer writes ت for the round ta; superscript alif -> ا, as the layer writes it; ي/ى -> ی, ك -> ک, ه -> ہ).
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

FOLD = str.maketrans({"ۃ": "ت", "ة": "ت", "ي": "ی", "ى": "ی", "ك": "ک", "ه": "ہ", "ۂ": "ہ", "ۓ": "ے", "أ": "ا",
                      "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ی", "ٰ": "ا"})
ARABIC = re.compile(r"[ؠ-يٮ-ۓەۮۯۺ-ۿݐ-ݿ]")
DIGIT_MAP = {**{chr(0x0660 + i): str(i) for i in range(10)}, **{chr(0x06F0 + i): str(i) for i in range(10)}}


def letters(text: str) -> collections.Counter:
    t = unicodedata.normalize("NFKC", text).translate(FOLD)
    return collections.Counter(ARABIC.findall(t))


def digits(text: str) -> collections.Counter:
    t = "".join(DIGIT_MAP.get(c, c) for c in unicodedata.normalize("NFKC", text))
    return collections.Counter(c for c in t if c.isascii() and c.isdigit())


def prf(ref: collections.Counter, got: collections.Counter) -> dict:
    inter = sum((ref & got).values()); r = sum(ref.values()); g = sum(got.values())
    rec = inter / r if r else (1.0 if not g else 0.0)
    pre = inter / g if g else (1.0 if not r else 0.0)
    return {"recall": round(rec, 4), "precision": round(pre, 4),
            "f1": round(2 * rec * pre / (rec + pre), 4) if rec + pre else 0.0, "ref": r, "got": g}


def text_layer(pdf: Path) -> dict[int, str]:
    import fitz  # PyMuPDF
    with fitz.open(pdf) as d:
        return {i + 1: d[i].get_text("text") for i in range(len(d))}


def score(pdf: Path, read: dict) -> dict:
    layer = text_layer(pdf)
    out = {}
    for n, pg in sorted(read.get("pages", {}).items(), key=lambda kv: int(kv[0])):
        ref = layer.get(int(n), "")
        row = {}
        for reader in ("qaari", "qwen3"):
            if reader in pg:
                txt = "\n".join(pg[reader])
                row[reader] = {"letters": prf(letters(ref), letters(txt)), "digits": prf(digits(ref), digits(txt))}
        out[int(n)] = row
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?"); ap.add_argument("read", nargs="?")
    ap.add_argument("--dir"); ap.add_argument("--pdfs")
    ap.add_argument("--json", help="write all scores here")
    a = ap.parse_args()
    jobs = []
    if a.dir:
        pdfs = {p.stem: p for p in Path(a.pdfs).glob("**/*.pdf")}
        for r in sorted(Path(a.dir).glob("**/read.json")):
            stem = r.parent.name
            if stem.endswith("-UR") and stem in pdfs:
                jobs.append((pdfs[stem], r))
    else:
        jobs.append((Path(a.pdf), Path(a.read)))
    allres, agg = {}, collections.defaultdict(list)
    for pdf, r in jobs:
        s = score(pdf, json.loads(Path(r).read_text(encoding="utf-8")))
        allres[pdf.stem] = s
        for n, row in s.items():
            line = [f"{pdf.stem} p{n}"]
            for reader, v in row.items():
                agg[reader].append(v["letters"]["f1"])
                line.append(f"{reader} F1 {v['letters']['f1']:.3f} (R {v['letters']['recall']:.3f} P "
                            f"{v['letters']['precision']:.3f}, {v['letters']['ref']} letters) digits F1 {v['digits']['f1']:.2f}")
            print("  ".join(line))
    for reader, xs in agg.items():
        xs = sorted(xs)
        print(f"== {reader}: {len(xs)} pages, median letter F1 {xs[len(xs) // 2]:.3f}, "
              f">=0.98: {sum(x >= 0.98 for x in xs)}, <0.90: {sum(x < 0.90 for x in xs)}")
    if a.json:
        Path(a.json).write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
