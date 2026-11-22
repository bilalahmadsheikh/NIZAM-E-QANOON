"""The judgment parser (nizam/corpus/judgment.py, D-118) and the judgment citation rules (D-119).

Synthetic documents pin each rule, including the failures each one exists to prevent:
- a decision date taken from the hearing or a folder;
- '302.' inside a sentence opening a paragraph;
- an invented paragraph number;
- the court below named as the deciding court.
Real Supreme Court files are checked where the archive is on this machine.
"""
from __future__ import annotations

import datetime as dt
import zipfile
from pathlib import Path

import pytest

from nizam.corpus.judgment import Held, ParsedJudgment, parse_judgment, read_date
from nizam.shared.corpus_types import ExtractedBlock, ExtractedDocument, ExtractedPage
from nizam.storage.judgment_linking import case_citations, quotation_after, statute_citations

TODAY = dt.date(2026, 11, 22)
ALIASES = {"supreme court of pakistan": "SC", "lahore high court": "LHC", "high court of sindh": "SHC",
           "peshawar high court": "PHC"}
TYPES = {"SC:CP": ("leave_petition", ["civil petition", "civil petitions", "c p"]),
         "SC:CA": ("appeal", ["civil appeal", "c a"]),
         "SC:JP": ("jail_petition", ["jail petition", "j p"])}


def doc(pages: list[list[str]], height: float = 800.0) -> ExtractedDocument:
    """A document whose pages each hold the given blocks, top to bottom; a block starting '@' sits at the foot."""
    blocks, ro, ps = [], 0, []
    for p, texts in enumerate(pages, 1):
        y = 40.0
        for t in texts:
            foot = t.startswith("@")
            t = t.lstrip("@")
            y0 = height * 0.85 if foot else y
            blocks.append(ExtractedBlock(p, len(blocks), ro, 50.0, y0, 500.0, y0 + 20, t, "latin"))
            ro += 1
            y += 25
        ps.append(ExtractedPage(p, 600.0, height, sum(len(t) for t in texts) + 400, "E2"))
    return ExtractedDocument("0" * 64, "en", "other", len(pages), sum(p.char_count for p in ps), 1.0, 0, "E2",
                             "test", {}, {}, ps, blocks)


HEADER = ["IN THE SUPREME COURT OF PAKISTAN", "(Appellate Jurisdiction)", "PRESENT:",
          "Mr. Justice Alpha Beta", "Mr. Justice Gamma Delta",
          "Civil Petition No.600 of 2020",
          "(Against the order of Lahore High Court, Lahore dated 04.02.2020 passed in WP No.67 of 2020)",
          "Attiq ur Rehman ...Petitioner(s)", "Versus", "Tahir Mehmood ...Respondent(s)",
          "For the petitioner(s): Dr. X, ASC.", "Date of hearing: 26.01.2023"]


def parsed(d) -> ParsedJudgment:
    r = parse_judgment(d, ALIASES, TYPES, expected_court="SC", today=TODAY)
    assert isinstance(r, ParsedJudgment), r
    return r


def test_dates_in_every_printed_form_and_never_in_the_future():
    assert read_date("Islamabad, the 19th January, 2021", TODAY) == dt.date(2021, 1, 19)
    assert read_date("Announced in open Court on 18.09.2015.", TODAY) == dt.date(2015, 9, 18)
    assert read_date("ISLAMABAD 20.04.2020", TODAY) == dt.date(2020, 4, 20)
    assert read_date("the 2nd of March 2020", TODAY) == dt.date(2020, 3, 2)
    assert read_date("January 26, 2023", TODAY) == dt.date(2023, 1, 26)
    assert read_date("31.02.2020", TODAY) is None                    # no such day
    assert read_date("01.01.2091", TODAY) is None                    # a misread year, after today


def test_a_judgment_is_dated_by_its_closing_not_its_hearing_or_folder():
    d = doc([HEADER + ["ORDER", "Alpha Beta, J.- Respondent No.1 challenged an inquiry under section 302. The "
                       "court issued notices.", "2.", "It is the settled policy of this Court not to interfere.",
                       "Accordingly, this petition is dismissed and leave refused.",
                       "Islamabad,", "26th January, 2023.", "Approved for reporting", "Judge", "Judge"]])
    r = parsed(d)
    # 'Islamabad, 26th January, 2023' sits after the order and before the signatures; the hearing was the same day
    assert r.decided_on == dt.date(2023, 1, 26) and r.hearing_on == dt.date(2023, 1, 26)
    assert r.case_type_code == "SC:CP" and r.case_number == "600" and r.case_year == 2020
    assert r.disposition == "leave_refused" and r.reported_flag is True
    assert r.lineage and r.lineage[0].lower_court_code == "LHC" and r.lineage[0].outcome == "leave_refused"
    assert r.lineage[0].lower_decided_on == dt.date(2020, 2, 4)
    assert r.bench_printed == ["Mr. Justice Alpha Beta", "Mr. Justice Gamma Delta"]


