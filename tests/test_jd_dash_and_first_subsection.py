"""Agent JD's tests (14 Oct 2026) for rules `marked_dash_section_cut` (D) and `subsection_line_cut` (E) (doc 4234),
ported into nizam/corpus/segment.py by builder BZ (group 5). JD's draft ran them against its in-memory ON copy;
here `seg` is the live module, as JD's note directs. Assertions unchanged."""
import pytest

import nizam.corpus.segment as seg

S5_S6 = ("3[5.       Number of trustees - The Board shall consist of 4[eleven] members.] \n"
         "5[6. —(1) Appointment of Chairman and election of Vice-Chairman. Government shall from \n"
         "time to time appoint a person to be Chairman of the Board.] \n")
S12 = ("7[The Chairman shall hold office for such period as the 6[Federal Government] may \nfrom time to time decide]. \n"
       " \n8[12.— (1) Time for holding elections and making appointments.  (1) The \nelection of trustees ... \n")
PLAIN = "5. Number of trustees - The Board shall consist of members. \n6.—(1) Appointment of Chairman ... \n"
S15A = "1[15A. Grounds on which trustees shall vacate office. – \n2[(1)] Any trustee who – \n"
S2 = ("2. \nDefinitions – In this Act, unless there be something repugnant in the subject or \ncontext:- \n(1) \n"
      "“Port” means the port of Karachi; \n")


def pieces(text, var=None, texts=()):
    token = var.set(frozenset(texts)) if var is not None else None
    try:
        return seg.subdivide(text)
    finally:
        if token is not None:
            var.reset(token)


def test_D_inert_without_key():
    assert not any(p.lstrip().startswith("5[6.") for p in pieces(S5_S6))
    assert not any(p.lstrip().startswith("8[12.") for p in pieces(S12))


def test_D_cuts_listed_note_marked_dash_section():
    got = pieces(S5_S6, seg._JD_MDS_TEXTS, [S5_S6])
    assert any(p.lstrip().startswith("5[6. —(1)") for p in got)
    assert seg.classify(next(p for p in got if p.lstrip().startswith("5[6.")))[:2] == ("section", "6")
    got = pieces(S12, seg._JD_MDS_TEXTS, [S12])
    assert any(p.lstrip().startswith("8[12.—") for p in got)


def test_D_unlisted_block_is_inert_even_when_another_is_listed():
    assert not any(p.lstrip().startswith("5[6.") for p in pieces(S5_S6, seg._JD_MDS_TEXTS, [S12]))


def test_D_refuses_listed_block_without_note_marked_line():
    with pytest.raises(ValueError):
        pieces(PLAIN, seg._JD_MDS_TEXTS, [PLAIN])


def test_E_inert_without_key():
    assert not any(p.lstrip().startswith("2[(1)]") for p in pieces(S15A))
    assert not any(p.lstrip().startswith("(1)") for p in pieces(S2))


def test_E_cuts_closed_bracket_and_quoted_first_subsection():
    got = pieces(S15A, seg._JD_FSC_TEXTS, [S15A])
    assert any(p.lstrip().startswith("2[(1)] Any") for p in got)
    got = pieces(S2, seg._JD_FSC_TEXTS, [S2])
    assert any(p.lstrip().startswith("(1)") for p in got)


def test_E_refuses_listed_block_without_such_line():
    with pytest.raises(ValueError):
        pieces(PLAIN, seg._JD_FSC_TEXTS, [PLAIN])
