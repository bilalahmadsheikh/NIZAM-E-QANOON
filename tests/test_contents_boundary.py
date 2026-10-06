"""Source-derived boundary regressions: doc 02 §5.1–5.2, no DB required."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nizam.corpus.segment import (
    _detached_schedule_reference,
    _has_contents_marker,
    parse_contents,
    segment,
)


def test_bare_column_header_must_own_its_block():
    assert _has_contents_marker("Rules.")
    assert _has_contents_marker("THE EXAMPLE ACT\nCONTENTS\nAct No. I")
    assert not _has_contents_marker(
        "1.\nThese\nrules\nmay be called the Example Rules, 2026."
    )


def test_marker_with_no_numbered_rows_before_formula_does_not_use_body_as_toc():
    texts = [
        "THE EXAMPLE ACT", "CONTENTS", "Short title.", "Definitions.",
        "WHEREAS it is expedient to enact the following law",
        "1. This Act may be called the Example Act.",
        "2. In this Act, prescribed means prescribed by rules.",
        "3. The authority shall act.",
        "1. First schedule row.", "2. Second schedule row.",
        "3. Third schedule row.",
    ]
    bs = [
        {"id": i, "text": text, "page_no": 1 if i < 5 else 2,
         "y0": 60.0 + i * 10, "page_height": 792.0,
         "x0": 72.0, "x1": 520.0}
        for i, text in enumerate(texts)
    ]
    toc, boundary, found = parse_contents(bs)
    assert not found
    assert toc == {} and boundary == 0


def test_unmarked_operative_body_run_is_not_contents_of_later_table():
    texts = [
        "1. These rules shall commence at once.",
        "2. The authority shall appoint officers.",
        "3. Government may prescribe procedure.",
        "4. Every officer shall keep records.",
        "5. The board shall decide applications.",
        "1. Chairman", "2. Director", "3. Secretary", "4. Treasurer",
        "5. Auditor",
    ]
    bs = [
        {"id": i, "text": text, "page_no": 1 if i < 5 else 2,
         "y0": 60.0 + i * 10, "page_height": 792.0,
         "x0": 72.0, "x1": 520.0}
        for i, text in enumerate(texts)
    ]
    assert parse_contents(bs) == ({}, 0, False)


@pytest.mark.parametrize('document,boundary', [(1438, 15), (2581, 14)])
def test_final_body_boundary_and_promises_use_the_same_source_prefix(document, boundary):
    blocks = json.loads((Path(__file__).parent / 'fixtures' / f'contents-{document}.json').read_text(encoding='utf-8'))
    toc, actual_boundary, found = parse_contents(blocks)
    assert found and actual_boundary == boundary  # no shrinkage of the body
    assert set(toc) == {'1', '2', '3', '4'}
    result = segment(blocks)
    assert not result.missing
    assert result.repeated_labels_demoted == 0
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert [n.label for n in sections] == ['1', '2', '3', '4']
    assert all(n.first_page == 2 for n in sections)
    schedule = [n for n in result.flatten() if n.kind == 'schedule']
    assert len(schedule) == 1 and schedule[0].first_page == 3
    parts = [n for n in schedule[0].children if n.kind == 'part']
    assert [n.label for n in parts] == ['I', 'II']
    assert [n.label for n in parts[0].children if n.kind == 'clause'] == [str(i) for i in range(1, 25)]
    assert set(result.block_roles) == {b['id'] for b in blocks}
    assert all(e['source_page'] == 1 and e['node'] is not None for e in result.toc_entries)


def test_detached_schedule_proof_does_not_accept_continued_prose():
    assert _detached_schedule_reference('THE SCHEDULE', '(See sections 2 and 3)')
    assert not _detached_schedule_reference('the Schedule', '(See sections 2 and 3)')
    assert not _detached_schedule_reference('THE SCHEDULE', '(See sections 2 and 3) shall apply')
    assert not _detached_schedule_reference('THE SCHEDULE referred to', '(See section 2)')


def test_title_year_before_printed_contents_is_not_a_promised_section():
    blocks = json.loads((Path(__file__).parent / 'fixtures' / 'contents-1224.json').read_text(encoding='utf-8'))
    original = deepcopy(blocks)
    toc, boundary, found = parse_contents(blocks)
    assert found and boundary == 20
    assert list(toc) == [str(i) for i in range(1, 13)]
    assert blocks == original  # immutable title-year evidence is retained
    result = segment(blocks)
    assert not result.missing
    assert [e['label'] for e in result.toc_entries] == list(toc)
    assert [n.label for n in result.flatten() if n.kind == 'section'] == list(toc)
    assert all(n.first_page >= 2 for n in result.flatten() if n.kind == 'section')
    assert result.repeated_labels_demoted == 0
    assert set(result.block_roles) == {b['id'] for b in original}


def test_four_digit_labels_after_contents_marker_are_not_discarded():
    blocks = json.loads((Path(__file__).parent / 'fixtures' / 'contents-1224.json').read_text(encoding='utf-8'))
    # Synthetic negative case derived from the real layout: a four-digit
    # provision explicitly printed IN the list, and corroborated in the body.
    blocks.insert(8, {'id': -1, 'page_no': 1, 'text': '1975. Historical jurisdiction.', 'y0': 100})
    blocks.append({'id': -2, 'page_no': 5, 'text': '1975. Historical jurisdiction. This rule governs historical claims.', 'y0': 100})
    toc, boundary, found = parse_contents(blocks)
    assert found and boundary == 21
    assert toc['1975'] == 'Historical jurisdiction.'


def test_generic_sections_header_does_not_authorize_title_year_exclusion():
    blocks = json.loads((Path(__file__).parent / 'fixtures' / 'contents-1224.json').read_text(encoding='utf-8'))
    blocks[4]['text'] = blocks[4]['text'].replace('CONTENTS.', 'SECTIONS')
    toc, _, found = parse_contents(blocks)
    assert found and '1975' in toc


def test_editorial_note_inside_contents_is_not_a_body_restart():
    """Doc 3581 shape: a repeal footnote must not truncate the TOC at 7."""
    texts = ['THE EXAMPLE ACT, 1870', 'CONTENTS']
    texts.extend(f'{n}. Promised heading {n}.' for n in range(1, 8))
    texts.append('1. Repealed vide A.O., 1937.')
    texts.append('8. [Repealed.]')
    texts.extend(f'{n}. Promised heading {n}.' for n in range(9, 11))
    body_start = len(texts)
    substantive = (
        ' Every authority shall apply this provision to every proceeding '
        'and shall record its decision in writing.'
    )
    texts.extend(
        f'{n}. Promised heading {n}.{substantive}'
        for n in (*range(1, 8), 9, 10)
    )
    blocks = [
        {
            'id': index,
            'text': text,
            'page_no': 1 if index < body_start else 2,
            'y0': 60.0 + (index % 20) * 20,
            'page_height': 792.0,
            'x0': 72.0,
            'x1': 520.0,
        }
        for index, text in enumerate(texts)
    ]

    toc, boundary, found = parse_contents(blocks)

    assert found
    assert boundary == body_start
    assert list(toc) == [str(n) for n in range(1, 11)]
    assert toc['8'] == '[Repealed.]'


def _agriculturists_opening_excerpt():
    # Non-contiguous, immutable block projections from the real 37-page PDF.
    # This tests the opening boundary, not the omitted intervening law text.
    return json.loads((Path(__file__).parent/'fixtures'/'contents-opening-3353.json').read_text())


def test_closed_repeal_placeholder_and_compound_margin_do_not_swallow_opening():
    blocks = _agriculturists_opening_excerpt()
    original = deepcopy(blocks)
    toc, boundary, found = parse_contents(blocks)
    assert found and blocks[boundary]['id']==358517 and blocks[boundary]['page_no']==6
    assert toc['2A']=='[Repealed.]'  # retained promise/evidence, not deleted
    assert toc['1']=='Short title. Commencement. Local extent.'
    assert blocks==original


# These negatives prove the compound-opening concession is REQUIRED, by
# removing its evidence and showing the boundary is then NOT the opening. The
# fallback they land on is block 358528, which is past 358525 -- section 2's
# enacted text ("In construing this Act ... the following rules shall be
# observed ... 'Agriculturist' shall be taken to mean ..."). Since the body
# floor stopped being allowed to advance past enacted text, that fallback is
# refused and the earliest candidate wins, which is 358517 -- the right answer
# for the wrong reason, and the negatives stopped discriminating.
#
# So take the enacted witness out of the already-synthetic negatives too. The
# concession is observable again, under both the fenced and the unfenced
# parser, and nothing here certifies 358528 as a correct boundary -- it never
# was one.
_SECTION_TWO_ENACTED_TEXT = 358525


def test_generic_short_title_alone_cannot_corroborate_the_opening():
    blocks = [b for b in _agriculturists_opening_excerpt()
              if b['id'] != _SECTION_TWO_ENACTED_TEXT]
    for block in blocks:
        if block['id']==358518:
            block['text']='Short title.'  # synthetic negative: no second component
        elif block['id'] in (358524,358538,358555,358558):
            block['text']='Unrelated subject.'
    _, boundary, _ = parse_contents(blocks)
    assert blocks[boundary]['id']!=358517


def test_heading_about_repeal_of_another_law_is_not_a_placeholder():
    blocks = [b for b in _agriculturists_opening_excerpt()
              if b['id'] != _SECTION_TWO_ENACTED_TEXT]
    blocks[1]['text']=blocks[1]['text'].replace('[Repealed.]','[Repealed enactments and savings.]')
    _, boundary, _ = parse_contents(blocks)
    assert blocks[boundary]['id']!=358517


def test_compound_opening_concession_requires_three_operative_promises():
    # Synthetic negative built from the real opening layout: reduce the list
    # and body witnesses to only sections 1 and 2. Their abbreviated compound
    # margin must not receive the new exception, which needs two OTHER ordered
    # headings. This does not certify the fallback numeric boundary as correct;
    # see the note above _SECTION_TWO_ENACTED_TEXT for why that block is not a
    # witness here.
    witness_ids = {
        358439, 358442, 358515, 358516, 358517, 358518,
        358519, 358524, 358528, 358810,
    }
    blocks = [b for b in _agriculturists_opening_excerpt()
              if b['id'] in witness_ids]
    next(b for b in blocks if b['id'] == 358442)['text'] = (
        '1. Short title. Commencement. Local extent.\n2. Construction.'
    )
    original = deepcopy(blocks)
    toc, boundary, found = parse_contents(blocks)
    assert found and list(toc) == ['1', '2']
    assert blocks[boundary]['id'] != 358517
    assert blocks == original
