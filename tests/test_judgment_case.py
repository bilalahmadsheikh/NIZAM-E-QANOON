"""Case identity grammar (D-125): case keys, the numbers a case line joins, the reasons statement, copies.

Every printed form below was seen in the Supreme Court archive (23 Nov 2026)."""
from __future__ import annotations

import datetime as dt

from nizam.corpus.judgment_case import (announces_reasons_later, case_key, copy_score, read_case_line,
                                        reasons_statement, shingles)

CA = ["civil appeal", "civil appeals", "c a", "c as", "ca", "cas"]
CONSTP = ["constitution petition", "constitution petitions", "const p", "const ps"]
CMA = ["civil miscellaneous application", "civil misc application", "civil misc applications", "c m a", "cma"]
D = dt.date


def test_the_key_is_the_case_as_printed_and_leading_zeros_are_not_part_of_it():
    assert case_key("SC", "SC:CONSTP", "05", 2012) == case_key("SC", "SC:CONSTP", "5", 2012) == "SC/CONSTP/5/2012"
    assert case_key("SC", "SC:CA", "801-l", 2013) == "SC/CA/801-L/2013"


def test_appeals_printed_together_are_each_a_case():
    r = read_case_line("Civil Appeals No. 1507 and 1508 of 2024", CA)
    assert (r.lead, r.year, r.joined) == ("1507", 2024, ["1508"])
    r = read_case_line("Civil Appeal Nos.981, 984 and 985 of 2018", CA)
    assert (r.lead, r.year, r.joined) == ("981", 2018, ["984", "985"])
    r = read_case_line("CIVIL APPEALS NO.545 TO 550 OF 2015", CA)
    assert (r.lead, r.year, r.joined) == ("545", 2015, ["546", "547", "548", "549", "550"])


def test_hyphen_ranges_expand_but_a_seat_suffix_is_part_of_the_number():
    r = read_case_line("CONSTITUTION PETITIONS NOS. 11-15, 18-22, 24 & 39-41/2010", CONSTP)
    assert r.lead == "11" and r.year == 2010
    assert r.joined == ["12", "13", "14", "15", "18", "19", "20", "21", "22", "24", "39", "40", "41"]
    r = read_case_line("Civil Appeals No.800-L and 801-L of 2013", CA)
    assert (r.lead, r.joined) == ("800-L", ["801-L"])
    r = read_case_line("(CA 801-L/2013)", CA)
    assert (r.lead, r.year, r.joined) == ("801-L", 2013, [])
    misc = ["crl misc", "criminal misc"]
    assert read_case_line("Crl. Misc. 2143-CB of 2021.", misc).lead == "2143-CB"        # cancellation of bail
    assert read_case_line("Crl. Misc. No. 3952-B/2025", misc).lead == "3952-B"
    r = read_case_line("CR. No.259-D-2005/BWP", ["cr"])
    assert (r.lead, r.year) == ("259-D", 2005)


def test_a_seat_suffix_after_a_slash_is_part_of_the_number_and_a_slash_year_stays_a_year():
    # D-157: the Federal Shariat Court's 'No.01/K OF 2022' and Lahore's 'No.853/B/2014'
    ca = ["criminal appeal", "jail criminal appeal"]
    assert (lambda r: (r.lead, r.year))(read_case_line("Criminal Appeal No.01/K OF 2022", ca)) == ("1-K", 2022)
    assert (lambda r: (r.lead, r.year))(read_case_line("Jail Criminal Appeal NO. 07/I OF 2024", ca)) == ("7-I", 2024)
    assert (lambda r: (r.lead, r.year))(read_case_line("CRIMINAL APPEAL NO. 04-P OF 2025", ca)) == ("4-P", 2025)
    misc = ["crl misc"]
    assert (lambda r: (r.lead, r.year))(read_case_line("Crl.Misc.No.853/ B/2014/BWP", misc)) == ("853-B", 2014)
    assert (lambda r: (r.lead, r.year))(read_case_line("Crl. Misc. No. 3952/2025", misc)) == ("3952", 2025)


def test_an_application_of_another_type_in_the_line_is_not_another_case():
    r = read_case_line("C.M.A. NO.3470 OF 2013 IN C.M.A. NO.1536 OF 2013", CMA)
    assert (r.lead, r.year, r.joined) == ("3470", 2013, [])
    r = read_case_line("Constitution Petition No.05/2012 and CMA Nos.2382, 2487", CONSTP)
    assert (r.lead, r.year, r.joined) == ("5", 2012, [])


