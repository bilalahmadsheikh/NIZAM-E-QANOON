"""tools/record_provision_repeals.py: partial repeals read from the corpus's own clauses (migration 0102).

The clauses are the corpus's, verbatim or nearly. The negatives are the shapes the 17 Nov 2026 survey found that are
NOT a repeal of a unit: an amendment of words inside a section, a unit of a schedule 'to' another law, a saving
reference to a section.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import record_provision_repeals as pr  # noqa: E402


def units(text):
    return pr.parse_units(text)


def test_a_range_inside_a_chapter_is_one_range():
    assert units("Sections 121 to 147 contained in Chapter XVI") == [
        {"kind": "range", "unit": "section", "lo": 121, "hi": 147}]


def test_a_list_with_lettered_sections_keeps_each_label():
    got = units("section 2 and sections 43,44,45,46,47, 48, 49, 50, 51, 51A, 51B, 52, 53, and 54")
    labels = [u["label"] for u in got]
    assert labels[0] == "2" and "51A" in labels and "51B" in labels and labels[-1] == "54" and len(labels) == 15


def test_hyphenated_letters_fold_to_one_label():
    assert [u["label"] for u in units("Sections 13-A, 13-B, and 13C")] == ["13A", "13B", "13C"]


def test_a_sub_section_of_a_section_and_sections_mix():
    assert units("section 7, sub-section (2) of section 27 and section 28") == [
        {"kind": "section", "label": "7"}, {"kind": "subsection", "section": "27", "label": "2"},
        {"kind": "section", "label": "28"}]


def test_both_inclusive_range():
    assert units("sections 12 to 21 (both inclusive)") == [{"kind": "range", "unit": "section", "lo": 12, "hi": 21}]


def test_parts_and_articles():
    assert units("Part VIIIA") == [{"kind": "part", "label": "VIIIA"}]
    assert [u["label"] for u in units("Articles 3, 4, 5, 6 and 8")] == ["3", "4", "5", "6", "8"]


def test_words_amended_inside_a_section_are_not_a_unit_list():
    assert units("in section 2, the words \"and except the Jhansi Division\"") is None
    assert units("section 1, sub-section (2), the words") is None


def test_the_clause_reads_the_law_and_year_after_the_units():
    c = pr.clauses("Sections 121 to 147 contained in Chapter XVI of the Sindh Local Government Ordinance 1979 "
                   "are hereby repealed.")
    assert len(c) == 1 and c[0]["title"] == "Sindh Local Government Ordinance" and c[0]["year"] == 1979
    assert c[0]["verb"] == "repealed" and c[0]["units"][0]["lo"] == 121
    c = pr.clauses("(2) section 7 of the Civil Aviation Ordinance, 1960 (Ordinance XXXII of 1960) is hereby "
                   "repealed.")
    assert c and c[0]["title"] == "Civil Aviation Ordinance" and c[0]["year"] == 1960
    assert c[0]["units"] == [{"kind": "section", "label": "7"}]


def test_a_unit_of_a_schedule_to_another_law_is_not_read():
    # 'Part III of the Second Schedule to the Balochistan Local Government Act 2010' -- 'to the', not 'of the' law
    c = pr.clauses("Part III of Second Schedule to the Balochistan Local Government Act 2010 shall be omitted.")
    assert all(x["units"] is None or x["title"] != "Balochistan Local Government Act" for x in c)


HELD = [  # (relative path, kind, label, text)
    ("ch_XVI", "chapter", "XVI", "TAXATION"),
    ("ch_XVI.s_121", "section", "121", "Levy of taxes. The Council may levy ..."),
    ("ch_XVI.s_122", "section", "122", "Manner of levy ..."),
    ("ch_XVI.s_122A", "section", "122A", "Rates ..."),
    ("ch_XVI.s_123", "section", "123", "Omitted."),
    ("s_27", "section", "27", "Powers."),
    ("s_27.ss_1", "subsection", "1", "The Authority may ..."),
    ("s_27.ss_2", "subsection", "2", "The Government may ..."),
    ("s_28", "section", "28", "Appeal. 3[Any person aggrieved ...]"),
    ("sch_FIRST.s_5", "section", "5", "a schedule's own numbering"),
    ("s_5", "section", "5", "Definitions ..."),
]


def test_a_range_resolves_to_every_held_section_in_it_including_inserted_ones():
    got, why, _missing = pr.resolve_units([{"kind": "range", "unit": "section", "lo": 121, "hi": 123}], HELD)
    assert why is None and [r for r, _ in got] == ["ch_XVI.s_121", "ch_XVI.s_122", "ch_XVI.s_122A", "ch_XVI.s_123"]


def test_a_schedule_section_is_never_the_law_s_section():
    got, why, _missing = pr.resolve_units([{"kind": "section", "label": "5"}], HELD)
    assert why is None and got == [("s_5", "section 5")]


def test_a_sub_section_resolves_under_its_section():
    got, why, _missing = pr.resolve_units([{"kind": "subsection", "section": "27", "label": "2"}], HELD)
    assert why is None and got == [("s_27.ss_2", "sub-section (2) of section 27")]


def test_a_unit_the_held_text_lacks_is_counted_and_the_others_still_resolve():
    # 2722: 'Clause (5) of section 2 and sections 43 ... 54 of the Patents and Designs Act, 1911': the consolidation
    # no longer prints clause (5); sections 43-54 are still named and still held
    got, why, missing = pr.resolve_units([{"kind": "section", "label": "5"}, {"kind": "section", "label": "99"}], HELD)
    assert got == [("s_5", "section 5")] and why is None and missing == 1
    got, why, missing = pr.resolve_units([{"kind": "section", "label": "99"}], HELD)
    assert got == [] and why == "unit not in the held text" and missing == 1


def test_a_unit_already_printed_omitted_or_carrying_an_amendment_mark_is_not_recorded():
    texts = {rp: tx for rp, _k, _l, tx in HELD}
    assert pr.unit_state("ch_XVI.s_123", texts) == "reflected"
    assert pr.unit_state("s_28", texts) == "marked"      # '3[' -- may have been re-enacted after the repeal
    assert pr.unit_state("s_27.ss_2", texts) == "live"


def _plan(text, repealer=("rep", "sindh", "act", "Karachi Water Act", 1996, 2, 0, None),
          target=("tgt", "sindh", "ordinance", "Sindh Local Government Ordinance", 1979, 1, 0, None),
          currency=None):
    instruments = [repealer, target]
    return pr.plan(instruments, [(repealer[0], "s_150", 77, text)], lambda t: HELD,
                   currency or {"rep": "current", "tgt": "current"}, {"tgt": ["sindh"]})


def test_the_whole_path_records_live_units_and_reports_reflected_ones():
    rows, stats = _plan("Sections 121 to 123 contained in Chapter XVI of the Sindh Local Government Ordinance 1979 "
                        "are hereby repealed.")
    assert [r["repealed_relative_path"] for r in rows] == ["ch_XVI.s_121", "ch_XVI.s_122", "ch_XVI.s_122A"]
    assert all(r["territory"] is None for r in rows) and stats["unit reflected"] == 1


def test_a_lapsed_ordinance_s_partial_repeal_is_not_recorded():
    rows, stats = _plan("Section 5 of the Sindh Local Government Ordinance 1979 is hereby repealed.",
                        repealer=("rep", "sindh", "ordinance", "Sindh X Ordinance", 1996, 2, 0, None),
                        currency={"rep": "not_current", "tgt": "current"})
    assert rows == [] and stats["skipped: repealer is neither an Act nor current"] == 1


def test_a_province_repealing_part_of_a_federal_law_does_so_for_itself():
    rows, _ = pr.plan(
        [("rep", "punjab", "act", "Punjab X Act", 2025, 2, 0, None),
         ("tgt", "fed", "act", "Civil Aviation Ordinance", 1960, 1, 0, None)],
        [("rep", "s_40", 77, "Section 5 of the Civil Aviation Ordinance, 1960 is hereby repealed.")],
        lambda t: HELD, {"rep": "current", "tgt": "current"}, {"tgt": ["punjab", "sindh"]})
    assert len(rows) == 1 and rows[0]["territory"] == "punjab"


def test_words_after_the_verb_in_the_same_jurisdiction_skip_the_clause():
    rows, stats = _plan("Section 5 of the Sindh Local Government Ordinance 1979 is hereby repealed in so far as it "
                        "relates to the Karachi Division.")
    assert rows == [] and stats["skipped: words follow the verb"] == 1


# --- the shapes the second pass reads (17 Nov 2026), verbatim from the corpus ---

def test_the_provisions_of_and_a_leading_dash_are_read():
    c = pr.clauses("The provisions of section 9 of the Sindh Finance Act, 1994 are hereby repealed.")
    assert c and c[0]["units"] == [{"kind": "section", "label": "9"}] and c[0]["title"] == "Sindh Finance Act"
    c = pr.clauses("– Section 12 of the Probation of Offenders Ordinance, 1960 (XLV of 1960) is hereby omitted.")
    assert c and c[0]["verb"] == "omitted" and c[0]["units"] == [{"kind": "section", "label": "12"}]


def test_a_unit_inside_a_list_of_whole_enactments_is_read():
    c = pr.clauses("The Islamabad Local Government Ordinance, 2002 (LVII of 2002) and section 15-A of the Capital "
                   "Development Authority Ordinance, 1960 (XXIII of 1960) are hereby repealed.")
    hit = [x for x in c if x["title"] == "Capital Development Authority Ordinance"]
    assert hit and hit[0]["units"] == [{"kind": "section", "label": "15A"}]


def test_whole_enactments_after_the_unit_s_law_do_not_stop_it():
    c = pr.clauses("The Agricultural Produce Market Act, 1939 (IV of 1939), and sections 86 to 94 of the Balochistan "
                   "Local Government Ordinance, 1980 (II of 1980), and the Balochistan Agricultural Produce Markets "
                   "Ordinance, 1991 (I of 1991), are hereby repealed.")
    hit = [x for x in c if x["title"] == "Balochistan Local Government Ordinance"]
    assert hit and hit[0]["units"] == [{"kind": "range", "unit": "section", "lo": 86, "hi": 94}]


def test_two_laws_named_by_units_in_one_list_are_both_read():
    c = pr.clauses("Sub-sections (2) to (6) of section 10, sub- section (2) of section 28 and section 29 of the Lahore "
                   "Development Authority Act, 1975 (XXX of 1975), and clause (xvi) of sub-section (2) of section 7, "
                   "sub-section (2) of section 27 and section 28 of the Punjab Development of Cities Act, 1976 "
                   "(XIX of 1976) are hereby repealed.")
    by = {x["title"]: x["units"] for x in c}
    lda = by["Lahore Development Authority Act"]
    assert [u["label"] for u in lda if u["kind"] == "subsection" and u["section"] == "10"] == ["2", "3", "4", "5", "6"]
    assert {"kind": "section", "label": "29"} in lda
    pdc = by["Punjab Development of Cities Act"]
    assert pdc[0] == {"kind": "clause", "section": "7", "sub": "2", "label": "XVI"}
    assert {"kind": "section", "label": "28"} in pdc


def test_a_clause_of_a_section_and_the_comma_before_a_citation():
    c = pr.clauses("Clause (5) of section 2 and sections 43,44,45,46,47, 48, 49, 50, 51, 51A, 51B, 52, 53, and 54 of "
                   "the Patents and Designs Act, 1911, (II of 1911) are hereby repealed.")
    assert c and c[0]["title"] == "Patents and Designs Act" and c[0]["year"] == 1911
    assert c[0]["units"][0] == {"kind": "clause", "section": "2", "sub": None, "label": "5"}


def test_a_printed_date_between_shall_and_stand_is_the_repeal_date():
    import datetime
    c = pr.clauses("Articles 3, 4, 5, 6 and 8 of the Distribution of Revenues Order, 1953 shall, as from the first "
                   "day of July, 1962, stand repealed.")
    assert c and c[0]["from"] == datetime.date(1962, 7, 1) and [u["label"] for u in c[0]["units"]] == \
        ["3", "4", "5", "6", "8"]


def test_rules_made_under_a_section_in_relation_to_a_subject_are_not_read():
    # 4001: '... section 7 of the Civil Aviation Ordinance, 1960 ... and the rules made thereunder in relation to the
    # subject matter of this Act shall stand repealed' -- partial by subject, not a unit repeal
    c = pr.clauses("On the commencement of this Act, section 7 of the Civil Aviation Ordinance, 1960 (Ordinance "
                   "XXXII of 1960) and the rules made thereunder in relation to the subject matter of this Act shall "
                   "stand repealed.")
    assert c == []


def test_a_clause_resolves_under_its_sub_section():
    held = HELD + [("s_27.ss_2.cl_xvi", "clause", "xvi", "the Authority shall ...")]
    got, why, _missing = pr.resolve_units([{"kind": "clause", "section": "27", "sub": "2", "label": "XVI"}], held)
    assert why is None and got == [("s_27.ss_2.cl_xvi", "clause (xvi) of sub-section (2) of section 27")]


# --- whole repeals that except named units (migration 0103) ---

COMPANIES = [  # the held 1984 Ordinance files Part VIIIA's sections under Part VIII and prints no Part VIIIA heading
    ("pt_VIII", "part", "VIII", "MANAGEMENT AND ADMINISTRATION"),
    ("pt_VIII.s_282", "section", "282", "Application of sections 261 to 281 to liquidators"),
    ("pt_VIII.s_282_A", "section", "282 A", "Application of this Part."),
    ("pt_VIII.s_282CA", "section", "282CA", "..."),
    ("pt_VIII.s_282_D", "section", "282.D", "Power to issue directions."),
    ("pt_VIII.s_282_N", "section", "282 N", "Rehabilitation of NBFCs."),
    ("pt_IX.s_283", "section", "283", "Power for companies to refer matters to arbitration."),
]


def test_lettered_sections_of_one_number_are_a_range():
    assert units("sections 282A to 282N") == [
        {"kind": "letter_range", "unit": "section", "num": 282, "lo": "A", "hi": "N"}]


def test_the_companies_ordinance_save_clause_keeps_part_viiia_s_sections():
    c = pr.save_clauses("(1) The Companies Ordinance, 1984 (XLVII of 1984), hereinafter called as repealed "
                        "Ordinance, shall stand repealed, except Part VIIIA consisting of sections 282A to 282N, from "
                        "the date of coming into force of this Act")
    assert len(c) == 1 and c[0]["title"].endswith("Companies Ordinance") and c[0]["year"] == 1984
    assert c[0]["readings"] == ["Part VIIIA", "sections 282A to 282N"]
    got, why = pr.resolve_survivals(c[0]["readings"], COMPANIES)
    # no Part VIIIA is held, so the second reading decides; 282 itself and 283 are not kept
    assert why is None and [g[0] for g in got] == ["pt_VIII.s_282_A", "pt_VIII.s_282CA", "pt_VIII.s_282_D",
                                                    "pt_VIII.s_282_N"]


PIA = [("s_7", "section", "7", "⸻(1) The name of the Company shall not be changed without the consent ..."),
       ("s_7.ss_2", "subsection", "2", "The Headquarters of the Company ... shall be at Karachi.")]


def test_a_sub_section_held_as_its_section_s_own_words_survives_as_that_node_alone():
    for text in ("(1) The Pakistan International Airlines Corporation (Conversion) Act, 2016 (XV of 2016) is hereby "
                 "repealed except sub-section (1) of section 7 of the repealed Act.",
                 "(1) The Pakistan International Airlines Corporation (Conversion) Act, 2016 (XV of 2016), except "
                 "sub-section (1) of section 7 is hereby repealed."):
        c = pr.save_clauses(text)
        assert len(c) == 1 and c[0]["title"].endswith("(Conversion) Act") and c[0]["year"] == 2016
        got, why = pr.resolve_survivals(c[0]["readings"], PIA)
        assert why is None and got == [("s_7", "sub-section (1) of section 7", False)]


def test_an_exception_that_does_not_resolve_records_nothing():
    c = pr.save_clauses("The Foo Act, 1990 is hereby repealed except section 99.")
    got, why = pr.resolve_survivals(c[0]["readings"], PIA)
    assert got == [] and why == "an excepted unit is not in the held text"
