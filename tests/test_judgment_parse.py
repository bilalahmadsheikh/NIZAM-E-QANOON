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
    head = [ln.replace("of 2020", "of 2015") for ln in HEADER[:-1]] + ["Date of hearing: 10.09.2015"]
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


AJK = {"supreme court of azad jammu and kashmir": "AJKSC", "high court of azad jammu and kashmir": "AJKHC",
       "supreme appellate court gilgit baltistan": "GBSAC"}
AJK_TYPES = {"AJKSC:CPLA": ("leave_petition", ["civil pla"]), "GBSAC:CA": ("appeal", ["civil appeal"])}


def test_ajk_and_gb_judgments_are_dated_as_their_courts_print_them():
    # /11 (D-142): the AJK Supreme Court signs 'JUDGE / Mirpur / 25.11.2020' at its seat; a blank day stays undated
    head = ["SUPREME COURT OF AZAD JAMMU AND KASHMIR", "[Appellate Jurisdiction]", "PRESENT:", "Alpha Beta, J.",
            "Civil PLA No.123 of 2020", "(Filed on 21.11.2020)", "Rehana Rasheed ...PETITIONER", "VERSUS",
            "Shumaila Sabir ...RESPONDENT", "Date of hearing: 25.11.2020"]
    body = ["ORDER:", "Alpha Beta, J.- The petition is directed against the order of the Service Tribunal.",
            "The PLA stands disposed of in the manner indicated above.", "JUDGE"]
    r = parse_judgment(doc([head + body + ["Mirpur", "25.11.2020"]]), AJK, AJK_TYPES, expected_court="AJKSC",
                       today=TODAY)
    assert isinstance(r, ParsedJudgment), r
    assert (r.decided_on, r.decided_on_basis, r.seat) == (dt.date(2020, 11, 25), "signed_at", "Mirpur")
    r = parse_judgment(doc([head + body + ["Mirpur,", "__.11.2020"]]), AJK, AJK_TYPES, expected_court="AJKSC",
                       today=TODAY)
    assert r.decided_on is None and r.decided_on_basis == "undated"
    # the GB Supreme Appellate Court prints its detailed judgment's date in the header
    head = ["IN THE SUPREME APPELLATE COURT GILGIT-BALTISTAN,", "SKARDU REGISTRY.", "BEFORE:-",
            "Mr. Justice Alpha Beta, Chief Judge.", "Civil Appeal No.04/2016", "Muhammad ...PETITIONER.", "VERSUS",
            "Yousuf ...RESPONDENT.", "DATE OF HEARING: - 05.10.2016.", "DATE OF DETAIL JUDGMENT: - 03.11.2016.",
            "JUDGMENT", "Alpha Beta, Chief Judge.- The appeal arises out of the impugned judgment.",
            "The appeal is dismissed in above terms.", "Chief Judge.", "Judge."]
    r = parse_judgment(doc([head]), AJK, AJK_TYPES, expected_court="GBSAC", today=TODAY)
    assert isinstance(r, ParsedJudgment), r
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2016, 11, 3), "date_of_decision")
    # 'Announced:- 03-11-2016.' with its dash
    no_detail = [x for x in head if not x.startswith("DATE OF DETAIL")]
    r = parse_judgment(doc([no_detail + ["Announced:- 04-11-2016."]]), AJK, AJK_TYPES, expected_court="GBSAC",
                       today=TODAY)
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2016, 11, 4), "announced")


def test_lahore_today_and_plural_dates_of_hearing():
    # /12 (D-142): 'Announced in open Court today i.e. 02.02.2011.'; 'Dates of hearing' bounds an undated judgment
    head = [ln.replace("Date of hearing: 26.01.2023", "Dates of hearing 21.01.2011") for ln in HEADER]
    head = [ln.replace("of 2020", "of 2010") for ln in head]
    body = ["JUDGMENT", "Alpha Beta, J.- The petition is dismissed.", "Judge"]
    r = parsed(doc([head + body + ["Announced in open Court today i.e. 02.02.2011.", "Judge"]]))
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2011, 2, 2), "announced")
    r = parsed(doc([head + body + ["Judge"]]))
    assert r.decided_on is None and (r.decided_not_before, r.decided_not_before_basis) == (dt.date(2011, 1, 21),
                                                                                          "hearing")


