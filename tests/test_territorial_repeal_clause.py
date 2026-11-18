"""tools/record_territorial_repeals.clause_territory: which territory a provincial repeal clause confines itself to.

The Balochistan Antiquities Act, 2014 s.41(1) repeals 'The Antiquities Act, 1975 (Act No.VII of 1976) as applicable
to the extent of the Province of Balochistan' (D-078). Before 18 Nov 2026 the 'as applicable to' branch read
'the extent of the Province of Balochistan' as the place and skipped the clause, so the federal Act stayed served in
Balochistan.

`qual` is the recorder's REPEAL group: the words between the year and 'is ... repealed', up to and including the
comma the print sets before 'is'; `after` is the rest of the sentence."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from record_territorial_repeals import clause_territory  # noqa: E402


def test_as_applicable_to_the_extent_of_the_repealers_own_province():
    terr, why = clause_territory(' (Act No.VII of 1976) as applicable to the extent of the Province of Balochistan,',
                                 '', 'balochistan')
    assert (terr, why) == ('balochistan', "the clause confines the repeal to the repealer's territory")


def test_as_applicable_to_a_province_without_the_extent_words_still_reads():
    assert clause_territory(' as applicable to the Province of Sindh,', '', 'sindh')[0] == 'sindh'


def test_the_extent_words_never_admit_another_territory():
    assert clause_territory(' as applicable to the extent of the Province of the Punjab,', '', 'balochistan') == (
        None, "skipped: the qualifier names another territory than the repealer's")


def test_an_unread_place_is_still_skipped():
    assert clause_territory(' as applicable to the extent of the Tribal Areas,', '', 'balochistan') == (
        None, 'skipped: the qualifier names a place not read')


def test_to_the_extent_of_ict_after_the_verb_is_unchanged():
    assert clause_territory('', ' to the extent of Islamabad Capital Territory.', 'ict')[0] == 'ict'


def test_a_provincial_act_without_a_qualifier_repeals_for_its_own_province():
    assert clause_territory('', '', 'kp') == ('kp', 'a provincial Act repeals for its own province')
