"""The parser-drift repair: the drift shapes stop, the fixes stay.

On 23 Sep a managed full replay withdrew 24 released instruments. The cause
was not the fix it shipped but ``segment.py`` edits that had reached only
their own documents through bounded replays (docs/RELEASE-ALL-HANDOFF-
2026-09-23.md, "a count-only gate passed a release SWAP"). Each edit fixed a
real document, so the repair narrows rather than reverts them
(``.patch_drift.py``):

  A  a bare contents column word sharing a block is a header only when it is
     SET OFF as one -- no sentence text above it, and it closes the block or
     heads the first entry (drift edit 3);
  B  a block already proved apparatus is not cut down to its first note
     (drift edits 5+10);
  C  the marginal-heading scan skips the unit's own block only for a SECTION
     label, and only over what would end the scan (drift edits 11+12);
  D  a text repeated at the top of pages is a running title only if it reads
     as one (drift edit 13).

Both sides are pinned against trees the corpus actually STORED
(``fixtures/parser-drift-repair.json``: every source block verbatim, and the
reference tree's sections, contents links and S7 population):

  * "lost": a withdrawn instrument, against its PRE-replay release -- the
    known specimens of the drift shapes;
  * "codex": a document a drift edit was written for (or that only the edit
    released, doc 3880), against its current tree. Reverting the three
    culprits instead fails 4465 and 1847; narrowing C to bare labels only
    fails 3880.

Doc 02 sections 5.1-5.2.  These skip until ``.patch_drift.py`` is applied,
the convention for measured parser work handed over rather than applied.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nizam.corpus import segment as S

pytestmark = pytest.mark.skipif(
    not hasattr(S, "_column_word_is_set_off"),
    reason=".patch_drift.py is not applied",
)

FIXTURE = Path(__file__).parent / "fixtures" / "parser-drift-repair.json"
_CACHE: dict = {}


def _fixture() -> dict:
    if not _CACHE:
        _CACHE.update(json.loads(FIXTURE.read_text(encoding="utf-8")))
    return _CACHE


def _overrides(resolutions: list[dict] | None) -> dict:
    merged: dict = {}
    for row in resolutions or []:
        merged.update((row.get("evidence") or {}).get("structural_overrides") or {})
    return merged


def build(document: str):
    """segment() with the reviewed inputs the worker passes for this document."""
    case = _fixture()[document]
    resolutions = case["structural_resolutions"] or None
    return S.segment(case["blocks"],
                     structural_resolutions=resolutions,
                     structural_overrides=_overrides(resolutions) or None,
                     detect_contents=case["window_pages"] is None)


def sections(seg) -> list[list]:
    return [[n.kind, n.label, n.first_block, n.first_page]
            for n in seg.flatten() if n.kind in ("section", "article")]


def open_collisions(seg) -> int:
    return sum(1 for d in seg.repeated_label_decisions
               if not d.get("settled_by_review"))


WHOLE_DOCUMENTS = ["983", "1119", "1139", "252", "2034",   # lost
                   "3720", "4465", "1847", "3880"]          # codex


@pytest.mark.parametrize("document", WHOLE_DOCUMENTS)
def test_rebuilds_the_stored_tree(document):
    """Sections (label, first block, page), S7 population and contents links
    equal the stored reference tree."""
    case = _fixture()[document]
    ref = case["reference"]
    seg = build(document)
    assert sections(seg) == ref["sections"], case["why"]
    assert open_collisions(seg) == ref["s7_candidates"], case["why"]
    assert len(seg.toc_entries) == ref["toc_entries"]
    assert sum(1 for e in seg.toc_entries if e.get("node") is None) == ref["toc_unlinked"]


# ------------------------------------------------------------- A: contents word
def _block(document: str, block_id: int) -> str:
    return next(b["text"] for b in _fixture()[document]["blocks"] if b["id"] == block_id)


@pytest.mark.parametrize("text", [
    # doc 1119 p1: the header over its own first entry "01."
    "C O N T E N T \n \n \n01. \nShort title, and commencement.  \n",
    # docs 3329/3499 p1: a misspelt banner, then the column word
    " \n \n \n \nCONTAINTS  \n \n \n  RULES. \n \n",
    # doc 2875 p1
    " \nCONTENT \n \nPreamble \nSections \n \n",
    # the Rohri Canal Act layout named in `_CONTENTS_COLUMN_HEADER`'s comment
    "[2nd April, 1991]\nPreamble\nSections\n1.  Short title and commencement.",
    "THE CANAL AND DRAINAGE ACT, 1991\nSections",
    "Rules.",
])
def test_a_a_column_word_set_off_as_a_header_is_one(text):
    assert S._has_contents_marker(text)


def test_a_the_1119_block_is_a_header_and_s10_stays_operative():
    """Refusing doc 1119's fused header demoted operative s.10 (p3) beneath
    the contents line "10. Repeal of Sindh Ordinance X of 1995." (p1)."""
    assert S._has_contents_marker(_block("1119", 54322))
    s10 = [row for row in sections(build("1119")) if row[1] == "10"]
    assert [row[3] for row in s10] == [3]


@pytest.mark.parametrize("text", [
    # doc 3720 p1: word-per-line prose; the line after continues the sentence
    "1. \n(1) \nThese \nrules \nmay \nbe \ncalled \nthe \nSindh \n",
    # doc 4465 p1: sentence text above the word
    "In exercise of the powers conferred\nby\nsection\nl4\nread\nwith\nsection\n13\nof\n",
    "(1)\nIn\nthese\nrules\nunless there\nis anything\nrepugnant",
    # doc 3720 p2: a marginal heading "... made under these / rules."
    "Appointment to be \nmade under these \nrules. \n \n4.  (1)    Appointment to a post",
    # doc 4139: "... in accordance with the Government / rules." and a
    # marginal heading "Application / of / Government / Rules"
    "shall be determined in accordance with the Government \nrules. \n",
    "Application \nof \nGovernment \nRules  \n",
    # doc 4471: a designation in a signature block and in a name list
    "(MUSADDIQUE\nMEMON)\nSECTION\nOFFICER (REGULATION-I)\n",
    "Mr.\nMusaddique\nMemon,\nSection\nOfficer\n(Regulation-I) were the key officers",
    # doc 4347 p2: the end of regulation 1.1's own sentence
    "1.1 \nThese Regulations shall be called Sindh Seed Corporation Service \n"
    "Regulations.  \n1.2 \nThey Shall apply to:  \n",
    # doc 4467 p1: "... has made the following" / "rules / with the approval"
    "rules\nwith the approval\nof the Governor\nof Sindh, to regulate\n",
])
def test_a_a_column_word_inside_sentence_text_is_not_a_header(text):
    """The last two are the pre-replay releases of docs 4347 and 4467, which
    existed only because this prose was read as a contents header: 4347 then
    held regulation 1.1-1.2 as its "contents" and cited "1.1" to training
    text on p6; 4467 held the real rules 1 and 2 as "contents" and cited a
    gazette footnote and a table row as rules 1 and 2. Refusing the prose
    reads both correctly and leaves their genuine collisions for review."""
    assert not S._has_contents_marker(text)


# ------------------------------------------------------ B: whole-apparatus block
def test_b_a_proved_footnote_block_is_not_cut_to_its_first_note():
    """Doc 983 p3: notes 1-12 in one block, note 1 reading "The original words
    viz. ... to read as above." Cut to that note, it opened a phantom section
    1 that collided with the real one."""
    seg = build("983")
    phantom = [n for n in seg.flatten()
               if n.first_block == 46445 and n.kind in ("section", "clause")]
    assert phantom == []


def test_b_notes_fused_below_a_provision_are_still_cut():
    """Doc 4432 p37, the edit's own case: the cut itself is unchanged."""
    text = ("63.  * * * * ]\n\n"
            "1 Substituted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n"
            "2 Substituted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n"
            "3 Deleted vide the Khyber Pakhtunkhwa Act No. XXV of 2019.\n")
    assert S._without_trailing_inline_footnotes(text) == "63.  * * * * ]"


