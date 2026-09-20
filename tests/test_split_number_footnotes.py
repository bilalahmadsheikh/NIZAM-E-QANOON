"""Rendered Sindh source regressions: docs 02 section 5 and 03 section 2A."""
from copy import deepcopy
import json
from pathlib import Path

from nizam.corpus.segment import _is_footnote_run, segment


def test_isolated_note_numbers_keep_their_provenance_vocabulary():
    text = ('1.\nCl. 7th ins. By Sind Repealing and Amending Act, 1910.\n'
            '2.\nSubs. by Sind Act 17 of 1975, s. 3, Sch. II.\n'
            '3.\nIns. By Act 22 of 1882, s. 5.\n'
            '4.\nThe words were repealed by the Amending Act, 1895.\n')
    assert _is_footnote_run(text)
    assert _is_footnote_run(text, split_numbers_only=True)


def test_repealed_subsection_note_is_provenance_not_an_operative_repeal():
    text = ('1.\nSee now the Code of Civil Procedure, 1908.\n'
            '2.\nCentral Acts, Vol. III.\n'
            '3.\nSubs. for the words Local Government by the A.O., 1937.\n'
            '4.\nSub-section repealed by Punjab Act VIII of 1926, s.6.\n')
    assert _is_footnote_run(text, split_numbers_only=True)


def test_split_contents_and_operative_amending_sections_are_not_notes():
    assert not _is_footnote_run('1.\nShort title.\n2.\nDefinitions.\n3.\nRepeal.\n')
    assert not _is_footnote_run(
        '1.\nThis Act may be called the Amendment Act.\n'
        '2.\nIn the said Act, section 9 shall be omitted.\n'
        '3.\nFor section 10, the following shall be substituted.\n')


def test_trailing_notes_cannot_swallow_their_leading_operative_sentence():
    assert not _is_footnote_run(
        'The Government shall publish the rules.\n'
        '1.\nSubs. by Act I of 1955.\n2.\nIns. by Act II of 1956.\n'
        '3.\nSubs. by Act III of 1957.\n', split_numbers_only=True)


def test_numeric_table_and_unordered_marker_runs_are_not_proven_notes():
    assert not _is_footnote_run('1.\n1000\n2.\n2000\n3.\n3000\n')
    assert not _is_footnote_run('1.\nSubs. by Act I.\n3.\nIns. by Act II.\n2.\nSubs. by Act III.\n')


def test_inline_detection_is_not_broadened_in_the_split_only_body_path():
    text = '1. Subs. by Act I.\n2. Ins. by Act II.\n3. Subs. by Act III.\n'
    assert _is_footnote_run(text)
    assert not _is_footnote_run(text, split_numbers_only=True)


def test_original_subsection_renumbering_note_and_preamble_note_are_apparatus():
    assert _is_footnote_run(
        '1.\nThe Preamble omitted. Ibid, s. 3.\n'
        '2.\nSubs. by Punjab Act I of 1942.\n'
        '3.\nThe original sub-section (2) re-numbered as sub-section (3), '
        'by Punjab Act XI of 1942, s. 4 (a).\n'
        '4.\nIns. by Punjab Act II of 1944.\n', split_numbers_only=True)


def test_two_provenance_notes_never_vouch_for_a_numbered_law_paragraph():
    assert not _is_footnote_run(
        '1.\nThis Act may be called the Amendment Act.\n'
        '2.\nSubs. by Act I of 1955.\n3.\nIns. by Act II of 1956.\n',
        split_numbers_only=True)
    assert not _is_footnote_run(
        '1.\nSubs. by Act I of 1955.\n2.\nIns. by Act II of 1956.\n'
        '3.\nThe Government shall make rules.\n', split_numbers_only=True)
    assert not _is_footnote_run(
        '1.\nSee now the Code of Civil Procedure, 1908.\n'
        '2. Subs. by Act I of 1955.\n3. Ins. by Act II of 1956.\n'
        '4. The Government shall make rules.\n', split_numbers_only=True)


def test_real_land_preservation_source_retains_law_and_all_blocks():
    blocks = json.loads((Path(__file__).parent / 'fixtures' /
                        'split-notes-1927.json').read_text(encoding='utf-8'))
    original = deepcopy(blocks)
    result = segment(blocks)
    assert blocks == original
    assert result.repeated_labels_demoted == 0
    assert set(result.block_roles) == {b['id'] for b in blocks}
    for block_id in (136526, 136616, 136626):
        assert result.block_roles[block_id][0] == 'footnote'
    by_label = {n.label: n for n in result.flatten() if n.kind == 'section'}
    assert by_label['1'].first_page == by_label['2'].first_page == 3
    assert by_label['15'].first_page == by_label['16'].first_page == 15
    assert by_label['17'].first_page == by_label['18'].first_page == 16
    assert by_label['19'].first_page == 16
    assert 'publish' in by_label['22'].children[-1].text.casefold()


def test_provenance_vocabulary_never_overrides_unquoted_operative_modality():
    for operative in (
        'The words "civil court" shall be omitted by this Act.',
        'The provisions of section 5 shall be amended by the Government in the prescribed manner.',
        'The original words may be amended by the Government.',
    ):
        assert not _is_footnote_run(
            f'1.\n{operative}\n2.\nSubs. by Act I of 1955.\n'
            '3.\nIns. by Act II of 1956.\n', split_numbers_only=True)
    assert _is_footnote_run(
        '1.\nThe words “the Government shall make rules” omitted by Punjab Act I of 1944.\n'
        '2.\nSubs. by Act I of 1955.\n3.\nIns. by Act II of 1956.\n',
        split_numbers_only=True)


def test_mukhtiarkars_courts_source_boundary_and_first_sections_are_retained():
    blocks = json.loads((Path(__file__).parent / 'fixtures' /
                        'split-notes-2960.json').read_text(encoding='utf-8'))
    original = deepcopy(blocks)
    result = segment(blocks)
    assert blocks == original
    assert not result.missing and result.repeated_labels_demoted == 0
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert [n.label for n in sections] == [str(i) for i in range(1,27)]
    assert [n.first_page for n in sections[:5]] == [3,3,3,4,4]
    assert result.block_roles[280159][0] == 'footnote'
    assert set(result.block_roles) == {b['id'] for b in blocks}
    assert 'shall preside over a Court' in sections[4].children[0].text
    assert sum(n.kind == 'schedule' for n in result.flatten()) == 3
