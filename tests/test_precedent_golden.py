"""The precedent stratum of the golden set (D-133): its authority reading, its split and its records' shape.

Pure: reads the built JSONL and the split file, never the database.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals/golden"))
GOLDEN = ROOT / "evals/golden"

from precedent_common import expected_status  # noqa: E402


def _cases():
    out = []
    for p in sorted(GOLDEN.glob("golden-pk-v1-precedent*.draft.jsonl")):
        out += [json.loads(line) for line in p.open(encoding="utf-8") if line.strip()]
    return out


def test_the_author_reads_art_189_and_art_201_and_nothing_else():
    assert expected_status("SC", "sindh") == "binding"            # Art. 189: every court
    assert expected_status("LHC", "punjab") == "binding"          # Art. 201: its own subordinate courts
    assert expected_status("LHC", "kp") == "not_binding"          # another province's High Court persuades only
    assert expected_status("PHC", "punjab") == "not_binding"
    assert expected_status("PHC", "kp") == "binding"
    assert expected_status("LHC", None) is None                   # no forum, no authority question


def test_every_answer_case_names_judgment_paragraphs_from_records():
    cases = _cases()
    assert len(cases) >= 50
    for c in cases:
        gold = c["precedentGold"]
        if c["expectedOutcome"] == "abstain":
            assert not gold["necessaryJudgments"] and c["abstention"]["code"] in ("court_not_held", "before_coverage")
            continue
        assert gold["necessaryJudgments"] and c["textChecks"], c["caseId"]
        for u in gold["necessaryJudgments"]:
            assert u["textSha256"] and u["court"] in ("SC", "LHC", "PHC"), c["caseId"]
            assert u["existsAtAsOf"], c["caseId"]                 # no gold judgment postdates the question
            assert (u["paragraph"] is None) == (u["paragraphId"] is None)
            assert "chunk" not in json.dumps(u)                    # INV-4: labels end at paragraphs
        for u in gold["hardNegatives"]:
            assert not u["existsAtAsOf"], c["caseId"]              # a trap is a judgment that did not yet exist


def test_the_split_keeps_each_family_whole_and_covers_every_case():
    split = json.loads((GOLDEN / "split-precedent-v1.json").read_text(encoding="utf-8"))
    dev, test = set(split["dev"]), set(split["test"])
    assert not dev & test
    fams = {c["familyId"] for c in _cases()}
    assert fams == dev | test
    # unanswerable families fall on both sides, so abstention is measured on test too
    un = {c["familyId"] for c in _cases() if c["expectedOutcome"] == "abstain"}
    assert un & dev and un & test
