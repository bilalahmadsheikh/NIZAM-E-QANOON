"""L1 extraction, lane E4 with a cloud reader -- Google Document AI's OCR processor.

Document 02 §4 fixes what lane E4 must deliver (a 300 DPI-quality reading, script-aware, accepted on legal-token
checks with review below threshold); it does not fix the engine. D-114 adds Document AI beside Tesseract because the
owner asked (22 Nov 2026) for the scans held back by D-034 to be read with it and released; Tesseract stays as the
independent second reader. This module keeps the lane's contract unchanged:

  * the output is the same `ExtractedDocument` as `ocr.ocr_pdf`: lane E4, a real confidence on every block,
    coordinates in PDF points of the original page, reading order dense across the whole document;
  * the metadata keys `verify_ocr` reads (`ocr_language`, `ocr_mean_confidence`, `ocr_words`, `needs_review`)
    mean the same thing;
  * the extractor string names the processor version, so a re-read by a newer model is a new revision, never a
    silent overwrite.

Two parts, kept apart so the mapping can be tested without a network:

  `document_from_responses()`  pure: the original PDF's page rectangles plus the processor's JSON responses in,
                               an `ExtractedDocument` out;
  `DocAIClient`                the network: splits a PDF into parts the online endpoint accepts (15 pages,
                               measured limit 21 Nov 2026), posts each, and keeps every raw response on disk
                               (gzip JSON, one file per part, named by the PDF's SHA-256 and the processor version)
                               so a re-run reads the stored response instead of paying for the page again, and a
                               better mapping can be replayed over the same evidence -- the `raw_note` rule of
                               docs/02 §6 applied to OCR.

Credentials are Application Default Credentials (`gcloud auth application-default login`, or
GOOGLE_APPLICATION_CREDENTIALS naming a service-account key). Nothing about the user or the project is sent beyond
the PDF bytes and the processor name.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import random
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from nizam.shared.corpus_types import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionRejected,
)

# The processor the owner created on 21 Nov 2026 (Document OCR, region us). Override with NIZAM_DOCAI_PROCESSOR.
DEFAULT_PROCESSOR = "projects/189384242594/locations/us/processors/537ddf134d0c28d0"
PAGES_PER_REQUEST = 15          # online limit for Enterprise Document OCR (cloud.google.com/document-ai/limits)
MAX_REQUEST_BYTES = 18_000_000  # under the 20 MB the processor page states (the limits page says 40 MB)
REVIEW_THRESHOLD = 0.70         # the same review line as Tesseract's lane (ocr.REVIEW_THRESHOLD)
MIN_WORDS_PER_PAGE = 3          # as ocr.MIN_WORDS_PER_PAGE: a page that yields almost nothing was not read

_ARABIC = re.compile(r'[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]')


# --------------------------------------------------------------------------------------------- the pure mapping

def _segments_text(text: str, layout: dict) -> str:
    """The text a layout anchors, from the response's document text.

    Indices are JSON strings (int64), and proto3 JSON omits a zero startIndex.
    """
    anchor = (layout or {}).get("textAnchor") or {}
    out = []
    for seg in anchor.get("textSegments") or []:
        start = int(seg.get("startIndex", 0) or 0)
        end = int(seg.get("endIndex", 0) or 0)
        out.append(text[start:end])
    return "".join(out)


def _box(layout: dict, dim: dict, width_pt: float, height_pt: float) -> tuple[float, float, float, float] | None:
    """The layout's bounding box in PDF points of the original page.

    normalizedVertices are 0..1 of the page image; vertices are pixels of the image the processor saw, scaled by
    page.dimension. Either way the result is in the same space lane E2 stores, so a citation points at the same
    rectangle whichever lane read the page.
    """
    poly = (layout or {}).get("boundingPoly") or {}
    norm = poly.get("normalizedVertices") or []
    if norm:
        xs = [float(v.get("x", 0.0)) * width_pt for v in norm]
        ys = [float(v.get("y", 0.0)) * height_pt for v in norm]
    else:
        verts = poly.get("vertices") or []
        dw = float((dim or {}).get("width") or 0)
        dh = float((dim or {}).get("height") or 0)
        if not verts or not dw or not dh:
            return None
        xs = [float(v.get("x", 0)) / dw * width_pt for v in verts]
        ys = [float(v.get("y", 0)) / dh * height_pt for v in verts]
    x0, x1 = max(min(xs), 0.0), min(max(xs), width_pt)
    y0, y1 = max(min(ys), 0.0), min(max(ys), height_pt)
    return (x0, y0, x1, y1)


def _inside(box: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return outer[0] - 1 <= cx <= outer[2] + 1 and outer[1] - 1 <= cy <= outer[3] + 1


def _language(codes: dict[str, float]) -> str:
    """'urd' when Urdu (or another Arabic-script language) carries most of the detected weight, else 'eng'."""
    if not codes:
        return "eng"
    arabic = sum(w for c, w in codes.items() if c.split("-")[0] in {"ur", "sd", "ar", "fa", "ps"})
    return "urd" if arabic > sum(codes.values()) / 2 else "eng"


def document_from_responses(page_rects: list[tuple[float, float]], responses: list[dict], sha256: str, *,
                            processor_version: str, publication_role: str = "code_portal") -> ExtractedDocument:
    """Map Document AI responses for consecutive parts of one PDF onto the lane-E4 document.

    `page_rects` is (width, height) in points for every page of the ORIGINAL PDF, in order; `responses` are the
    processor's `document` objects for the parts, in order, together covering every page once. Each paragraph is
    a block (the grain Tesseract's (block, paragraph) grouping gives the same lane); its confidence is the mean
    of its tokens', and the document's mean confidence is token-weighted, as the Tesseract lane's is word-weighted.
    """
    n_pages = len(page_rects)
    pages: list[ExtractedPage] = []
    blocks: list[ExtractedBlock] = []
    order = 0
    total_chars = 0
    empty_pages = 0
    conf_sum = 0.0
    word_total = 0
    lang_weight: dict[str, float] = {}

    page_cursor = 0
    for resp in responses:
        text = resp.get("text") or ""
        for page in resp.get("pages") or []:
            if page_cursor >= n_pages:
                raise ExtractionRejected(f"{sha256[:12]}: the responses hold more pages than the PDF ({n_pages})")
            page_no = page_cursor + 1
            width_pt, height_pt = page_rects[page_cursor]
            page_cursor += 1
            dim = page.get("dimension") or {}

            for lang in page.get("detectedLanguages") or []:
                code = lang.get("languageCode") or ""
                if code:
                    lang_weight[code] = lang_weight.get(code, 0.0) + float(lang.get("confidence") or 0.0)

            tokens = []
            for tok in page.get("tokens") or []:
                lay = tok.get("layout") or {}
                box = _box(lay, dim, width_pt, height_pt)
                if box is None:
                    continue
                tok_text = _segments_text(text, lay).strip()
                if tok_text:
                    tokens.append((box, float(lay.get("confidence") or 0.0)))

            page_blocks: list[ExtractedBlock] = []
            order_before = order
            page_words = 0
            page_conf = 0.0
            for block_no, para in enumerate(page.get("paragraphs") or []):
                lay = para.get("layout") or {}
                raw = _segments_text(text, lay)
                # The processor ends each line with '\n'; keep the line breaks (the segmenter reads them) and drop
                # the trailing one, as the Tesseract lane joins lines with '\n' and adds none at the end.
                body = "\n".join(line.strip() for line in raw.strip("\n").split("\n"))
                body = unicodedata.normalize("NFC", body).strip()
                box = _box(lay, dim, width_pt, height_pt)
                if not body or box is None:
                    continue
                mine = [c for b, c in tokens if _inside(b, box)]
                if mine:
                    conf = sum(mine) / len(mine)
                    words = len(mine)
                else:
                    conf = float(lay.get("confidence") or 0.0)
                    words = max(len(body.split()), 1)
                page_words += words
                page_conf += conf * words
                page_blocks.append(ExtractedBlock(
                    page_no=page_no, block_no=block_no, reading_order=order,
                    x0=box[0], y0=box[1], x1=box[2], y1=box[3], text=body,
                    script="arabic" if _ARABIC.search(body) else "latin",
                    confidence=round(min(max(conf, 0.0), 1.0), 3),
                ))
                order += 1

            if page_words < MIN_WORDS_PER_PAGE:
                # As the Tesseract lane: an unread page contributes nothing and gives its reading-order slots back,
                # so reading_order stays dense.
                empty_pages += 1
                page_blocks = []
                order = order_before
            else:
                conf_sum += page_conf
                word_total += page_words
                blocks.extend(page_blocks)
            chars = sum(len(b.text) for b in page_blocks)
            total_chars += chars
            pages.append(ExtractedPage(page_no=page_no, width=float(width_pt), height=float(height_pt),
                                       char_count=chars, lane="E4"))

    if page_cursor != n_pages:
        raise ExtractionRejected(f"{sha256[:12]}: the responses cover {page_cursor} of {n_pages} pages")
    if word_total == 0:
        raise ExtractionRejected(f"{sha256[:12]}: Document AI read no words -- the scan is not readable")

    mean_conf = conf_sum / word_total
    lang = _language(lang_weight)
    meta = {
        "ocr_engine": "google-documentai",
        "ocr_processor_version": processor_version,
        "ocr_language": lang,
        "ocr_detected_languages": {k: round(v, 3) for k, v in sorted(lang_weight.items())},
        "ocr_mean_confidence": round(mean_conf, 4),
        "ocr_words": word_total,
        "ocr_pages_at_fallback_dpi": 0,
        "ocr_pages_timed_out": 0,
        "needs_review": mean_conf < REVIEW_THRESHOLD,
    }
    return ExtractedDocument(
        sha256=sha256,
        language="ur" if lang == "urd" else "en",
        publication_role=publication_role,
        page_count=n_pages,
        char_count=total_chars,
        printable_ratio=round(min(max(mean_conf, 0.0), 1.0), 4),   # as lane E4: the mean word confidence
        empty_pages=empty_pages,
        lane="E4",
        extractor=f"google-documentai-ocr/{processor_version}+pymupdf-{pymupdf.__version__}",
        extractor_config={"engine": "google-documentai", "processor_version": processor_version,
                          "pages_per_request": PAGES_PER_REQUEST, "block": "paragraph",
                          "confidence": "token-mean"},
        pdf_metadata=meta,
        pages=pages,
        blocks=blocks,
    )


# ------------------------------------------------------------------------------------------------- the network

def split_pdf(data: bytes, pages_per_part: int = PAGES_PER_REQUEST,
              max_bytes: int = MAX_REQUEST_BYTES) -> tuple[list[tuple[float, float]], list[bytes]]:
    """The original page rectangles, and the PDF cut into consecutive parts the online endpoint accepts.

    A part that comes out over `max_bytes` is halved again; a single page over the limit is refused, because the
    online endpoint would refuse it too.
    """
    src = pymupdf.open(stream=data, filetype="pdf")
    try:
        if src.page_count == 0:
            raise ExtractionRejected("no pages")
        rects = [(float(p.rect.width), float(p.rect.height)) for p in src]

        def cut(first: int, last: int) -> list[bytes]:
            part = pymupdf.open()
            part.insert_pdf(src, from_page=first, to_page=last)
            blob = part.tobytes(garbage=3, deflate=True)
            part.close()
            if len(blob) <= max_bytes:
                return [blob]
            if first == last:
                raise ExtractionRejected(f"page {first + 1} alone is {len(blob)} bytes, over the online limit")
            mid = (first + last) // 2
            return cut(first, mid) + cut(mid + 1, last)

        parts: list[bytes] = []
        for first in range(0, src.page_count, pages_per_part):
            parts.extend(cut(first, min(first + pages_per_part, src.page_count) - 1))
        return rects, parts
    finally:
        src.close()


@dataclass
class DocAIClient:
    """Posts PDF parts to one Document AI processor and keeps every response.

    `cache_dir/<processor version>/<sha256>/<part>.json.gz` holds the processor's `document` object for each part;
    a stored part is never requested again.
    """
    processor: str = os.environ.get("NIZAM_DOCAI_PROCESSOR", DEFAULT_PROCESSOR)
    cache_dir: Path = Path(os.environ.get("NIZAM_DOCAI_CACHE", "/mnt/e/nizam-data/ocr/docai"))
    timeout: int = 300
    retries: int = 6

    def __post_init__(self) -> None:
        m = re.fullmatch(r"projects/[^/]+/locations/([a-z0-9-]+)/processors/[^/]+", self.processor)
        if not m:
            raise ValueError(f"not a processor name: {self.processor!r}")
        self.endpoint = f"https://{m.group(1)}-documentai.googleapis.com/v1/{self.processor}"
        self._session = None
        self._version: str | None = None

    # The session is created lazily so the pure parts of this module import without google-auth installed.
    def _authed(self):
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            self._session = AuthorizedSession(creds)
        return self._session

    def processor_version(self) -> str:
        """The version the processor serves by default (its last path segment), read once per client."""
        if self._version is None:
            r = self._request("GET", self.endpoint)
            name = r.get("defaultProcessorVersion") or ""
            self._version = name.rsplit("/", 1)[-1] or "unknown"
        return self._version

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        delay = 2.0
        for attempt in range(self.retries + 1):
            resp = self._authed().request(method, url, json=body, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                time.sleep(delay + random.random())
                delay = min(delay * 2, 60)
                continue
            raise RuntimeError(f"Document AI {method} {resp.status_code}: {resp.text[:300]}")
        raise RuntimeError("unreachable")

    def _part_path(self, sha256: str, index: int) -> Path:
        return self.cache_dir / self.processor_version() / sha256 / f"{index:04d}.json.gz"

    def read_part(self, sha256: str, index: int, part: bytes) -> dict:
        path = self._part_path(sha256, index)
        if path.exists():
            return json.loads(gzip.decompress(path.read_bytes()))
        body = {"rawDocument": {"mimeType": "application/pdf",
                                "content": base64.b64encode(part).decode("ascii")},
                "imagelessMode": True}
        doc = self._request("POST", f"{self.endpoint}:process", body).get("document") or {}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(json.dumps(doc, ensure_ascii=False).encode("utf-8")))
        tmp.replace(path)
        return doc

    def ocr_pdf(self, data: bytes, sha256: str, *, publication_role: str = "code_portal") -> ExtractedDocument:
        rects, parts = split_pdf(data)
        responses = [self.read_part(sha256, i, part) for i, part in enumerate(parts)]
        return document_from_responses(rects, responses, sha256, processor_version=self.processor_version(),
                                       publication_role=publication_role)