def test_an_order_dated_line_dates_the_order_but_an_impugned_order_never_does():
    head = ["IN THE SUPREME APPELLATE COURT GILGIT-BALTISTAN,", "GILGIT.", "BEFORE:-",
            "Mr. Justice Alpha Beta, Chief Judge.", "Civil Appeal No.04/2016", "Muhammad ...PETITIONER.", "VERSUS",
            "Yousuf ...RESPONDENT."]
    body = ["ORDER", "Alpha Beta, Chief Judge.- The impugned order dated 11.06.2016 passed by the Chief Court is set "
            "aside.", "The appeal is allowed.", "Chief Judge.", "Judge."]
    r = parse_judgment(doc([head + ["Order Dated 07-10-2016"] + body]), AJK, AJK_TYPES, expected_court="GBSAC",
                       today=TODAY)
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2016, 10, 7), "date_of_order")
    r = parse_judgment(doc([head + body]), AJK, AJK_TYPES, expected_court="GBSAC", today=TODAY)
    assert r.decided_on is None and r.decided_on_basis == "undated"      # 'impugned order dated' dates nothing


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


def test_a_decision_date_before_the_case_year_makes_the_judgment_undated():
    # D-138: 'C.P. No. D-1544 of 2026' read as decided on 02.03.1989 (an earlier order's date, or a misprint)
    head = HEADER[:-1] + ["Date of hearing: 10.09.2015"]                  # Civil Petition No.600 of 2020
    r = parsed(doc([head + ["ORDER", "Alpha Beta, J.- The petition is dismissed.", "Judge",
                            "Announced in open Court at Islamabad on 18.09.2015.", "Judge"]]))
    assert r.decided_on is None and r.decided_on_basis == "undated"
    assert r.undated_reason.startswith("the decision date read (2015-09-18") and "case year 2020" in r.undated_reason
    # the hearing printed is before the case year too, so it is not the bound: the case year is
    assert (r.decided_not_before, r.decided_not_before_basis) == (dt.date(2020, 1, 1), "case_year")
    # a date in the case's own year stands
    r = parsed(doc([HEADER[:-1] + ["ORDER", "Alpha Beta, J.- The petition is dismissed.", "Judge",
                                   "Announced in open Court at Islamabad on 18.09.2020.", "Judge"]]))
    assert r.decided_on == dt.date(2020, 9, 18)


def test_a_reading_with_no_body_text_is_held_not_released():
    # D-138: SHC C.P. D-649/2020 parsed to a header and a closing only; audit A25 refuses a bodyless judgment
    r = parse_judgment(doc([HEADER + ["ORDER", "Judge", "Announced in open Court at Islamabad on 18.09.2023.", "Judge"]]),
                       ALIASES, TYPES, expected_court="SC", today=TODAY)
    assert isinstance(r, Held) and "no body text" in r.reason


def test_the_federal_constitutional_courts_heading_and_author_line():
    # D-139: 'JUDGMENT OF THE COURT', then 'JUSTICE AAMER FAROOQ:'; the bench lines in the header are not authors
    aliases = dict(ALIASES, **{"federal constitutional court of pakistan": "FCC"})
    types = {"FCC:FCPLA": ("leave_petition", ["f c p l a", "fcpla"])}
    head = ["FEDERAL CONSTITUTIONAL COURT OF PAKISTAN", "(Appellate Jurisdiction)", "Present:",
            "Justice AAMER FAROOQ", "Justice ROZI KHAN BARRECH",
            "F.C.P.L.A. No. 642 of 2026", "(Against judgment dated 24.12.2025, passed by the Lahore High Court)",
            "Muhammad Ali …Petitioner(s)", "Versus", "Federation of Pakistan …Respondent(s)",
            "Date of Hearing : 30.06.2026"]
    body = ["JUDGMENT OF THE COURT", "JUSTICE AAMER FAROOQ: - The question is whether leave should be granted.",
            "2.", "Leave is refused.", "Judge", "Announced in open Court at Islamabad on 07.07.2026.", "Judge"]
    r = parse_judgment(doc([head + body]), aliases, types, expected_court="FCC", today=TODAY)
    assert isinstance(r, ParsedJudgment), r
    assert (r.court_code, r.case_type_code, r.case_number, r.case_year) == ("FCC", "FCC:FCPLA", "642", 2026)
    assert r.opinions[0].author_printed == "AAMER FAROOQ, J." and r.decided_on == dt.date(2026, 7, 7)
    assert [p.printed_no for p in r.paragraphs if p.kind == "body"] == [None, "2"]


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


