"""Per-entry source anchors for printed contents rows: doc 02 §5.1, doc 03 §4.

PyMuPDF merges several printed contents lines into one block. Before this, every
entry cut out of such a block stored the same ``source_block_id`` and nothing
else, so the rows were indistinguishable as evidence and their stored order was
whichever reader happened to find them first. These regressions pin both halves
of the fix: ``subdivide_spans`` reports where each piece begins, and
``_toc_source_entries`` anchors and orders every row on that character offset.

No database. The 1918 fixture is the real extracted block stream of the Sind
Landing and Wharfage Fees Act, 1882, whose page-1 contents arrives as eight rows
inside block 134870.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

# The segmenter under test. Normally the repo's module; ``NIZAM_SEGMENT_PATH``
# points these same assertions at a copy of segment.py, which is how the patch
# that introduced them was verified before it was applied.
_override = os.environ.get("NIZAM_SEGMENT_PATH")
if _override:
    _spec = importlib.util.spec_from_file_location(
        "segment_under_test", str(Path(_override).resolve()))
    segment_module = importlib.util.module_from_spec(_spec)
    sys.modules["segment_under_test"] = segment_module
    _spec.loader.exec_module(segment_module)
else:
    from nizam.corpus import segment as segment_module

subdivide = segment_module.subdivide
subdivide_spans = segment_module.subdivide_spans
segment = segment_module.segment
_toc_source_entries = segment_module._toc_source_entries

FIXTURES = Path(__file__).parent / "fixtures"

# Block 134870 of document 1918, verbatim. Eight printed contents rows, one
# block: this is the shape the anchor exists for.
MERGED_CONTENTS_BLOCK = (
    "5.  \nGovernment to fix limits of bandars, etc., and the fees to be  \n \n"
    "levied. \n \n6. \nPowers and duties under this Act by whom to be exercised "
    "\n          and performed. \n \n7. \nPowers, privileges and liabilities of "
    "officers who collect fees.                      \nPunishment of offenders."
    " \n \n8. \nTables of fees to be posted up. \n \n9. \nPower to make bye-laws."
    " \n \n10. \nFees realised under this Act how to be expended. \n \n11. "
    "\nReceipt, expenditure and account of landing and wharfage  \nfees. \n \n"
    "     12.      Grouping of ports. \n \n"
)


def blocks(*texts: str, page: int = 1) -> list[dict]:
    """Blocks as the extractor hands them over: id, text, page, geometry."""
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0}
            for i, t in enumerate(texts)]


# --------------------------------------------------------- subdivide_spans
def test_spans_agree_with_subdivide_and_locate_every_piece():
    """One cut rule, two views of it. The offset must be where the piece is."""
    texts = [
        MERGED_CONTENTS_BLOCK,
        "1. Short title and commencement. \n2. Repeal.",
        "5. Power to require works. \n6. \nPenalty. \n7. Appeal lies to the "
        "Collector.",
        "The preceding provision applies.\n5.A. Power to require works.",
        "In this Act, unless the context otherwise requires,",
        "",
        "   \n \n",
    ]
    for text in texts:
        spans = subdivide_spans(text)
        assert [piece for _, piece in spans] == subdivide(text)
        assert spans, "subdivide_spans must return at least one piece"
        for offset, piece in spans:
            assert offset >= 0
            assert text[offset:offset + len(piece)] == piece
        # Offsets are the reading order of the page, strictly increasing.
        assert [o for o, _ in spans] == sorted(o for o, _ in spans)
        assert len({o for o, _ in spans}) == len(spans)


def test_fused_margin_prefix_offsets_stay_relative_to_the_block():
    """The fused-margin rule rebuilds its pieces from two capture groups, so the
    naive "offset = running length" bookkeeping would drift. Section 27 of the
    Balochistan Education Foundation Act is the case the rule was written for.
    """
    text = ("Repeal.\n27.\n2The Balochistan Education Foundation Ordinance, "
            "2002 (Ordinance No. V of 2002), is hereby repealed.")
    spans = subdivide_spans(text)
    assert len(spans) == 2
    assert spans[0] == (0, "Repeal.")
    offset, piece = spans[1]
    assert text[offset:] == piece
    assert text[offset:offset + 3] == "27."


def test_uncut_text_anchors_at_the_start_of_the_block():
    text = "In this Act 9[the term “Government”] means the Government."
    assert subdivide_spans(text) == [(0, text)]


# ------------------------------------------------- per-entry contents anchor
def test_eight_printed_rows_in_one_block_get_eight_distinct_anchors():
    """Document 1918, read from its own extracted blocks.

    Block 134870 holds the printed rows for labels 5 to 12. Every one of them is
    a separate promise the Act makes about itself, and every one now names the
    character where the reader can see it.
    """
    stream = json.loads((FIXTURES / "contents-anchors-1918.json")
                        .read_text(encoding="utf-8"))
    text_of = {b["id"]: b["text"] for b in stream}
    result = segment(stream)

    merged = [e for e in result.toc_entries if e["source_block_id"] == 134870]
    assert [e["label"] for e in merged] == [
        "5", "6", "7", "8", "9", "10", "11", "12"]
    assert text_of[134870] == MERGED_CONTENTS_BLOCK      # fixture is verbatim

    offsets = [e["source_char_offset"] for e in merged]
    assert offsets == [0, 82, 172, 291, 330, 361, 418, 496]
    assert len(set(offsets)) == len(offsets)
    assert offsets == sorted(offsets)                    # printed order
    for entry in merged:
        printed = text_of[134870][entry["source_char_offset"]:]
        # The anchor lands on the printed label itself, not on the whitespace
        # that separates two rows.
        assert printed.startswith(entry["label"])
        assert not printed[:1].isspace()


def test_every_contents_entry_of_a_document_carries_a_unique_anchor():
    """Two printed rows cannot begin at the same character of the same block.
    Migration 0051 relies on this; assert it on real source, not by argument.
    """
    stream = json.loads((FIXTURES / "contents-anchors-1918.json")
                        .read_text(encoding="utf-8"))
    result = segment(stream)
    assert result.toc_entries
    anchors = [(e["source_block_id"], e["source_char_offset"])
               for e in result.toc_entries]
    assert all(block is not None and offset is not None
               for block, offset in anchors)
    assert len(set(anchors)) == len(anchors)
    lengths = {b["id"]: len(b["text"]) for b in stream}
    for block, offset in anchors:
        assert 0 <= offset < lengths[block]


def test_anchoring_does_not_change_which_rows_are_read():
    """The fix re-anchors entries; it must not create or drop one. Document
    1918's printed page-1 contents is twelve rows, and the parser reads
    seventeen because its contents boundary also swallows page 2 -- a separate
    defect, deliberately still visible here. What matters is that the ledger is
    unchanged row for row.
    """
    stream = json.loads((FIXTURES / "contents-anchors-1918.json")
                        .read_text(encoding="utf-8"))
    result = segment(stream)
    assert [(e["label"], e["source_block_id"]) for e in result.toc_entries] == [
        ("1", 134866), ("2", 134867), ("3", 134868), ("4", 134869),
        ("5", 134870), ("6", 134870), ("7", 134870), ("8", 134870),
        ("9", 134870), ("10", 134870), ("11", 134870), ("12", 134870),
        ("1", 134874), ("2", 134875), ("3", 134877), ("4", 134878),
        ("5", 134894),
    ]
    assert [e["ordinal"] for e in result.toc_entries] == list(range(17))


# ----------------------------------------------------------- printed order
def test_rows_in_one_block_are_ordered_by_the_page_not_by_the_reader():
    """A contents block can hold both printed forms at once: a row set with its
    period ("5. Heading") and rows set as a two-column table (the number alone
    on one line, the heading on the next).

    Sorting only on the block index left Python's stable sort to decide, so
    every dotted row in a block came before every two-column row in it and
    `ordinal` -- the printed position stored in `instrument_toc_entry` -- was
    wrong. The order-bounded recovery reads adjacency out of that list, so this
    is not cosmetic.
    """
    contents = (
        "1\nShort title and commencement. \n"
        "2\nDefinitions. \n"
        "3\nAppointment of officers. \n"
        "4\nPowers of the Collector. \n"
        "5. Register of licences to be maintained. \n"
        "6\nRenewal of a licence. \n"
        "7\nSuspension and cancellation. \n"
        "8\nAppeal to the Commissioner. \n"
        "9\nPower to make rules. \n"
    )
    body = [
        "1. Short title and commencement. This Act may be called the Test Act.",
        "2. Definitions. In this Act, unless the context otherwise requires.",
        "3. Appointment of officers. Government may appoint such officers.",
        "4. Powers of the Collector. The Collector may enter any premises.",
        "5. Register of licences to be maintained. Every officer shall keep.",
        "6. Renewal of a licence. A licence may be renewed on application.",
        "7. Suspension and cancellation. A licence may be suspended.",
        "8. Appeal to the Commissioner. An appeal lies to the Commissioner.",
        "9. Power to make rules. Government may make rules to carry out.",
    ]
    stream = blocks(contents, *body)
    labels = {str(n): "" for n in range(1, 10)}
    entries = _toc_source_entries(stream, 1, labels)

    assert [e["label"] for e in entries] == [str(n) for n in range(1, 10)]
    assert all(e["source_block_id"] == 0 for e in entries)
    offsets = [e["source_char_offset"] for e in entries]
    assert offsets == sorted(offsets)
    assert len(set(offsets)) == 9
    for entry in entries:
        assert contents[entry["source_char_offset"]:].startswith(entry["label"])
