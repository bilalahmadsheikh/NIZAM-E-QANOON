"""The case-treatment grammar (D-160): the court's own words, in the citation's sentence; the misreadings the survey
of 33,047 resolved citations showed are refused."""
from __future__ import annotations

from nizam.storage.treatment import NEGATIVE, POLARITY, review_key, sentence_bounds, treatment_of


def test_the_courts_own_treatment_is_read():
    assert treatment_of("The view taken in X v. Y (PLD 2018 SC 405) is hereby overruled.") == "overruled"
    assert treatment_of("The State (PLD 2009 SC 460) was per incuriam because it failed to notice the ruling.") \
        == "per_incuriam"
    assert treatment_of("The dictum in Minhaj Ahmad Khan, 2012 SCMR 6 is not good law.") == "disapproved"
    assert treatment_of("Khawaja Muhammad Dawood (2016 SCMR 1420) is distinguishable on facts.") == "distinguished"
    assert treatment_of("We respectfully follow Ali v. State (2020 SCMR 2134).") == "followed"
    assert treatment_of("Reliance is placed upon Abdul Ghani v. State (2019 SCMR 608).") == "applied"


def test_the_misreadings_the_survey_found_are_refused():
    # an objection is overruled, not a case
    assert treatment_of("In view of X (2012 SCMR 152), the objection to this extent is overruled.") != "overruled"
    # a third case overruled it: not this judgment's treatment
    assert treatment_of("Registrar (PLD 2016 SC 961) has been overruled by Gul Taiz Khan Marwat.") is None
    assert treatment_of("this judgment was subsequently overruled in Gul Taiz Khan Marwat Vs. Returning Officer") \
        is None
    # counsel's case is not the court's view
    assert treatment_of("It has been contended that 2012 SCMR 152 & PLD 2011 SC 132 are judgments per incuriam.") \
        is None
    assert treatment_of("Learned counsel relied upon Ali v. State (2020 SCMR 2134).") is None
    # 'following' is not 'followed'
    assert treatment_of("Syed Sallahuddin (2022 SCMR 991), wherein the issue was dealt in the following manner:") \
        is None
    # 'doubt' is not read
    assert treatment_of("Following Tariq Pervez (1995 SCMR 1345), the benefit of doubt goes to the accused.") is None


def test_polarity_is_a_fixed_map_and_reviews_outlive_rebuilds():
    assert POLARITY["overruled"] == "negative" and POLARITY["followed"] == "positive"
    assert NEGATIVE == {"overruled", "per_incuriam", "disapproved"}
    k = review_key("X  is  not good law.", "SC/CA/1/2020", "disapproved")
    assert k == review_key("X is not good law.", "SC/CA/1/2020", "disapproved")     # spacing is not the evidence
    assert k != review_key("X is not good law.", "SC/CA/2/2020", "disapproved")


def test_the_sentence_is_the_one_holding_the_citation():
    t = "First point. The view in X (PLD 2018 SC 405) is hereby overruled. Next point."
    s = t.index("X (PLD")
    a, b = sentence_bounds(t, s, s + 18)
    assert t[a:b] == "The view in X (PLD 2018 SC 405) is hereby overruled."