# ------------------------------------------------------------------------------------- High Court layouts (D-128)

LHC_TYPES = {"LHC:CRLMISC": ("misc_application", ["crl misc", "criminal misc"]),
             "LHC:WP": ("writ", ["writ petition", "w p", "wp"]),
             "LHC:FAO": ("appeal", ["f a o", "fao"])}


def lhc(d) -> ParsedJudgment | Held:
    return parse_judgment(d, ALIASES, LHC_TYPES, expected_court="LHC", today=TODAY)


ORDER_SHEET = ["Form No: HCJD/C-121", "ORDER SHEET", "IN THE LAHORE HIGH COURT, MULTAN BENCH, MULTAN",
               "JUDICIAL DEPARTMENT", "Crl. Misc. No. 3952-B/2025", "Maqbool Ali", "Versus", "The State etc.",
               "Sr.No.of order/", "Proceedings", "Date of order/", "Proceedings",
               "Order with signatures of Judge, and that of parties or counsel,", "where necessary.",
               "20.02.2025", "Mr. Naveed Ahmad Khawaja, Advocate for the petitioner.",
               "Through this petition, the petitioner seeks post arrest bail in case FIR No.1573.",
               "2.", "The allegation as set out in the crime report is that heroin was recovered.",
               "3.", "For the reasons recorded, this petition is dismissed.", "(MUHAMMAD AMJAD RAFIQ)", "JUDGE"]


def test_an_order_sheet_is_dated_by_its_date_of_order_and_its_form_title_is_not_a_heading():
    r = lhc(doc([ORDER_SHEET]))
    assert isinstance(r, ParsedJudgment), r
    assert r.court_code == "LHC" and r.seat == "Multan"
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2025, 2, 20), "date_of_order")
    assert r.case_type_code == "LHC:CRLMISC" and r.case_number == "3952-B" and r.case_year == 2025
    assert [o.kind for o in r.opinions] == ["order_of_court"]
    body = [p for p in r.paragraphs if p.kind == "body"]
    assert [p.printed_no for p in body] == [None, "2", "3"]
    assert "Sr.No.of order" not in " ".join(p.text for p in body)      # column labels are header


def test_an_order_sheet_opening_a_second_proceeding_with_another_date_is_undated():
    second = ORDER_SHEET[:-2] + ["27.02.2025", "Mr. X, Advocate for the petitioner.", "Order reserved.",
                                 "(MUHAMMAD AMJAD RAFIQ)", "JUDGE"]
    r = lhc(doc([second]))
    assert r.decided_on is None and r.undated_reason.startswith("several order dates")


JUDGMENT_SHEET = ["Stereo. H C J D A 38.", "Judgment Sheet", "LAHORE HIGH COURT LAHORE", "JUDICIAL DEPARTMENT",
                  "F.A.O. No.68910 of 2022", "Oil Marketing Association of Pakistan", "Versus",
                  "Oil Companies Advisory Council and 02 others", "J U D G M E N T", "Date of Hearing",
                  "29.10.2025", "For the appellant", "Mr. Ahmad Ali Ranjha, Advocate.",
                  "Raheel Kamran J:- The instant First Appeal from Order has been filed under Section 21(4).",
                  "2.", "By the impugned order, the Committee allowed the appeal.", "No order as to costs.",
                  "(RAHEEL KAMRAN)", "JUDGE", "Announced in the Open Court on ___________", "JUDGE",
                  "Approved for reporting."]


