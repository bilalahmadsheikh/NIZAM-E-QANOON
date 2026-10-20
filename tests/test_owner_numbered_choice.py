"""Group 36 (18 Oct 2026): the owner-cited label choice 'owner-numbered' (doc 4588, owner decision-review-2026-10-18-
4588.json q1; agent K6). Rules 29 and 46 of the Agricultural Produce Markets rules print their headings under pasted
slips; the existing source_owner_cited_labels opener (printed_label null) opens each at its first visible words under the
owner's number. The choice is admitted like 'cite-115A'; no parse logic changes."""
import json

import pytest

from nizam.workers.segment import OWNER_CITED_LABEL_CHOICES, owner_cited_label_shape_ok
from tools.record_curation_patch import owner_cited_decision_check

RULE_29 = {"kind": "section", "printed_label": None, "cited_label": "29", "source_block_id": 101,
           "source_prefix": "1. In rule 29, for the agricultural produce",
           "owner_decision": {"export": "X", "document_id": 4588, "question_id": "q1"}}


def _export(tmp_path, choice):
    path = tmp_path / "decision-review-4588.json"
    path.write_text(json.dumps({"answers": [{"document_id": 4588, "question_id": "q1", "choice": choice}]}),
                    encoding="utf-8")
    return str(path)


def test_owner_numbered_is_an_owner_cited_label_choice():
    assert "owner-numbered" in OWNER_CITED_LABEL_CHOICES


def test_an_opener_citing_owner_numbered_is_accepted(tmp_path):
    entry = dict(RULE_29, owner_decision=dict(RULE_29["owner_decision"], export=_export(tmp_path, "owner-numbered")))
    assert owner_cited_label_shape_ok(entry)
    owner_cited_decision_check([entry], 4588)   # does not raise


def test_an_unlisted_choice_is_still_refused(tmp_path):
    entry = dict(RULE_29, owner_decision=dict(RULE_29["owner_decision"], export=_export(tmp_path, "owner-numbering")))
    with pytest.raises(ValueError, match="q1 choice 'owner-numbering', not one of"):
        owner_cited_decision_check([entry], 4588)
