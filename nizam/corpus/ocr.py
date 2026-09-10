"""L1 extraction, lane E4 — Document 02 §4: scanned PDFs.

    E4 | Scanned PDF | 300 DPI render, deskew, denoise, script-aware OCR;
         English and Urdu/Sindhi models selected per region
         Acceptance: legal-token checks plus human review below threshold

Pure like `extract`: bytes in, an `ExtractedDocument` out. No database.

What OCR produces is *not* the same kind of data as a text layer, and the code
is careful never to let the two be confused downstream:

  * every block carries a real confidence, where lane E2 stores None because a
    text layer is not a guess;
  * the document and its pages are labelled E4;
  * documents whose mean confidence falls below the review threshold are
    reported so a person can look, rather than silently joining the corpus.

Accuracy is bounded by the scan. A clean 300 DPI page of printed English gets
into the high nineties; a fourth-generation photocopy of a 1975 Gazette does not,
whatever settings are used. The confidence stored per block is what lets
retrieval and citation treat the two differently.
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import unicodedata

import pymupdf

from nizam.shared.corpus_types import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionRejected,
)

RENDER_DPI = 300          # §4 specifies 300 DPI
FALLBACK_DPI = 200        # retry at this if a page will not finish at 300

# Per page, and generous on purpose. Tesseract's cost is superlinear in the
# amount of ink on a page, so a dense Gazette scan takes far longer than a title
# page, and a loaded machine stretches both. A first run with a 180 s cap and
# five workers competing with another job for six cores timed out on every
# document -- the cap was measuring contention, not the document.
OCR_TIMEOUT = 900
OSD_TIMEOUT = 120

# Below this mean word confidence the document is flagged for human review
# rather than trusted. It does not reject: partial text from a poor scan is
# still better than nothing, provided nobody mistakes it for clean text.
REVIEW_THRESHOLD = 0.70

# A page that yields almost nothing is not a page we managed to read.
MIN_WORDS_PER_PAGE = 3

_ARABIC = re.compile(r'[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]')

# One thread per tesseract process, deliberately.
#
# Tesseract is built with OpenMP and by default grabs every core for a single
# page. Run five worker processes and you get ~30 threads fighting over six
# cores: measured load average 20.7, and documents taking three hours that
# should take well under one. Pinning each process to one thread turns that
# contention into real five-way parallelism, because the parallelism we want is
# across documents, not within a page.
_OCR_ENV = {**os.environ, "OMP_THREAD_LIMIT": "1", "OMP_NUM_THREADS": "1"}


def _tesseract(png: bytes, lang: str, dpi: int = RENDER_DPI,
               psm: int | None = None) -> str:
    """Run tesseract over one rendered page, returning its TSV output."""
    cmd = ["tesseract", "stdin", "stdout", "--dpi", str(dpi)]
    if psm is not None:
        cmd += ["--psm", str(psm)]
    cmd += ["-l", lang, "tsv"]
    out = subprocess.run(cmd, input=png, capture_output=True,
                         timeout=OCR_TIMEOUT, env=_OCR_ENV)
    if out.returncode != 0:
        raise ExtractionRejected(f"tesseract failed: {out.stderr.decode()[:200]}")
    return out.stdout.decode("utf-8", "replace")


def _ocr_page(page, lang: str) -> tuple[str, str | None, int]:
    """OCR one page, dropping to a lower resolution rather than losing it.

    A page that will not finish at 300 DPI is usually a very large or very dense
    scan. Half the pixels is a real quality cost, so it is a fallback and the
    resolution actually used is recorded per page -- silently degrading and not
    saying so would be worse than either outcome.
    """
    for dpi in (RENDER_DPI, FALLBACK_DPI):
        png = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY).tobytes("png")
        try:
            primary = _tesseract(png, lang, dpi)
            # PSM 3 is strong at page layout but repeatedly drops short labels
            # in the left margin of scanned statutes. PSM 6 sees those labels
            # by treating a legal page as one text region. Keep it as a second
            # independent reading; selection below is evidence-based per page.
            supplemental = None
            if lang == "eng":
                try:
                    supplemental = _tesseract(png, lang, dpi, psm=6)
                except subprocess.TimeoutExpired:
                    pass
            return primary, supplemental, dpi
        except subprocess.TimeoutExpired:
            if dpi == FALLBACK_DPI:
                raise
    raise AssertionError("unreachable")


def _detect_script(doc: pymupdf.Document, sample: int = 3) -> str:
    """Pick the OCR model from the page image, not from the filename.

    §4 wants the model selected by script. Orientation and script detection is a
    separate, cheap tesseract pass; running it on a few pages and taking the
    majority is far cheaper than per-page detection and is right for statutes,
    which do not change script partway through.
    """
    votes: list[str] = []
    for i in range(min(sample, doc.page_count)):
        try:
            png = doc[i].get_pixmap(dpi=150).tobytes("png")
            out = subprocess.run(
                ["tesseract", "stdin", "stdout", "--psm", "0", "-l", "osd"],
                input=png, capture_output=True, timeout=OSD_TIMEOUT, env=_OCR_ENV,
            ).stdout.decode("utf-8", "replace")
            m = re.search(r"Script:\s*(\S+)", out)
            if m:
                votes.append(m.group(1))
        except Exception:
            continue
    if votes and sum(1 for v in votes if v == "Arabic") > len(votes) / 2:
        return "urd"
    return "eng"


def _blocks_from_tsv(tsv: str, page_no: int, start_order: int,
                     scale: float) -> tuple[list[ExtractedBlock], int, float, int]:
    """Group tesseract's per-word rows into blocks, preserving coordinates.

    Coordinates are divided back by the render scale so they are in PDF points,
    the same space lane E2 stores. A citation must be able to point at the same
    rectangle whichever lane read the page.
    """
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE))
    grouped: dict[tuple, list[dict]] = {}
    for r in rows:
        try:
            if int(r["level"]) != 5:          # 5 = word
                continue
            conf = float(r["conf"])
        except (KeyError, ValueError, TypeError):
            continue
        text = (r.get("text") or "").strip()
        if not text or conf < 0:
            continue
        key = (int(r["block_num"]), int(r["par_num"]))
        grouped.setdefault(key, []).append(
            {"text": text, "conf": conf,
             "l": float(r["left"]), "t": float(r["top"]),
             "w": float(r["width"]), "h": float(r["height"]),
             "line": int(r["line_num"])})

    blocks: list[ExtractedBlock] = []
    order = start_order
    conf_sum = 0.0
    word_count = 0
    for block_no, (_, words) in enumerate(sorted(grouped.items())):
        lines: dict[int, list[dict]] = {}
        for w in words:
            lines.setdefault(w["line"], []).append(w)
        text = "\n".join(" ".join(w["text"] for w in lines[k]) for k in sorted(lines))
        text = unicodedata.normalize("NFC", text)
        x0 = min(w["l"] for w in words) / scale
        y0 = min(w["t"] for w in words) / scale
        x1 = max(w["l"] + w["w"] for w in words) / scale
        y1 = max(w["t"] + w["h"] for w in words) / scale
        mean_conf = sum(w["conf"] for w in words) / len(words) / 100.0
        conf_sum += sum(w["conf"] for w in words)
        word_count += len(words)
        blocks.append(ExtractedBlock(
            page_no=page_no, block_no=block_no, reading_order=order,
            x0=x0, y0=y0, x1=x1, y1=y1, text=text,
            script="arabic" if _ARABIC.search(text) else "latin",
            confidence=round(min(max(mean_conf, 0.0), 1.0), 3),
        ))
        order += 1
    return blocks, order, conf_sum, word_count


_LEGAL_ANCHOR = re.compile(r"(?m)^\s*\d{1,4}(?:\s*[-\u2013]\s*[A-Z]{1,3}|[A-Z]{0,3})\s*\.\s+[A-Z]")


def _legal_anchor_count(blocks: list[ExtractedBlock]) -> int:
    """Count provision-shaped line starts, not bare numbers in tables."""
    return sum(len(_LEGAL_ANCHOR.findall(block.text)) for block in blocks)


def _prefer_supplemental(primary: list[ExtractedBlock],
                         supplemental: list[ExtractedBlock],
                         primary_words: int, supplemental_words: int) -> bool:
    """Choose PSM 6 only when it recovers additional legal structure safely.

    More text alone is not enough: tables often become noisier in single-block
    mode. The alternate reading must recover at least one additional
    section-shaped line while retaining at least 85% of the primary words.
    """
    return (supplemental_words >= primary_words * 0.85
            and _legal_anchor_count(supplemental) > _legal_anchor_count(primary))


def ocr_pdf(data: bytes, sha256: str, *,
            language: str | None = None,
            publication_role: str = "code_portal") -> ExtractedDocument:
    """OCR one scanned PDF. Raises ExtractionRejected if nothing readable comes out."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        if doc.page_count == 0:
            raise ExtractionRejected(f"{sha256[:12]}: no pages")

        lang = language or _detect_script(doc)

        pages: list[ExtractedPage] = []
        blocks: list[ExtractedBlock] = []
        order = 0
        total_chars = 0
        empty_pages = 0
        conf_sum = 0.0
        word_total = 0

        dpis: list[int] = []
        timed_out = 0
        supplemental_pages = 0
        for index in range(doc.page_count):
            page = doc[index]
            page_no = index + 1
            try:
                tsv, supplemental_tsv, used_dpi = _ocr_page(page, lang)
            except subprocess.TimeoutExpired:
                # One unreadable page must not cost the other 161. Record it as
                # empty and carry on: doc 02 §4 routes per page for this reason.
                timed_out += 1
                dpis.append(0)
                empty_pages += 1
                rect = page.rect
                pages.append(ExtractedPage(
                    page_no=page_no, width=float(rect.width), height=float(rect.height),
                    char_count=0, lane="E4"))
                continue
            dpis.append(used_dpi)
            scale = used_dpi / 72.0
            # Remember where the counter was: if this page turns out to be
            # unreadable its blocks are discarded, and the counter has to go back
            # with them. Advancing past discarded blocks leaves holes in
            # reading_order, which breaks the density the whole ordering relies on
            # -- and it silently did, on two documents, before this line existed.
            order_before = order
            page_blocks, order, csum, wcount = _blocks_from_tsv(
                tsv, page_no, order, scale)
            if supplemental_tsv:
                alt_blocks, alt_order, alt_csum, alt_words = _blocks_from_tsv(
                    supplemental_tsv, page_no, order_before, scale)
                if _prefer_supplemental(page_blocks, alt_blocks, wcount, alt_words):
                    page_blocks, order = alt_blocks, alt_order
                    csum, wcount = alt_csum, alt_words
                    supplemental_pages += 1

            if wcount < MIN_WORDS_PER_PAGE:
                empty_pages += 1
                page_blocks = []
                order = order_before
            else:
                conf_sum += csum
                word_total += wcount
                blocks.extend(page_blocks)

            chars = sum(len(b.text) for b in page_blocks)
            total_chars += chars
            rect = page.rect
            pages.append(ExtractedPage(
                page_no=page_no, width=float(rect.width), height=float(rect.height),
                char_count=chars, lane="E4",
            ))

        if word_total == 0:
            raise ExtractionRejected(
                f"{sha256[:12]}: OCR produced no words at {RENDER_DPI} DPI with '{lang}' "
                f"-- the scan is not readable"
            )

        mean_conf = conf_sum / word_total / 100.0
        downgraded = sum(1 for d in dpis if d == FALLBACK_DPI)
        meta = {k: v for k, v in (doc.metadata or {}).items() if v}
        meta["ocr_language"] = lang
        meta["ocr_mean_confidence"] = round(mean_conf, 4)
        meta["ocr_words"] = word_total
        meta["ocr_pages_at_fallback_dpi"] = downgraded
        meta["ocr_pages_timed_out"] = timed_out
        meta["ocr_pages_psm6_selected"] = supplemental_pages
        meta["needs_review"] = (mean_conf < REVIEW_THRESHOLD
                                or timed_out > 0 or downgraded > 0)

        return ExtractedDocument(
            sha256=sha256,
            language="ur" if lang == "urd" else "en",
            publication_role=publication_role,
            page_count=doc.page_count,
            char_count=total_chars,
            # For OCR this is the mean word confidence, not a character-class
            # ratio. Same column, and both answer "how much should this be
            # trusted", but the lane says which meaning applies.
            printable_ratio=round(min(max(mean_conf, 0.0), 1.0), 4),
            empty_pages=empty_pages,
            lane="E4",
            extractor=f"tesseract-{_tesseract_version()}+pymupdf-{pymupdf.__version__}",
            extractor_config={"dpi": RENDER_DPI, "fallback_dpi": FALLBACK_DPI,
                              "lang": lang, "psm": "auto+6-legal-anchor-ensemble",
                              "colorspace": "gray",
                              "pages_at_fallback": downgraded,
                              "pages_timed_out": timed_out,
                              "pages_psm6_selected": supplemental_pages},
            pdf_metadata=meta,
            pages=pages,
            blocks=blocks,
        )
    finally:
        doc.close()


def _tesseract_version() -> str:
    try:
        out = subprocess.run(["tesseract", "--version"], capture_output=True, timeout=30)
        return out.stdout.decode().split()[1]
    except Exception:
        return "unknown"