def test_hearing_and_counsel_after_the_heading_are_header_and_a_blank_announcement_dates_nothing():
    r = lhc(doc([JUDGMENT_SHEET]))
    assert isinstance(r, ParsedJudgment), r
    assert r.hearing_on == dt.date(2025, 10, 29)
    assert r.decided_on is None and r.decided_on_basis == "undated"
    assert (r.decided_not_before, r.decided_not_before_basis) == (dt.date(2025, 10, 29), "hearing")
    assert r.opinions[0].author_printed and r.opinions[0].author_printed.startswith("Raheel Kamran")
    body = " ".join(p.text for p in r.paragraphs if p.kind == "body")
    assert "Advocate" not in body and body.startswith("Raheel Kamran J:- The instant First Appeal")


def test_signed_on_and_pronounced_on_are_printed_dates():
    signed = [x.replace("29.10.2025", "10.02.2025") for x in JUDGMENT_SHEET[:-3]] + ["Signed on 25.02.2025", "JUDGE"]
    assert lhc(doc([signed])).decided_on == dt.date(2025, 2, 25)
    said = JUDGMENT_SHEET[:-3] + ["This judgment has been dictated, pronounced on 13.03.2023 and signed later."]
    r = lhc(doc([[x.replace("29.10.2025", "01.03.2023") for x in said]]))
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2023, 3, 13), "announced")


def test_a_judge_word_wrapped_onto_its_own_line_does_not_end_the_order():
    lines = ORDER_SHEET[:16] + ["The petitioner challenges the order of the learned Civil", "Judge",
                                "Sahiwal dated 25-1-2001 which was not sustainable in law."] + \
        [f"line {k} of the reasons continues here." for k in range(45)] + ORDER_SHEET[-2:]
    r = lhc(doc([lines]))
    body = " ".join(p.text for p in r.paragraphs if p.kind == "body")
    assert "Sahiwal dated 25-1-2001" in body and "line 44 of the reasons" in body


def test_a_case_line_after_case_no_or_an_enumerator_is_read():
    for line in ("Case No. Writ Petition No.2849/2011", "1. W.P. No.2849 of 2011"):
        lines = [x if x != "F.A.O. No.68910 of 2022" else line for x in JUDGMENT_SHEET]
        r = lhc(doc([lines]))
        assert (r.case_type_code, r.case_number, r.case_year) == ("LHC:WP", "2849", 2011), line


def test_a_reprint_opening_with_its_series_is_not_landed():
    reprint = ["PLJ 2020 Lahore 555 (DB)", "[Rawalpindi Bench Rawalpindi]", "Present: A AND B, JJ.",
               "HABIB BANK LTD.--Appellant", "versus", "ZAWAR HUSSAIN SHAH--Respondent",
               "R.F.A. No. 26 of 2012, decided on 4.11.2020.",
               "Financial Institutions (Recovery of Finances) Ordinance, 2001--",
               "----Ss. 9(2) & 22--Bankers Book Evidence Act, 1891, S. 2(8)--Suit for recovery--Dismissed--",
               "Statement of account--Non-availability of date--Challenge to--"] + ["text"] * 20
    r = lhc(doc([reprint]))
    assert isinstance(r, Held) and r.outcome == "reporter_reprint"


def test_a_garbled_text_layer_goes_to_ocr_and_a_clean_one_records_its_score():
    """J9 (D-130): a court's own rough OCR is not released as citable text."""
    from nizam.corpus.judgment import plausibility
    garbled = ("IN TIIE PESIIAWAR IIIGII COUITT ll:e pctitioncr hns approachcd thc Court tlrrough tlris pctition "
               "agninst thc ordcr dntcd ") * 30
    clean = ("The petitioner has approached this Court through this petition against the order passed by the "
             "learned trial court which dismissed the application filed under the law ") * 20
    assert plausibility(garbled)[0] < 0.90 < plausibility(clean)[0]
    assert plausibility("too short")[0] is None
    lines = ORDER_SHEET[:15] + [garbled[k:k + 90] for k in range(0, len(garbled), 90)] + ORDER_SHEET[-2:]
    r = lhc(doc([lines]))
    assert isinstance(r, Held) and r.outcome == "needs_ocr" and r.reason.startswith("J9")
    ok = lhc(doc([ORDER_SHEET[:15] + [clean[k:k + 90] for k in range(0, len(clean), 90)] + ORDER_SHEET[-2:]]))
    assert isinstance(ok, ParsedJudgment) and ok.detail["plausibility"] > 0.9