def test_the_lead_is_the_first_number_after_the_type_not_a_number_of_another_type():
    # the header parser read 13124-P here (the HRC); this grammar reads 77, so the builder sees the disagreement
    r = read_case_line("Const. P.77 of 2010 and HRCs No.13124-P, 40303-P", CONSTP)
    assert (r.lead, r.year) == ("77", 2010)


def test_the_number_after_the_forms_unread_tail_and_no_as_the_text_layer_prints_it():
    crlp = ["criminal petition", "crl p", "cr p"]
    cp = ["civil petition", "civil petitions", "c p", "c ps", "cp"]
    assert read_case_line("Crl.P.L.A. No.15 of 2015", crlp).lead == "15"
    assert read_case_line("Crl.P.L.A No.619-L of 2024", crlp).lead == "619-L"
    assert read_case_line("Civil Appeals No. Nil of 2021", CA).lead is None        # 'Nil' is not a number
    assert read_case_line("Civil Appeal No. 0 of 2005", CA).lead is None           # no case is numbered 0
    r = read_case_line("C.P.L.As.211 and 213 of 2024", cp)
    assert (r.lead, r.year, r.joined) == ("211", 2024, ["213"])
    assert read_case_line("Civil Petitions No, 2547 and 2640 of 2023", cp).joined == ["2640"]
    assert read_case_line("Civil Appeal NO-1496 of 2019", CA).lead == "1496"
    assert read_case_line("CIVIL APPEAL NO. 45—L  OF 2018", CA).lead == "45-L"
    assert read_case_line("Criminal Appeal No.07(S)/2011", ["criminal appeal"]).lead == "7-S"
    # the year that closes the lead's own list, not a later one ('1646 & 2000/2006': not 2000; '/2011', not 2009)
    r = read_case_line("CIVIL APPEALS NO.1646 & 2000/2006 AND CIVIL PETITION NO.782-K/2009", CA)
    assert (r.lead, r.year, r.joined) == ("1646", 2006, ["2000"])
    assert read_case_line("CMA No.1652/2013 in SMC No.16 of 2011", CMA).year == 2013


def test_seat_ranges_two_digit_years_and_a_range_too_wide_to_expand():
    r = read_case_line("Civil Appeals Nos.80-L to 83-L of 2014.", CA)
    assert (r.lead, r.year, r.joined) == ("80-L", 2014, ["81-L", "82-L", "83-L"])
    r = read_case_line("Constitution Petition No.105/12 alongwith CMAs-3795 & 3798 of", CONSTP, today=D(2026, 11, 23))
    assert (r.lead, r.year) == ("105", 2012)
    r = read_case_line("Civil Petitions No.240 & 241 K of 2013", ["civil petitions"])
    assert (r.lead, r.year, r.joined) == ("240", 2013, ["241-K"])
    r = read_case_line("CIVIL PETITIONS NO.943 TO 954-K OF 2022", ["civil petitions"])
    assert (r.lead, r.year, r.joined) == ("943", 2022, ["954-K"])          # suffixes differ: the end kept as printed
    r = read_case_line("CIVIL APPEAL NOs. 1631 TO 2212 OF 2017", CA)
    assert (r.lead, r.year, r.joined) == ("1631", 2017, ["2212"])           # wider than RANGE_MAX: not expanded
    assert read_case_line("CIVIL PETITION NO. 611-L 2018", ["civil petition"]).year == 2018


def test_a_list_that_does_not_end_in_a_year_joins_nothing_and_a_wild_range_stops_the_reading():
    assert read_case_line("Civil Appeals No.10-0 and 1273 of 2021", CA).joined == []
    r = read_case_line("Civil Appeals No. 12 and 13", CA)
    assert (r.lead, r.year, r.joined) == ("12", None, [])


def test_reasons_for_our_short_order_read_with_its_date():
    s = reasons_statement(["The above are the detailed reasons of our short order dated 07.12.2020."], D(2020, 12, 7))
    assert (s.short_order_on, s.date_basis) == (D(2020, 12, 7), "printed")
    s = reasons_statement(["Foregoing are the reasons for our short order dated 02.08.2022, which is reproduced "
                           "here for convenience:- For reasons to be recorded later"], D(2022, 8, 20))
    assert s.short_order_on == D(2022, 8, 2)
    s = reasons_statement(["The foregoing sums up the detailed judgment of this Court’s short order delivered on "
                           "26.05.2009 in terms of which Civil Review Petitions"], None)
    assert s.short_order_on == D(2009, 5, 26)