# ------------------------------------------------------------ C: heading scan
def test_c_a_subsection_does_not_borrow_the_next_sections_margin():
    """Doc 1139 p3: block 55748 holds s.2's tail, "(3)", a wrapped "(2)", then
    "3." and "(1)". Section 3's marginal heading precedes the block. Letting
    "(3)" see it made "(3)" section 3 and the real "3." a root-level clause."""
    seg = build("1139")
    in_block = [(n.kind, n.label, n.parent.kind if n.parent else None)
                for n in seg.flatten() if n.first_block == 55748]
    assert ("section", "3", "instrument") in in_block
    assert ("subsection", "3", "section") in in_block
    assert not any(kind == "clause" and label == "3" for kind, label, _ in in_block)


def test_c_a_heading_in_the_labels_own_block_is_collected():
    """Doc 252 p13: "Overriding Effect." / "20" / "The provisions ..." in one
    block. Skipping the whole block lost s.20 and left a contents gap."""
    assert ["section", "20", 11130, 13] in sections(build("252"))


def test_c_a_bare_label_still_reaches_the_adjacent_margin():
    """Doc 1847 p7: "(2) A notification ..." and bare "9" / "Any number of
    localities ..." share block 126277; the heading is the block before."""
    assert ["section", "9", 126277, 7] in sections(build("1847"))


def test_c_a_dotted_label_after_provisos_reaches_its_margin():
    """Doc 3880 p21: section 9's closing provisos and "10." share block
    510370; "No remission in sentence." is the block before. Without the
    scan reaching it, sections 10-46 of the Sindh Control of Narcotic
    Substances Act fall to clauses and nine contents entries go unlinked."""
    seg = build("3880")
    assert ["section", "10", 510370, 21] in sections(seg)
    assert not [e for e in seg.toc_entries if e.get("node") is None]


# ------------------------------------------------------------ D: running title
def test_d_a_rate_repeated_at_page_tops_is_law_not_furniture():
    """Doc 3255 pp79-84, the Sindh Sales Tax on Services Act's schedule: the
    rate "15%" opens several pages. Every printed rate stays in the text."""
    case = _fixture()["3255"]
    seg = build("3255")
    printed = sum(b["text"].count("15%") for b in case["blocks"])
    kept = " ".join(n.text or "" for n in seg.flatten()).count("15%")
    assert kept == printed


def test_d_a_running_title_is_still_stripped_from_provision_text():
    """Drift edit 13's purpose survives: a title printed at the top of every
    page does not become part of the provision it interrupts."""
    title = "SINDH ACT NO.XVI OF 2012 THE EXAMPLE UNIVERSITY ACT, 2012."
    blocks = []
    for page in (1, 2, 3):
        blocks.append({"id": page * 10, "text": title, "page_no": page, "y0": 20.0,
                       "page_height": 792.0, "x0": 72.0, "x1": 520.0})
        blocks.append({"id": page * 10 + 1, "page_no": page, "y0": 300.0,
                       "page_height": 792.0, "x0": 72.0, "x1": 520.0,
                       "text": f"{page}. The Authority shall perform function {page} "
                               "and shall continue to do so"})
    seg = S.segment(blocks, detect_contents=False)
    text = " ".join(n.text or "" for n in seg.flatten())
    assert "EXAMPLE UNIVERSITY" not in text
    assert [n.label for n in seg.flatten() if n.kind == "section"] == ["1", "2", "3"]
