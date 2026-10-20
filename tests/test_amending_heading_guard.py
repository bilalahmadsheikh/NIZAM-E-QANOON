"""Rule `amending_heading_guard` (ungated, every profile; stage 3, agent DA, owner 11 Oct 2026).

With no contents list, a section is named by its first sentence-like span. In an amending or repealing section that
span is the section's own enacting words: doc 31 s.2 'In the Provincial Motor Vehicles Ordinance, 1965, for section
23-A, the following shall be substituted:- "23-A' ran into the quoted inserted section, and doc 428 s.3 '... is hereby
repealed.' enacted a repeal. Such a span is not a heading: the section keeps no heading and its text is the whole
printed body, in order. Ordinary first-sentence headings are unchanged.
"""
from nizam.corpus import segment as S


def _blocks(*texts):
    return [{"id": i, "text": t, "page_no": 1, "y0": 100.0 + 20 * i, "page_height": 792.0, "x0": 72.0, "x1": 480.0}
            for i, t in enumerate(texts)]


def _sections(seg):
    return {n.label: (n.heading, n.text) for n in seg.flatten() if n.kind == "section"}


def test_the_predicate():
    f = S._amending_heading_span
    assert f("In the Provincial Motor Vehicles Ordinance, 1965, for section 23-A, the following shall be "
             "substituted:- “23-A")
    assert f('In section 5, for the words "Government" the words "Provincial Government')       # odd straight quotes
    assert f("In the said Act, after section 4, the following shall be inserted:- Amendment of Section 5")
    assert f("The Sindh Coal Authority (Amendment) Ordinance, 1994, is hereby repealed")
    assert not f("Short title and commencement")
    assert not f("The following persons shall be the first Trustees")   # doc 4347 s.9: not the amending formula
    assert not f("Repeal")


def test_amending_section_keeps_its_whole_text_and_no_heading():
    seg = S.segment(_blocks(
        "1. Short title. This Act may be called the Provincial Motor Vehicles (Amendment) Act, 2022.",
        "2. In the Provincial Motor Vehicles Ordinance, 1965, for section 23-A, the following shall be "
        "substituted:- “23-A. Penalty in default of registration. If any owner of motor vehicle fails to "
        "register it, he shall be liable to a penalty.”.",
        "3. Repeal. The Provincial Motor Vehicles (Amendment) Ordinance, 2021, is hereby repealed."))
    s = _sections(seg)
    assert s["1"][0] == "Short title"                                    # ordinary guess unchanged
    assert s["2"][0] is None
    assert s["2"][1].startswith("In the Provincial Motor Vehicles Ordinance, 1965, for section 23-A, the following "
                                "shall be substituted:- “23-A. Penalty in default of registration.")
    assert s["3"][0] == "Repeal"                                         # a real heading before the repeal stays


def test_repealing_sentence_is_not_a_heading():
    seg = S.segment(_blocks(
        "1. Short title. This Ordinance may be called the Sindh Coal Authority (Repeal) Ordinance, 1995.",
        "2. The Sindh Coal Authority (Amendment) Ordinance, 1994, is hereby repealed. Repeal."))
    s = _sections(seg)
    assert s["2"][0] is None
    assert s["2"][1].startswith("The Sindh Coal Authority (Amendment) Ordinance, 1994, is hereby repealed.")