def test_of_even_date_is_the_judgments_own_date_and_names_none_when_it_is_undated():
    s = reasons_statement(["35. The aforesaid are the detailed reasons of our short Oder of event date, which reads"],
                          D(2018, 10, 17))
    assert (s.short_order_on, s.date_basis) == (D(2018, 10, 17), "even_date")
    s = reasons_statement(["These are reasons for our short order of even date."], None)
    assert (s.short_order_on, s.date_basis) == (None, "not_printed")
    s = reasons_statement(["Above are the reasons for our short order pronounced on even date."], D(2024, 7, 26))
    assert (s.short_order_on, s.date_basis) == (D(2024, 7, 26), "even_date")
    s = reasons_statement(["These are the detailed reasons for the short order announced by us on 31.05.2013 which "
                           "reads as follows"], D(2013, 6, 20))
    assert (s.short_order_on, s.date_basis) == (D(2013, 5, 31), "printed")


def test_the_short_order_date_printed_earlier_in_the_paragraph():
    s = reasons_statement(["Accordingly, instant petition was dismissed vide our short order dated 19.06.2025. Above "
                           "are the reasons of such short order, which reads as under:"], D(2025, 6, 19))
    assert (s.short_order_on, s.date_basis) == (D(2025, 6, 19), "paragraph")
    s = reasons_statement(["Since they involved similar issues, they were heard and decided together and a short "
                           "order was announced on 04.03.2011. These are the detailed reasons for the same."], None)
    assert s.short_order_on == D(2011, 3, 4)


def test_a_reasons_statement_quoted_from_an_earlier_order_is_not_this_judgments_and_of_today_is_its_date():
    quoted = ("The order of this Court read: “The petitioner was heard. These are the reasons in support of our short "
              "order dated 13.08.2015 whereby we dismissed this petition.” It is this paragraph that is of concern.")
    assert reasons_statement([quoted], D(2018, 6, 14)) is None
    s = reasons_statement(["These are the detailed reasons for our short order of today which is reproduced below"],
                          D(2017, 1, 12))
    assert (s.short_order_on, s.date_basis) == (D(2017, 1, 12), "even_date")


def test_a_short_order_says_its_reasons_will_follow():
    assert announces_reasons_later(["For reasons to be recorded later, this petition is converted into appeal."])
    assert announces_reasons_later(["For the reasons to follow separately, notice dated 31.07.2013 is withdrawn."])
    assert announces_reasons_later(["x", "For detailed reasons to be recorded later and subject to what is set out"])
    assert not announces_reasons_later(["The appeal is dismissed. These are the reasons for our short order."])


def test_another_courts_short_order_or_reasons_still_to_come_is_not_a_reasons_statement():
    assert reasons_statement(["The petition before us challenges the short order dated 10 January 2024, followed by "
                              "the twenty-six page judgment of the Peshawar High Court"], None) is None
    assert reasons_statement(["For reasons to be recorded later, this petition is converted into an appeal and "
                              "allowed."], D(2021, 10, 21)) is None
    assert reasons_statement(["vide short order1 dated 12.12.2023 the Balochistan High Court allowed the "
                              "constitution petition"], None) is None


def test_two_copies_of_one_decision_overlap_and_two_orders_of_one_case_do_not():
    body = " ".join(f"word{i} of the judgment in this case" for i in range(400))
    assert copy_score(shingles(body), shingles(body + " Sd/- Judge")) > 0.95
    other = " ".join(f"word{i} of the order passed on another day" for i in range(400))
    assert copy_score(shingles(body), shingles(other)) < 0.2
    assert copy_score(set(), shingles(body)) == 0.0


