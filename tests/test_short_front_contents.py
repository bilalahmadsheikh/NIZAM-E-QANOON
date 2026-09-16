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
