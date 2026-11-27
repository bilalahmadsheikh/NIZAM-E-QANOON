"""tools/rerank_train_pairs.py (D-171): the query a training group is built from, and what is never read."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import rerank_train_pairs as R  # noqa: E402


def test_every_citation_in_the_sentence_is_cut_out():
    text = "The applicant was convicted under section 302 PPC read with section 34 PPC and sentenced. Next."
    a, b = 0, text.index(" Next")
    spans = [(text.index("section 302"), text.index(" read")), (text.index("section 34"), text.index(" and"))]
    q = R.masked(text, spans, a, b)
    assert "302" not in q and "34" not in q and "PPC" not in q
    assert q == "The applicant was convicted under read with and sentenced."


def test_spans_outside_the_window_are_ignored_and_dangling_punctuation_closes_up():
    text = "Earlier, s.5 applies. Bail is refused under section 497 Cr.P.C., as held in PLD 2016 SC 1."
    a = text.index("Bail")
    spans = [(text.index("s.5"), text.index(" applies")), (text.index("section 497"), text.index(", as")),
             (text.index("PLD"), len(text) - 1)]
    q = R.masked(text, spans, a, len(text))
    assert q == "Bail is refused under, as held in."
    assert "s.5" not in q


def test_territory_scopes_the_slate_like_the_benchmark():
    assert R.jurisdiction("fed") == (None, ("fed",))
    assert R.jurisdiction("ict") == ("ict", ("fed",))          # ICT law is stored as federal, served by territory
    assert R.jurisdiction("punjab") == ("punjab", ("punjab", "fed"))


def test_a_quoted_headnote_is_never_a_query():
    assert R._HEADNOTE.search("Constitution of Pakistan (1973)---- -------Constitutional jurisdiction of High Court")
    assert R._HEADNOTE.search("Specific Relief Act---S. 42——Declaration")
    assert not R._HEADNOTE.search("the case calls for further inquiry - a well-settled rule")


def test_courts_that_opted_out_are_excluded_by_rule():
    assert set(R.EXCLUDED_COURTS) == {"SC", "BHC"}              # D-144 ai-train=no; D-139 robots-disallowed path


def test_the_precedent_gold_is_excluded():
    ids, keys = R.gold_exclusions()
    assert ids and keys
    assert all(len(i) == 36 for i in ids)                        # judgment uuids
