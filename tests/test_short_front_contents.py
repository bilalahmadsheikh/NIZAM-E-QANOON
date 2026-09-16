"""A short statute's printed contents must not become its sections.

The main contents parser rejects lists below four numbered units, below two
entries, or (unmarked) below five entries with the body in the first fifth of
the pages. The Diplomatic and Consular Privileges Act 1972 prints six contents
entries on page 1 and its six sections on pages 2-3, so every section used to
collide with its own contents entry and be demoted.
"""
import json
from pathlib import Path

from nizam.corpus.segment import (_parse_contents_main, _short_front_contents,
                                  parse_contents, segment)

FIXTURE = Path(__file__).parent / "fixtures" / "short-contents-3143.json"


def _blocks():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_main_parser_cannot_see_the_six_entry_contents():
    toc, boundary, found = _parse_contents_main(_blocks())
    assert not found


def test_short_list_is_read_as_contents_and_the_body_as_sections():
    blocks = _blocks()
    toc, boundary, found = parse_contents(blocks)
    assert found
    assert list(toc) == ["1", "2", "3", "4", "5", "6"]
    assert blocks[boundary]["page_no"] == 2
    result = segment(blocks)
    sections = [n for n in result.root.children if n.kind == "section"]
    assert [s.label for s in sections] == ["1", "2", "3", "4", "5", "6"]
    byid = {b["id"]: b for b in blocks}
    first = " ".join(byid[sections[0].blocks[0]]["text"].split())
    assert "This Act may be called" in first
    assert result.repeated_labels_demoted == 0


def _block(i, page, text):
    return {"id": 10_000 + i, "page_no": page, "block_no": i, "reading_order": i,
            "x0": 50.0, "y0": 100.0 + 20 * i, "x1": 500.0, "y1": 115.0 + 20 * i,
            "text": text, "page_height": 842.0}


def test_numbered_front_table_is_not_contents():
    # A membership table restarts at 1 before the enactment; its rows are not
    # repeated beside the sections that follow, so it must stay body.
    blocks = [
        _block(0, 1, "1. Prime Minister Chairman"),
        _block(1, 1, "2. Finance Minister Member"),
        _block(2, 2, "1. Short title. This Act may be called the Example Act."),
        _block(3, 2, "2. Definitions. In this Act, unless the context otherwise requires."),
    ]
    assert _short_front_contents(blocks) is None
    toc, boundary, found = parse_contents(blocks)
    assert not found


def test_operative_front_list_is_not_contents():
    # Enacted text restarted later (a second version) is not a contents list:
    # a heading does not say "shall".
    blocks = [
        _block(0, 1, "1. Short title. These rules shall come into force at once."),
        _block(1, 1, "2. Definitions. In these rules the Board means the Board."),
        _block(2, 2, "1. Short title. These rules shall come into force at once."),
        _block(3, 2, "2. Definitions. In these rules the Board means the Board."),
    ]
    assert _short_front_contents(blocks) is None


def _seg_blocks(*texts, page=1):
    return [{"id": i, "text": t, "page_no": page, "y0": 100.0 + i * 20,
             "page_height": 792.0} for i, t in enumerate(texts)]


def test_trailing_omitted_marker_is_a_source_verified_disposition():
    """The Pakistan Penal Code keeps the heading and appends the marker:
    "376B. Exceptional first offenders or repeat offenders [omitted]"."""
    toc = ["CONTENTS"] + [
        f"{n}. {'Exceptional first offenders or repeat offenders [omitted]' if n == 7 else f'Heading number {n}.'}"
        for n in range(1, 12)
    ]
    body = [f"{n}. Heading number {n}. Some enacted text here."
            for n in range(1, 12) if n != 7]
    seg = segment(_seg_blocks(*toc, *body), toc_dispositions=[{
        "id": 51, "toc_entry_ordinal": 6, "printed_label": "7",
        "printed_heading": "Exceptional first offenders or repeat offenders [omitted]",
        "disposition": "omitted", "source_block_id": 7, "source_page": 1,
        "amending_instrument_id": None,
    }])
    entry = next(item for item in seg.toc_entries if item["label"] == "7")
    assert entry["method"] == "source_verified_disposition"
    assert entry["node"].operation == "omitted"
    assert "7" not in seg.missing


def test_live_repeal_heading_is_not_a_disposition():
    """ "Repeal and savings" names live law; an assertion against it must fail."""
    import pytest
    toc = ["CONTENTS"] + [
        f"{n}. {'Repeal and savings.' if n == 7 else f'Heading number {n}.'}"
        for n in range(1, 12)
    ]
    body = [f"{n}. Heading number {n}. Some enacted text here."
            for n in range(1, 12) if n != 7]
    with pytest.raises(ValueError):
        segment(_seg_blocks(*toc, *body), toc_dispositions=[{
            "id": 52, "toc_entry_ordinal": 6, "printed_label": "7",
            "printed_heading": "Repeal and savings.", "disposition": "repealed",
            "source_block_id": 7, "source_page": 1, "amending_instrument_id": None,
        }])