def test_peshawar_prints_announced_with_a_stop_and_dated():
    from nizam.corpus.judgment import _ANNOUNCED
    for text, day in (("Announced. 14.11.2017", dt.date(2017, 11, 14)), ("Announced: 13.10.2020.", dt.date(2020, 10, 13)),
                      ("ANNOUNCED. Dated: 22/07/2015.", dt.date(2015, 7, 22)), ("Announced. Dt: 18.5.2016", dt.date(2016, 5, 18)),
                      ("Announced in open Court on 18.09.2015.", dt.date(2015, 9, 18))):
        m = _ANNOUNCED.search(text)
        assert m and read_date(m.group(0), TODAY) == day, text


# ------------------------------------------------------------------------------- headless orders (D-146, parser /13)

HC_ALIASES = dict(ALIASES, **{"supreme appellate court gilgit baltistan": "GBSAC"})
HC_TYPES = {"PHC:WP": ("writ", ["writ petition", "w p", "wp"]),
            "SHC:CRLACQA": ("appeal", ["crl acquittal appeal", "criminal acquittal appeal"]),
            "SHC:CP": ("writ", ["constt petition", "constitution petition", "const petition", "c p"]),
            "GBSAC:CPLA": ("leave_petition", ["cpla"])}


def hc(d, court):
    return parse_judgment(d, HC_ALIASES, HC_TYPES, expected_court=court, today=TODAY)


def test_a_sindh_author_line_closed_by_a_semicolon_but_never_a_bench_line():
    # Peshawar's OCR'd 'FAZAL SUBHAN. J.-' (a stop before the title) is not taken: those files' case lines read
    # wrong, so they stay held for the OCR lane (D-146)
    phc = ["PESHAWAR HIGH COURT, ABBOTTABAD BENCH", "JUDICIAL DEPARTMENT", "JUDGMENT SHEET",
           "Writ Petition No. 584-A/2022", "Date of hearing : 06.12.2022",
           "Petitioner (Sayyab Khan) By Mr. Aqeel, Advocate.", "Respondents (Mst. Tayyaba) By Mr. Munib, Advocate.",
           "FAZAL SUBHAN. J.- By way of this writ petition the petitioner has prayed for the relief below.",
           "2.", "For the reasons recorded, the petition is dismissed.", "JUDGE", "Announced. 14.12.2022"]
    held = hc(doc([phc]), "PHC")
    assert isinstance(held, Held) and held.reason.startswith("no JUDGMENT/ORDER heading")
    shc = ["JUDGMENT SHEET IN THE HIGH COURT OF SINDH, CIRCUIT COURT, LARKANA",
           "Crl.Acquittal Appeal No.D-39 of 2022.", "Before:", "Mr. Justice Adnan Iqbal Chaudhry,",
           "Mr. Justice Zulfiqar Ali Sangi,", "04. For hearing of main case.", "14.03.2023",
           "Mr. Suhail Ahmed Veesar, Advocate for appellant.",
           "ZULFIQAR ALI SANGI, J;- Through the listed appeal the appellant has impugned the judgment of acquittal.",
           "2.", "For the reasons recorded, the appeal is dismissed.", "JUDGE", "JUDGE"]
    r = hc(doc([shc]), "SHC")
    assert isinstance(r, ParsedJudgment), r
    assert r.opinions[0].author_printed.startswith("ZULFIQAR ALI SANGI")
    # a sentence ending in a capital and a stop is never an author line
    from nizam.corpus.judgment import _author
    assert _author("The appeal is allowed. J.") is None and _author("In view of the above. J.-") is None
    assert _author("Muhammad Saleem Jessar J; Adnan-ul-Karim Memon, J; For hearing of main case") is None