def test_cases_listed_in_a_header_are_decided_together_but_the_court_below_is_not():
    from nizam.corpus.judgment_case import header_cases
    forms = {"LHC:MR": ["murder reference", "m r"], "LHC:CRLA": ["criminal appeal", "crl appeal"],
             "LHC:CRLREV": ["criminal revision", "crl revision"], "LHC:WP": ["writ petition", "w p"]}
    head = ("JUDGMENT SHEET IN THE LAHORE HIGH COURT, LAHORE JUDICIAL DEPARTMENT Murder Reference No.290 of 2015 "
            "The State v. Rizwan Akhtar Criminal Appeal No.1112-J of 2015 Rizwan Akhtar v. The State "
            "3. Crl. Revision No.392 of 2013 (Muhammad Shahzad v. Allah Ditta)")
    got = [(c, x.lead, x.year) for c, x in header_cases(head, forms)]
    assert got == [("LHC:MR", "290", 2015), ("LHC:CRLA", "1112-J", 2015), ("LHC:CRLREV", "392", 2013)]
    below = ("Criminal Appeal No.12 of 2020 (Against the judgment dated 04.02.2020 passed in Writ Petition No.67 of "
             "2019 by the learned Single Judge)")
    assert [(c, x.lead) for c, x in header_cases(below, forms)] == [("LHC:CRLA", "12")]
    sc = {"SC:CRLP": ["criminal petition"], "SC:REF": ["reference"], "SC:CP": ["c p", "civil petition"]}
    head = ("Criminal Petition No.12 of 2016 (On appeal against the judgment dated 21.10.2015 passed by the Lahore "
            "High Court, Lahore, in Criminal Appeal No.300-J/2013 and Murder Reference No.138/2011) "
            "C.P. No. 14 of 2016 (against the order of the High Court of Sindh passed in C.P.D-568/12 and "
            "C.P.No.11-D/2017)")
    assert [(c, x.lead) for c, x in header_cases(head, sc)] == [("SC:CRLP", "12"), ("SC:CP", "14")]


def test_a_law_reports_masthead_is_a_reprint_and_a_courts_own_sheet_is_not():
    from nizam.corpus.judgment import _REPRINT_MASTHEAD as M
    assert M.match("2010 P L C (C.S.) 1449 [Quetta High Court] Before Qazi Faez Isa C. J. and Muhammad Noor ...")
    assert M.match("• • • PLJ 2017 Quetta 60 (DB) Present: MRS. SYEDA TAHIRA SAFDAR AND ZAHEER-UD-DIN KAKAR, JJ.")
    assert M.match("2012PCr.LJ646 [Balochistan] Before Muhammad Hashim Khan Kakar and Muhammad Noor Meskanzai, JJ")
    assert M.match("PLJ 2018 Cr.C. (Quetta) 130 (DB) Present: ABDULLAH BALOCH & MUHAMMAD EJAZ SWATI, JJ.")
    assert M.match("2015 P L C (C.S.) 788 [Balochistan High Court] Qazi Faez Isa, C.J. and Muhammad Kamran Khan")
    assert M.match("H.B.T./60/Q 2011 M L D 1819 [Quetta] Before Naeem Akhtar Afghan and Muhammad Noor Meskanzai, JJ")
    assert not M.match("JUDGMENT SHEET IN THE HIGH COURT OF BALOCHISTAN, QUETTA Constitutional Petition No.682 of 2011")
    assert not M.match("C.P. No.337 of 2011 Page 1 of 5 Malik Naimat v. DG Mines and Minerals. JUDGMENT SHEET IN THE")
    from nizam.corpus.judgment import _DATE_OF_DECISION as DD
    for printed in ("Announced on 31.01.2020", "Announced on: 22.08.2013", "Date of Order : 11.06.2026",
                    "Date of hearing and Order: 09.03.2026", "Announcement of judgment: 16th August, 2013"):
        assert DD.search(printed), printed
    assert not DD.search("FIR No.884/2024 dated 23.10.2024")
    from nizam.corpus.judgment import _ORDER_COLUMNS as OC, _ORDER_DATE as OD
    for printed in ("Order with signatures of Judge", "DATE ORDER WITH SIGNATURE(S) OF JUDGE(S)",
                    "ORDER WITH THE SIGNATURE OF THE JUDGE", "ORDER WITH SIGNATURE OF HON'BLE JUDGE"):
        assert OC.search(printed), printed
    assert OD.match("Dated 19-01-2017 Mr. Ansar Hussain Zaidi") and not OD.match("FIR dated 23.10.2024")
    assert not M.match("ORDER SHEET IN THE HIGH COURT OF SINDH AT KARACHI C.P. No. D-5050 of 2025 Before: Mr. Justice")


