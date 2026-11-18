"""nizam/storage/chunking.py (D-095): chunk spans are offsets that cover a provision version's text exactly, cut at
legal-text boundaries; the context prefix carries the rule a node qualifies. Pure."""
import random
import re

import pytest

from nizam.storage.chunking import (MAX_CHARS, MIN_CHARS, Node, Span, context_prefix, spans, unit_label)


def _covers(text, sp):
    """every non-space character in exactly one span, spans ordered, gaps only whitespace"""
    pos = 0
    for s in sp:
        assert s.start >= pos and s.end > s.start
        assert text[pos:s.start].strip() == ""
        assert not text[s.start].isspace() and not text[s.end - 1].isspace()
        pos = s.end
    assert text[pos:].strip() == ""


def test_short_text_is_one_span():
    t = "Whoever commits theft shall be punished with imprisonment."
    assert spans(t) == [Span(0, len(t))]


def test_blank_text_has_no_span():
    assert spans("") == [] and spans("   ") == []


def test_long_text_cuts_at_sentence_ends_within_the_budget():
    sent = "The Government may, by notification in the official Gazette, make rules for carrying out the purposes. "
    t = (sent * 40).strip()
    sp = spans(t)
    _covers(t, sp)
    assert len(sp) > 1 and all(s.end - s.start <= MAX_CHARS for s in sp[:-1])
    assert all(t[s.end - 1] == "." for s in sp)                  # every cut after a full stop


def test_a_citation_abbreviation_is_not_a_sentence_end():
    lead = "x " * (MIN_CHARS // 2 + 10)
    t = (lead + "as provided in s. 302 of the Code and No. 5 of the Schedule; the rest " + "y " * 500).strip()
    for s in spans(t):
        assert not re.search(r"\b(?:s|No)\.$", t[s.start:s.end])


def test_falls_back_to_semicolon_then_comma_then_space():
    semi = ("(a) any person who keeps an animal in a public place; " * 30).strip()
    assert all(semi[s.end - 1] == ";" for s in spans(semi)[:-1])
    comma = ("goods, wares, merchandise, " * 80).strip()
    assert all(comma[s.end - 1] == "," for s in spans(comma)[:-1])
    words = ("abcdefg " * 400).strip()
    sp = spans(words)
    _covers(words, sp)
    assert all(words[s.end - 1] == "g" for s in sp)                # never inside a word


def test_an_unbroken_run_is_hard_cut_and_still_covered():
    t = "x" * (MAX_CHARS * 3 + 7)
    sp = spans(t)
    _covers(t, sp)
    # three full cuts; the 7-character tail joins the last piece (it fits MAX_CHARS * 1.15)
    assert [s.end - s.start for s in sp] == [MAX_CHARS, MAX_CHARS, MAX_CHARS + 7]


def test_a_tiny_tail_joins_the_previous_piece():
    t = ("A sentence of ordinary legal length that ends here. " * 23).strip() + " Tail."
    sp = spans(t)
    assert sp[-1].end - sp[-1].start >= 120


@pytest.mark.parametrize("seed", range(25))
def test_random_texts_are_always_covered_exactly(seed):
    rnd = random.Random(seed)
    words = ["section", "302", "s.", "No.", "the", "Government;", "shall,", "be", "punished.", "(a)", "Rs.", "500",
             "Provided", "that", "—", "x" * 30]
    t = " ".join(rnd.choice(words) for _ in range(rnd.randint(1, 2500)))
    _covers(t, spans(t))


def test_unit_label_reads_like_a_citation():
    chain = [Node("chapter", "XVII", "Of offences against property"), Node("section", "378", "Theft"),
             Node("subsection", "1", None), Node("clause", "a", None)]
    assert unit_label(chain) == "s. 378(1)(a)"
    assert unit_label([Node("section", "378", "Theft"), Node("explanation", "Explanation 1", None)]) == \
        "s. 378, Explanation 1"
    assert unit_label([Node("section", "10", None), Node("proviso", "Provided", None)]) == "s. 10, Proviso"
    assert unit_label([Node("schedule", "FIRST SCHEDULE", None), Node("clause", "3", None)]) == "FIRST SCHEDULE(3)"


def test_a_proviso_carries_the_rule_it_qualifies():
    chain = [Node("section", "10", "Power to make rules"), Node("proviso", "Provided", None)]
    p = context_prefix("The Example Act, 2020", None, chain,
                       qualifies="The Government may make rules for carrying out the purposes of this Act.")
    assert p.startswith("The Example Act, 2020 | s. 10, Proviso Power to make rules | qualifies: The Government")


def test_a_plain_unit_has_no_qualifier_and_the_prefix_is_bounded():
    chain = [Node("section", "378", "Theft")]
    assert "qualifies" not in context_prefix("Pakistan Penal Code", "Of offences against property", chain,
                                             qualifies="anything")
    long = context_prefix("T" * 300, None, chain)
    assert len(long) <= 240
