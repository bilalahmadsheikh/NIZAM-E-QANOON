"""Source-derived boundary regressions: doc 02 §5.1–5.2, no DB required."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nizam.corpus.segment import _detached_schedule_reference, parse_contents, segment


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


def test_generic_short_title_alone_cannot_corroborate_the_opening():
    blocks = _agriculturists_opening_excerpt()
    for block in blocks:
        if block['id']==358518:
            block['text']='Short title.'  # synthetic negative: no second component
        elif block['id'] in (358524,358538,358555,358558):
            block['text']='Unrelated subject.'
    _, boundary, _ = parse_contents(blocks)
    assert blocks[boundary]['id']!=358517


def test_heading_about_repeal_of_another_law_is_not_a_placeholder():
    blocks = _agriculturists_opening_excerpt()
    blocks[1]['text']=blocks[1]['text'].replace('[Repealed.]','[Repealed enactments and savings.]')
    _, boundary, _ = parse_contents(blocks)
    assert blocks[boundary]['id']!=358517


def test_compound_opening_concession_requires_three_operative_promises():
    # Synthetic negative built from the real opening layout: reduce the list
    # and body witnesses to only sections 1 and 2. Their abbreviated compound
    # margin must not receive the new exception, which needs two OTHER ordered
    # headings. This does not certify the fallback numeric boundary as correct.
    witness_ids = {
        358439, 358442, 358515, 358516, 358517, 358518,
        358519, 358524, 358525, 358528, 358810,
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