def test_paragraphs_open_only_on_the_next_printed_number_and_none_is_invented():
    head = HEADER[:-1] + ["Date of hearing: 10.09.2015"]
    d = doc([head + ["JUDGMENT", "Alpha Beta, J.- The petitioner was convicted under section", "302.",
                       "PPC and sentenced.", "2.", "The second paragraph.", "4.", "Not a paragraph: out of sequence.",
                       "3.", "The third paragraph.", "Judge", "Announced in open Court at Islamabad on 18.09.2015.",
                       "Judge"]], )
    r = parsed(d)
    body = [p for p in r.paragraphs if p.kind == "body"]
    assert [p.printed_no for p in body] == [None, "2", "3"]          # '302.' and '4.' open nothing
    assert "302. PPC and sentenced" in body[0].text
    assert "4. Not a paragraph" in body[1].text
    assert r.decided_on == dt.date(2015, 9, 18) and r.decided_on_basis == "announced"
    assert r.opinions[0].kind == "judgment_of_court" and r.opinions[0].author_printed == "Alpha Beta, J."


def test_no_printed_decision_date_is_released_undated_not_guessed():
    # D-124: released marked undated; the hearing bounds it from below and is never taken as the date
    d = doc([HEADER + ["ORDER", "Alpha Beta, J.- The petition is dismissed.", "Judge", "Judge",
                       "Announced in Open Court on at Islamabad"]])
    r = parsed(d)
    assert (r.decided_on, r.decided_on_basis, r.decided_on_printed) == (None, "undated", None)
    assert r.undated_reason.startswith("no printed decision date")
    assert (r.decided_not_before, r.decided_not_before_basis) == (dt.date(2023, 1, 26), "hearing")
    assert r.seat is None


def test_a_date_line_after_the_last_paragraph_is_the_date_not_the_next_paragraph():
    # '12.02.2026' after paragraph 11 once opened a paragraph '12' and hid the date (D-124)
    paras = ["Alpha Beta, J.- Facts."] + [x for n in range(2, 12) for x in (f"{n}.", f"Paragraph {n}.")]
    d = doc([HEADER + ["JUDGMENT"] + paras + ["Leave to appeal is refused.", "LAHORE", "12.02.2026", "(Farrukh)",
                                              "Approved for Reporting"]])
    r = parsed(d)
    assert [p.printed_no for p in r.paragraphs if p.kind == "body"][-1] == "11"
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2026, 2, 12), "signed_at")


def test_ordinals_as_printed_and_blanks_filled_by_hand():
    assert read_date("Islamabad, the 22d December, 2021.", TODAY) == dt.date(2021, 12, 22)
    assert read_date("ANNOUNCED ON  _14th _January, 2011", TODAY) == dt.date(2011, 1, 14)


def test_without_a_hearing_the_case_year_bounds_an_undated_judgment():
    d = doc([HEADER[:-1] + ["ORDER", "Alpha Beta, J.- The petition is dismissed.", "Judge", "Judge"]])
    r = parsed(d)
    assert r.decided_on is None and (r.decided_not_before, r.decided_not_before_basis) == (dt.date(2020, 1, 1),
                                                                                           "case_year")


def test_a_hearing_after_the_date_read_makes_the_judgment_undated_and_is_not_trusted_as_a_bound():
    d = doc([HEADER + ["ORDER", "Alpha Beta, J.- The petition is dismissed.", "Judge",
                       "Announced in open Court at Islamabad on 18.09.2015.", "Judge"]])
    r = parsed(d)
    assert r.decided_on is None and r.undated_reason.startswith("hearing 2023-01-26 is after")
    assert r.decided_not_before_basis == "case_year"


def test_the_deciding_court_is_the_one_the_first_lines_print():
    # a misspelt court line must not resolve to the High Court named in the appeal line below it
    h = ["IN THE SUREME COURT OF PAKISTAN"] + HEADER[1:]
    r = parse_judgment(doc([h + ["ORDER", "X, J.- Dismissed.", "Islamabad 01.02.2023", "Judge"]]),
                       ALIASES, TYPES, expected_court="SC", today=TODAY)
    assert isinstance(r, Held) and "court not resolved" in r.reason


