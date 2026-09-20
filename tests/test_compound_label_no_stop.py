"""An inserted-suffix label printed without its closing stop: "59.F Establishment".

Doc 02 §5.1. The Karachi Port Trust Act prints its inserted sections as
``59.F Establishment of sinking fund.`` -- a stop between the number and the
letter, and none after the letter -- while the Act's own contents prints
``59A.``, ``59B.``, ``59C.`` The opener already handled ``5.A.``, which requires
the trailing stop, so this form fell through to the plain ``\d+\.`` rule: the
label became "59", the F was eaten into the heading, and section 59F collided
with the real section 59 (bye-laws to be exhibited) and was demoted.

Measured before the fix: 46 blocks in 26 documents open this way; 28 kept only
the bare number while 7 (documents 4235 and 4495) kept the compound label
correctly. An inconsistency in the opener, not a missing capability.
"""
import pytest

from nizam.corpus.segment import classify


@pytest.mark.parametrize('text,label', [
    ('59.F Establishment of sinking fund. –3[ (1) in respect of every loan',
     '59.F'),
    ('51.O Whistle-blower disclosure.- A person may disclose information.', '51.O'),
    ('3.A Application.- This Act shall apply to every person.', '3.A'),
    ('72.B Appeal to Tribunal.- Any person aggrieved may appeal.', '72.B'),
])
def test_compound_label_without_a_closing_stop_is_kept(text, label):
    kind, got, _ = classify(text)
    assert (kind, got) == ('section', label)


@pytest.mark.parametrize('text', [
    # a schedule row: the next token starts with a digit, not a heading word
    '2.A 4Computer Programmer BPS-16',
    # scan noise: the next token is a lone capital
    '13.U V 11 13',
])
def test_the_guard_refuses_the_false_positive_families(text):
    """Each of these was found by reading all 46 blocks that open this way."""
    kind, got, _ = classify(text)
    assert kind == 'section'
    assert '.' not in got, f'{text!r} must not yield a compound label'


def test_a_section_ending_in_a_stop_does_not_absorb_the_next_clause():
    """The letter must sit against the dot; "5." then "A." on the next line
    is a section followed by a clause, not section 5.A."""
    kind, got, _ = classify('5.\nA. Introduction to the schedule')
    assert (kind, got) == ('section', '5')