def test_a_wrapped_or_misread_order_sheet_column_header_opens_the_order():
    sheet = ["ORDER SHEET", "IN THE HIGH COURT OF SINDH, CIRCUIT COURT, LARKANA",
             "Constt. Petition No. D-722 of 2016", "Date Order with srgnature of", "Hon'ble Judge",
             "For orders on maintainability", "23.11.2016", "None present for the petitioner.",
             "Mr. Ali Akber Kalhoro, State Counsel",
             "None is present for the petitioner. Same was the position on the last date of hearing. It appears that "
             "after filing this petition the petitioner lost interest; it is dismissed for non-prosecution.", "JUDGE"]
    r = hc(doc([sheet]), "SHC")
    assert isinstance(r, ParsedJudgment), r
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2016, 11, 23), "date_of_order")
    assert [o.kind for o in r.opinions] == ["order_of_court"]
    wrapped = sheet[:3] + ["DATE ORDER WITH SIGNATURE OF", "JUDG"] + sheet[5:]
    assert isinstance(hc(doc([wrapped]), "SHC"), ParsedJudgment)


GB_ORDER = ["IN THE SUPREME APPELLATE COURT GILGIT-BALTISTAN", "CPLA No. 02/2010",
            "Before: Mr. Justice Muhammad Nawaz Abbasi, Chief Judge. Mr. Justice Syed Jaffar Shah, Judge.",
            "Muhammad Naseem s/o Abdul Sadique Petitioner. Versus Zafar Iqbal MD NATCO",
            "PETITION FOR LEAVE TO APPEAL UNDER ARTICLE 60 (11)(12) OF THE ORDER",
            "Mr. Ehsan Ali Advocate for Petitioner", "Order Dated: 08­06­2010",
            "These connected petitions have been directed against the judgment dated 28­09­2009 passed by the "
            "Chief Court in a Civil Revision.", "2.", "The leave is refused.", "Chief Judge.", "Judge."]


def test_an_order_dated_line_opens_a_headless_order_and_dates_it():
    r = hc(doc([GB_ORDER]), "GBSAC")
    assert isinstance(r, ParsedJudgment), r
    assert (r.decided_on, r.decided_on_basis) == (dt.date(2010, 6, 8), "date_of_order")   # soft hyphens read
    assert [o.kind for o in r.opinions] == ["order_of_court"]
    body = " ".join(p.text for p in r.paragraphs if p.kind == "body")
    assert body.startswith("These connected petitions") and "Advocate" not in body
    # without the line nothing marks where the order begins: still held, never guessed
    bare = [x for x in GB_ORDER if not x.startswith("Order Dated")]
    held = hc(doc([bare]), "GBSAC")
    assert isinstance(held, Held) and held.reason.startswith("no JUDGMENT/ORDER heading")


def test_sindh_date_of_hearing_and_decision_in_the_header_dates_the_judgment():
    for label in ("Date of hearing & decision:", "Date of hearing\n& decision:", "Date of hearing and Judgment:",
                  "Date of hearing& decision :"):
        sheet = ["IN THE HIGH COURT OF SINDH, CIRCUIT COURT, LARKANA", "Constt. Petition No. D-722 of 2016",
                 "Mr. Ali Akber Kalhoro, Advocate for the petitioner.", label, "10.12.2025.", "ORDER",
                 "ADNAN IQBAL CHAUDHRY, J.- The petitioner seeks the relief prayed in the petition.",
                 "2.", "For the reasons recorded, the petition is dismissed.", "JUDGE"]
        r = hc(doc([sheet]), "SHC")
        assert isinstance(r, ParsedJudgment), (label, r)
        assert (r.decided_on, r.decided_on_basis) == (dt.date(2025, 12, 10), "date_of_decision"), label
    # a hearing alone never dates the judgment
    alone = ["IN THE HIGH COURT OF SINDH, CIRCUIT COURT, LARKANA", "Constt. Petition No. D-722 of 2016",
             "Date of hearing:", "10.12.2025.", "ORDER",
             "ADNAN IQBAL CHAUDHRY, J.- The petitioner seeks the relief prayed in the petition.", "JUDGE"]
    assert hc(doc([alone]), "SHC").decided_on is None
