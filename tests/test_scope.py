"""D-102: the gate's scope vetoes. Each must fire on the question it exists for and stay silent on the ordinary
citizen question that merely mentions a foreign place, a court or the future. Fixtures are dev-split golden questions
and invented ones; test-split questions are never used here (they are scored once)."""
from __future__ import annotations

import glob
import json
from datetime import date
from pathlib import Path

import pytest

from nizam.retrieval import scope

AS_OF = date(2026, 11, 16)
TODAY = date(2026, 11, 20)
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("q,kind", [
    ("What does the law in Kabul, Afghanistan say about evicting a tenant?", "place"),            # S1-X01 (dev)
    ("What is the punishment for theft under the Indian Penal Code in India today?", "place"),    # S1-X03 (dev)
    ("What documents do I need for a UAE tourist visa?", "place"),                                # S1-X05 (dev)
    ("What is the punishment for theft in the UAE?", "place"),                                    # S2-X02 (dev)
    ("What are the labour laws in Saudi Arabia for Pakistani workers there?", "place"),          # S4-X04 (dev)
    ("What is the Indian law on dowry?", "place"),
    ("What are the divorce laws in the UK?", "place"),
    ("What did the Supreme Court decide in the Panama Papers case?", "source"),                   # S1-X02 (dev)
    ("What did the Supreme Court hold in the Zulfikar Ali Bhutto presidential reference?", "source"),  # S2-X01
    ("What did the Lahore High Court decide in the challenge to the Punjab Defamation Act, 2024?", "source"),
    ("Give me the case law on pre-emption", "source"),
    ("Summarise PLD 2016 SC 1", "source"),
    ("What will the income tax slabs for salaried people be in tax year 2029?", "time"),         # S2-X05 (dev)
    ("How much will the minimum wage rise next year?", "time"),
])
def test_the_veto_fires(q, kind):
    f = scope.veto(q, AS_OF, today=TODAY)
    assert f is not None and f.kind == kind, (q, f)
    assert f.code == {"place": "CORPUS_GAP", "source": "CORPUS_GAP", "time": "NO_VALID_VERSION"}[kind]
    assert f.matched and f.matched in q or f.matched.lower() in q.lower()


@pytest.mark.parametrize("q", [
    "My husband lives in Saudi Arabia and does not send maintenance. What can I do?",
    "My marriage took place in the UK. Is it valid in Pakistan?",
    "What does Pakistani law say about a marriage registered in the UK?",
    "I am Pakistani and want to take British citizenship. Will I lose my Pakistani citizenship?",
    "My Saudi employer has not paid me. Can I complain in Lahore?",
    "How do I get the family court to order maintenance for my children?",
    "Can I appeal against the judgment of the civil court?",
    "The court decided against me in my rent case. Can I appeal?",
    "My rent is due next month. Will my landlord be able to evict me if I pay late?",
    "What is the punishment for theft in Lahore?",
    "Can I send money to my brother in Dubai?",
    "s.302 PPC",
])
def test_the_veto_stays_silent(q):
    assert scope.veto(q, AS_OF, today=TODAY) is None, q


def test_a_resolved_citation_or_a_pakistani_place_lifts_the_place_veto():
    q = "What are the rights of a tenant in Dubai?"
    assert scope.place_veto(q) is not None
    assert scope.place_veto(q, cited=True) is None
    assert scope.place_veto(q + " I live in Karachi.") is None


def test_an_as_of_after_today_is_no_valid_version():
    f = scope.time_veto("Can my landlord evict me?", date(2027, 1, 1), today=TODAY)
    assert f.code == "NO_VALID_VERSION" and f.matched == "2027-01-01"
    assert scope.time_veto("Can my landlord evict me?", TODAY, today=TODAY) is None


def test_a_past_year_is_not_the_future():
    assert scope.time_veto("What will happen to a lease I signed in 2019?", AS_OF, today=TODAY) is None


def test_no_dev_answerable_golden_question_is_vetoed():
    dev = set(json.loads((ROOT / "evals/golden/split-v1.json").read_text(encoding="utf-8"))["dev"])
    n = 0
    for fn in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(fn, encoding="utf-8"):
            d = json.loads(line)
            if d["caseId"] in dev and d["expectedOutcome"] in ("answer", "conditional"):
                n += 1
                assert scope.veto(d["question"]["text"], date.fromisoformat(d["scope"]["asOf"]),
                                  today=TODAY) is None, d["caseId"]
    assert n > 0