def test_a_register_letter_before_the_number_is_part_of_it_and_listed_applications_are_not_cases():
    """Sindh (D-138): 'C.P. No. D-2606' (division bench) and 'S-1043' (single bench) are separate registers;
    an order sheet's 'For orders on M.A. No. ...' is an application before the court, not a case it decides."""
    cp = ["c p", "cp", "constitution petition"]
    r = read_case_line("C.P NO. D-2606 of 2018 [Anwar Khan & Others v. Zarai Taraqiati Bank]", cp)
    assert (r.lead, r.year) == ("D-2606", 2018)
    assert case_key("SHC", "SHC:CP", r.lead, r.year) == "SHC/CP/D-2606/2018"
    r = read_case_line("Cr. Bail Application No.S-1043 of 2022", ["cr bail application"])
    assert (r.lead, r.year) == ("S-1043", 2022)
    assert read_case_line("Civil Appeal No.800-L of 2013", CA).lead == "800-L"     # a suffix stays a suffix
    assert read_case_line("C.P. No.D-01 of 2016", cp).lead == "D-1"                  # no leading zero after it either
    assert case_key("SHC", "SHC:CP", "D-01", 2016) == "SHC/CP/D-1/2016"
    from nizam.corpus.judgment_case import header_cases
    forms = {"SHC:CP": cp, "SHC:MA": ["m a", "misc appeal"]}
    head = ("ORDER SHEET IN THE HIGH COURT OF SINDH, CIRCUIT COURT, HYDERABAD C.P NO. D-2606 of 2018 Dated: "
            "20.11.2025 For hearing on M.A No. 1056 of 2023")
    assert [(c, x.lead) for c, x in header_cases(head, forms)] == [("SHC:CP", "D-2606")]


def test_the_header_parser_keeps_the_register_letter_as_the_case_builder_does():
    """The judgment row's case number and the case key agree on 'D-1544' (D-138); 0135 lets the key hold it."""
    from nizam.corpus.judgment import _case
    types = {"SHC:CP": ("petition", ["constitutional petition", "c p"]), "SHC:CRLA": ("appeal", ["criminal appeal"])}
    assert _case(["Constitutional Petition No. D-1544 of 2026"], types)[2] == "D-1544"
    assert _case(["C.P.No.D- 920 of 2014"], types)[2] == "D-920"
    assert _case(["Criminal Appeal No. 125 of 2019"], types)[2] == "125"


def test_a_glued_register_is_read_and_a_section_number_is_never_a_case_number():
    """D-142 (/12): 'CP D101of 2012' printed its register letter and 'of' glued to the number, and the year 2012 was
    taken as the case number; 'CRIMINAL APPEAL UNDER SECTION 417' gave case number 417. A number needs a 'No.', a year
    or the case grammar's reading; a lower-case letter before digits is never a register."""
    from nizam.corpus.judgment import _case
    cp = ["c p", "cp"]
    r = read_case_line("CP D101of 2012 : Ghulam Asghar vs. District Education Officer", cp)
    assert (r.lead, r.year) == ("D-101", 2012)
    assert read_case_line("C.P. No.D-01 of 2016", cp).lead == "D-1"                  # the dashed form unchanged
    assert read_case_line("Civil Appeal No.d12 of 2016", CA).lead != "D-12"           # lower case: no register
    types = {"GBCC:CRLA": ("appeal", ["criminal appeal"]), "SHC:CP": ("petition", cp)}
    assert _case(["CRIMINAL APPEAL UNDER SECTION 417 CR.P.C IMPUGNED JUDGMENT"], types) is None
    assert _case(["Criminal Appeal N~2019 1- Said Rehman"], types) is None
    assert _case(["CP D101of 2012 : Ghulam Asghar"], types)[2:4] == ("D-101", 2012)
    assert _case(["Criminal Appeal No. 417"], types)[2] == "417"                    # 'No.' printed: kept


def test_the_header_parser_and_the_case_builder_read_one_number_and_year():
    """D-138 (/8): judgment.case_number and case_year are what read_case_line reads over the stored case line, so
    the case builder never finds them differing (judgment_case_state.header_differs)."""
    from nizam.corpus.judgment import _case
    types = {"SHC:CP": ("petition", ["constitutional petition", "c p"]),
             "SHC:CRLA": ("appeal", ["criminal appeal", "criminal appeals"]),
             "LHC:WP": ("writ", ["writ petition"])}
    for line in ["C.P. No.D-01 of 2016", "Criminal Appeal No. 05 of 2019", "Criminal Appeals Nos. 12 and 13 of 2019",
                 "C.P. No. D-1544/2026", "Writ Petition No.4-RWP of 2020", "Writ Petition No. 2143-CB/2015"]:
        code, printed, number, year, _ = _case([line], types)
        r = read_case_line(printed[:500], types[code][1])
        assert (number, year) == (r.lead, r.year), line
