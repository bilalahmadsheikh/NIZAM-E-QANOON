"""Title-region text as the law is READ: extracted blocks with the observation's page-read corrections applied.

D-092 (18 Nov 2026). record_instrument_numbers, record_long_titles and record_enacted_dates read `text_block`
directly, so a law whose title page was read by hand (an OCR scan corrected page by page, D-076) had its number,
long title and enactment date taken from the raw OCR instead of from the reading. This module applies the same
approved parser-input corrections the segmenter applies (segmentation_curation_patch, through the segmenter's own
`_apply_curation_patches`), to the blocks a recorder reads.

  * Corrections are loaded once, for every observation (`load_corrections`).
  * Each is applied alone, to the recorder's window only. A correction whose block lies outside that window (a later
    page, or a block the window cut off) is not applied, never guessed. One that matches two blocks still fails closed,
    as in the segmenter.
  * Identity readings (before == after: structural readings) change nothing.
Extracted text is never altered; this is a derived copy.
"""
from __future__ import annotations

import collections

from nizam.corpus.segment import _apply_curation_patches


def load_corrections(cur) -> dict[int, list[dict]]:
    """{source_observation_id: [patch]} -- every active, reviewed correction that changes text."""
    cur.execute("""SELECT source_observation_id, id::text, page_no, match_text, before_text, after_text, evidence
                     FROM segmentation_curation_patch
                    WHERE review_state IN ('source_verified', 'human_verified') AND retired_at IS NULL
                      AND before_text <> after_text
                    ORDER BY source_observation_id, page_no, created_at, id""")
    out: dict[int, list[dict]] = collections.defaultdict(list)
    for obs, pid, page, match, before, after, evidence in cur.fetchall():
        out[int(obs)].append({"id": pid, "page_no": page, "match_text": match, "before_text": before,
                              "after_text": after, "evidence": evidence or {}})
    return out


skipped: list[str] = []       # corrections a window could not apply whole (reported by the recorders)


def corrected(rows: list[tuple[int, int, str]], patches: list[dict]) -> tuple[list[tuple[int, int, str]], int]:
    """rows [(block_id, page_no, text)] with the corrections applied; returns (rows, corrections applied)."""
    if not patches or not rows:
        return rows, 0
    blocks = [{"id": b, "page_no": p, "text": t} for b, p, t in rows]
    pages = {p for _b, p, _t in rows}
    applied = 0
    for patch in patches:
        if patch["page_no"] not in pages:
            continue
        hits = [b for b in blocks if b["page_no"] == patch["page_no"]
                and patch["match_text"].casefold() in b["text"].casefold()]
        if not hits:
            continue                      # the block is outside this window
        try:
            blocks, n = _apply_curation_patches(blocks, [patch])
        except ValueError:
            # its evidence needs blocks the window does not hold (a structural label move spanning two blocks, a
            # locator repeated only within the window): read as extracted, as before D-092 -- never half-applied
            skipped.append(patch["id"])
            continue
        applied += n
    return [(b["id"], b["page_no"], b["text"]) for b in blocks], applied
