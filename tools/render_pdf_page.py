"""Render one landed PDF page for direct evidence review."""
from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("page", type=int, help="one-based page number")
    ap.add_argument("output", type=Path)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument(
        "--clip",
        help="optional PDF-point rectangle x0,y0,x1,y1 for high-resolution review",
    )
    args = ap.parse_args()
    with pymupdf.open(args.pdf) as pdf:
        if not 1 <= args.page <= pdf.page_count:
            ap.error(f"page must be within 1..{pdf.page_count}")
        clip = None
        if args.clip:
            try:
                values = [float(value) for value in args.clip.split(",")]
            except ValueError:
                ap.error("--clip values must be numbers")
            if len(values) != 4:
                ap.error("--clip requires x0,y0,x1,y1")
            clip = pymupdf.Rect(*values)
            if clip.is_empty or clip.is_infinite:
                ap.error("--clip must be a finite, non-empty rectangle")
        pixmap = pdf[args.page - 1].get_pixmap(
            dpi=args.dpi, alpha=False, clip=clip,
        )
        pixmap.save(args.output)
    print(f"rendered page {args.page} at {args.dpi} DPI -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