def test_a_case_line_broken_word_by_word_is_read_whole():
    h = HEADER[:5] + ["Jail", "Petition", "No. 787/2018"] + HEADER[6:]
    r = parsed(doc([h + ["JUDGMENT", "X, J.- Dismissed.", "Islamabad 01.02.2023", "Judge"]]))
    assert r.case_type_code == "SC:JP" and r.case_number == "787" and r.case_year == 2018


def test_footnotes_and_page_numbers_are_their_own_paragraphs():
    p1 = HEADER + ["ORDER", "X, J.- The relief was arbitrary1. We have examined it.",
                   "@1 Muhammad Sadiq v. Bashir Ahmad, PLD 1966 SC 717; 1996 SCMR 1528."]
    p2 = ["2", "2.", "The petition is dismissed.", "Islamabad 26.01.2023", "Judge"]
    r = parsed(doc([p1, p2]))
    notes = [p for p in r.paragraphs if p.kind == "footnote"]
    assert len(notes) == 1 and notes[0].printed_no == "1" and "PLD 1966 SC 717" in notes[0].text
    assert any(p.kind == "furniture" and p.text == "2" for p in r.paragraphs)
    assert all("PLD 1966" not in p.text for p in r.paragraphs if p.kind == "body")


def test_a_reporter_reprint_is_not_landed():
    d = doc([["2014 M L D 446 [Peshawar] Before A and B, JJ AMIR---Appellant Versus The STATE---Respondent",
              "Penal Code (XLV of 1860)--- ----S. 302(b)---Qatl-e-amd---Appreciation of evidence---"]])
    r = parse_judgment(d, ALIASES, TYPES, today=TODAY)
    assert isinstance(r, Held) and r.outcome == "reporter_reprint"


# ------------------------------------------------------------------------------------------------- the links

def test_statute_citations_carry_their_role():
    t = ("The petitioner was booked in FIR No.751 registered under Section 489-F PPC. The words of section 497(2) "
         "Cr.P.C. must be construed strictly. Section 9(c) of the Control of Narcotic Substances Act, 1997 was "
         "said to be ultra vires.")
    got = {(c.label, c.role) for c in statute_citations(t)}
    assert ("489-F", "charge") in got
    assert ("497", "interpreted") in got
    assert ("9", "challenged") in got


def test_case_citations_are_identifiers_only():
    t = ("See Muhammad Sadiq v. Bashir Ahmad, PLD 1966 SC 717; Salah-Ud-Din v. Zia, 1996 SCMR 1528 and the order "
         "in Civil Appeal No. 123 of 2015.")
    got = case_citations(t)
    assert [(c.series, c.year, c.court, c.page) for c in got if c.series] == [("PLD", 1966, "SC", 717),
                                                                              ("SCMR", 1996, None, 1528)]
    k = [c for c in got if c.case_type][0]
    assert (k.case_type, k.case_number, k.case_year) == ("civil appeal", "123", 2015)


def test_a_quotation_after_a_citation_is_found():
    t = 'Section 497 reads: "When any person accused of any non-bailable offence is arrested or detained."'
    assert quotation_after(t, len("Section 497")).startswith("When any person accused")


# -------------------------------------------------------------------------------------------- real SC files

ARCHIVE = Path("/mnt/e/nizam-data/scp_judgments.zip")


@pytest.fixture(scope="module")
def real():
    if not ARCHIVE.exists():
        pytest.skip("the Supreme Court archive is not on this machine")
    from nizam.corpus.extract import extract_pdf
    z = zipfile.ZipFile(ARCHIVE)
    try:
        from nizam.storage.judgment_write import reference_data
        aliases, types = reference_data()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")

    def read(member):
        return parse_judgment(extract_pdf(z.read(member), "0" * 64), aliases, types, expected_court="SC",
                              today=TODAY)
    return read


def test_a_2020_folder_judgment_decided_in_2023(real):
    r = real("scp_judgments/2020/c.p._600_2020.pdf")
    assert isinstance(r, ParsedJudgment)
    assert r.decided_on == dt.date(2023, 1, 26)                     # the folder is the case year
    assert r.disposition == "leave_refused" and r.lineage[0].lower_court_code == "LHC"


def test_an_announced_judgment_and_its_reporting_note(real):
    r = real("scp_judgments/2015/C.P._2532_2015.pdf")
    assert isinstance(r, ParsedJudgment)
    assert (r.decided_on, r.decided_on_basis, r.reported_flag) == (dt.date(2015, 9, 18), "announced", False)
    assert r.lineage[0].lower_court_code == "SHC"
