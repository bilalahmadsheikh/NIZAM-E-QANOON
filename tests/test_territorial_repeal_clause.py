"""tools/record_territorial_repeals.clause_territory: which territory a provincial repeal clause confines itself to.

The Balochistan Antiquities Act, 2014 s.41(1) repeals 'The Antiquities Act, 1975 (Act No.VII of 1976) as applicable
to the extent of the Province of Balochistan' (D-078). Before 18 Nov 2026 the 'as applicable to' branch read
'the extent of the Province of Balochistan' as the place and skipped the clause, so the federal Act stayed served in
Balochistan.

`qual` is the recorder's REPEAL group: the words between the year and 'is ... repealed', up to and including the
comma the print sets before 'is'; `after` is the rest of the sentence."""
import sys
from pathlib import Path

import pytest

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


# D-103 (20 Nov 2026): the KP Maternity Benefits Act, 2013 s.18 -- 'repealed in its application to the province of the
# Khyber Pakhtunkhwa' -- went unread, and the 1958 Ordinance stayed served in KP (found by the gate's error analysis)
@pytest.mark.parametrize("qual,after,own", [
    ('', ' in its application to the province of the Khyber Pakhtunkhwa.', 'kp'),
    ('', ' to the extent of the Province of the Khyber Pakhtunkhwa.', 'kp'),
    (' in its application to the Balochistan Province', '', 'balochistan'),
    ('', ' to the extent of its applicability to the Province of Sindh.', 'sindh'),
    (' (Act No.XIV of 1920), in its application to the Province of Khyber Pakhtunkhwa,', '', 'kp'),
    (' (VIII of 2001), in its application to this Province,', '', 'kp'),
    (' (XVIII of 1980), to the extent of the Province', '', 'kp'),
    ('', ' in its application to the extent of the Province of the 2[Khyber Pakhtunkhwa].', 'kp'),
])
def test_own_province_wordings_are_read(qual, after, own):
    assert clause_territory(qual, after, own)[0] == own


def test_the_province_never_names_another_territory_and_a_federal_act_never_reads_it():
    assert clause_territory('', ' to the extent of the province.', 'ict')[0] is None
    assert clause_territory('', ' in its application to the province of the Punjab.', 'kp')[0] is None


def test_a_plural_is_folded_only_as_a_fallback():
    from record_territorial_repeals import fold_plural
    assert fold_plural('west pakistan maternity benefits ordinance') == 'west pakistan maternity benefit ordinance'
    # the KP Press Act's clause 'Press, Newspaper, News Agencies ...' against the held '... Newspapers, News Agencies ...'
    assert fold_plural('press newspapers news agencies and books registration ordinance') == \
        fold_plural('press newspaper news agencies and books registration ordinance')
    assert fold_plural('business process') == 'business process'     # a double 's' is not a plural
    assert fold_plural('companies act') == 'companie act'            # crude, but applied to both sides alike
