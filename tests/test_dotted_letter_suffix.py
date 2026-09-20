"""Source-verified inserted-label typography: docs 02 section 5.1-5.2."""
import json
from copy import deepcopy
from pathlib import Path

from nizam.corpus.segment import _citation_label_key, classify, parse_contents, segment, subdivide


def test_printed_dotted_letter_suffix_is_a_complete_section_label():
    assert classify('5.A. Power to require execution of works.') == (
        'section', '5.A', 'Power to require execution of works.')
    assert classify('6[5.A. Power to require execution of works.]')[1] == '5.A'
    assert _citation_label_key('5.A') == _citation_label_key('5-A')
    assert _citation_label_key('5.1') != _citation_label_key('51')
    assert _citation_label_key('5.1.A') != _citation_label_key('51A')


def test_separate_letter_clause_and_prose_are_not_joined_to_the_number():
    assert classify('5.\nA. Introduction')[1] == '5'
    assert classify('5. A. Introduction')[1] == '5'
    assert classify('The rule refers to section 5.A.') is None
    assert len(subdivide('The preceding provision applies.\n5.A. Power to require works.')) == 2


def test_actual_toc_5_dot_a_links_only_to_body_5_dash_a():
    blocks = json.loads((Path(__file__).parent / 'fixtures' /
                        'split-notes-1927.json').read_text(encoding='utf-8'))
    toc, boundary, found = parse_contents(blocks)
    assert found and boundary == 24 and '5.A' in toc
    assert toc['5.A'] == 'Power to require execution of works and taking of measures.'
    result = segment(blocks)
    assert not result.missing and result.repeated_labels_demoted == 0
    entry = next(e for e in result.toc_entries if e['label'] == '5.A')
    assert entry['source_block_id'] == 136459 and entry['source_page'] == 1
    assert entry['node'].kind == 'section' and entry['node'].label == '5-A'
    assert entry['node'].first_block == 136521 and entry['node'].first_page == 6
    assert set(result.block_roles) == {b['id'] for b in blocks}


def test_two_source_forms_never_get_collapsed_into_one_heading_match():
    blocks = [
        {'id':1,'page_no':1,'text':'CONTENTS','y0':100},
        {'id':2,'page_no':1,'text':'1. Opening.\n5.A. Topic A.\n5-A. Topic B.','y0':120},
        {'id':3,'page_no':2,'text':'1. Opening. This Act applies to the district.','y0':100},
        {'id':4,'page_no':2,'text':'5.A. Topic A. This section governs first-class works.','y0':150},
        {'id':5,'page_no':2,'text':'5-A. Topic B. This section governs second-class works.','y0':200},
    ]
    result = segment(blocks)
    entries = [e for e in result.toc_entries if _citation_label_key(e['label']) == '5a']
    assert len(entries) == 2
    assert entries[0]['node'] is not entries[1]['node']
    assert [e['node'].heading for e in entries] == ['Topic A.', 'Topic B.']


def test_actual_punjab_oath_section_is_citable_and_links_to_printed_contents():
    blocks = json.loads((Path(__file__).parent/'fixtures'/'dotted-suffix-3485.json').read_text())
    original = deepcopy(blocks)
    result = segment(blocks)
    entry = next(e for e in result.toc_entries if e['label']=='4-A')
    assert entry['source_block_id']==391103 and entry['source_page']==1
    assert entry['node'].kind=='section' and entry['node'].label=='4.A'
    assert entry['node'].first_block==391144 and entry['node'].first_page==3
    assert 'members shall make oath in the form set out in the Schedule' in entry['node'].text
    assert not result.missing and result.repeated_labels_demoted==0
    assert len([n for n in result.flatten() if n.kind=='section'])==12
    assert set(result.block_roles)=={b['id'] for b in blocks}
    assert blocks==original


def test_actual_companies_direction_section_owns_its_operative_children():
    blocks = json.loads((Path(__file__).parent/'fixtures'/'dotted-suffix-4495-page181.json').read_text())
    original = deepcopy(blocks)
    result = segment(blocks)
    section = next(n for n in result.flatten() if n.kind=='section' and n.label=='282.D')
    assert section.first_block==881480 and section.first_page==181
    assert 'Notwithstanding anything contained in any other provision' in section.text
    for label,block in [('a',881481),('b',881482),('c',881484),('2',881486)]:
        child = next(n for n in result.flatten() if n.label==label and n.first_block==block)
        assert child.parent is section
    assert result.repeated_labels_demoted==0
    assert set(result.block_roles)=={b['id'] for b in blocks}
    assert blocks==original


def test_actual_forest_whistleblower_sections_are_not_three_clauses_called_51():
    blocks = json.loads((Path(__file__).parent/'fixtures'/'dotted-suffix-4235.json').read_text())
    original = deepcopy(blocks)
    result = segment(blocks, detect_contents=False)
    nodes = list(result.flatten())
    sections = [n for n in nodes if n.kind=='section']
    assert [(n.label,n.first_block,n.first_page) for n in sections] == [
        ('51.O',635032,45),('51.P',635036,45),('51.Q',635040,46)]
    assert not any(n.label=='51' for n in nodes)
    by_label = {n.label:n for n in sections}
    for label,section,anchor in [('2','51.O',635033),('3','51.O',635034),
                                  ('4','51.O',635035),('2','51.P',635038),
                                  ('2','51.Q',635041)]:
        child = next(n for n in nodes if n.label==label and n.first_block==anchor)
        assert child.parent is by_label[section]
    proviso = next(n for n in nodes if n.kind=='proviso' and n.first_block==635037)
    assert proviso.parent.kind=='subsection' and proviso.parent.parent is by_label['51.P']
    cross_page = next(n for n in nodes if n.first_block==635038)
    assert cross_page.last_page==46
    assert cross_page.text.endswith('one hundred thousand rupees.')
    assert result.repeated_labels_demoted==0 and not result.missing
    assert set(result.block_roles)=={b['id'] for b in blocks}
    assert blocks==original
