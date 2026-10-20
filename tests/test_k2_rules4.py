"""Agent K2's rule `reviewed_bound_note` (doc 4397; owner q1 'punjab-text', lead's delegated q2 'latest-punjab-text';
docs/SEGMENTATION-PROFILES.md). Data-gated.

Run against the live module once ported (copy to tests/); before the port, against the prototype:
    K2_RULE=<scratchpad>/agK2-rule4.py ./.venv/bin/python -m pytest <this file>
"""
import importlib.util
import os
import sys

import pytest

if os.environ.get("K2_RULE"):
    _spec = importlib.util.spec_from_file_location("k2_rule4_t", os.environ["K2_RULE"])
    _R = importlib.util.module_from_spec(_spec)
    sys.modules["k2_rule4_t"] = _R
    _spec.loader.exec_module(_R)
    W = _R.load_worker("k2_test_worker4")
    S = sys.modules["agk2_segment4"]
else:
    from nizam.corpus import segment as S
    import nizam.workers.segment as W


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


def blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


RULES = blocks(
    "1. Short title.- These rules may be called the Test Rules.",
    "2. Fees.- (1) The fee shall be five rupees.\n(2) The fee shall be paid in advance.\n"
    "SINDH AMENDMENT: In sub-rule (1) for the words “five rupees” the words “ten rupees” shall be substituted.",
    "BALUCHISTAN AMENDMENT: In sub-rule (2) the word “advance” shall be omitted.",
    "3. Appeals.- An appeal shall lie to the Authority.")
NOTE = {"source_block_id": 101, "source_prefix": "SINDH AMENDMENT: In sub-rule (1)", "end_block_id": 102,
        "end_prefix": None, "owner_kind": "section", "owner_label": "2"}


def node(seg, label):
    hits = [n for n in seg.flatten() if n.kind == "section" and n.label == label]
    assert len(hits) == 1
    return hits[0]


def test_bound_note_leaves_the_text_and_is_kept_on_its_rule():
    seg = S.segment(RULES, structural_overrides={"source_bound_notes": [NOTE]})
    r2 = node(seg, "2")
    whole = " ".join(n.text for n in seg.flatten())
    assert "SINDH AMENDMENT" not in whole and "BALUCHISTAN AMENDMENT" not in whole
    assert r2.amendment_note.startswith("SINDH AMENDMENT: In sub-rule (1)")
    assert "BALUCHISTAN AMENDMENT" in r2.amendment_note
    role, owner = seg.block_roles[102]
    assert role == "footnote" and owner is r2          # the wholly consumed block is a note bound to rule 2
    assert [c.label for c in r2.children] == ["1", "2"]
    off = S.segment(RULES)
    assert "SINDH AMENDMENT" in " ".join(n.text for n in off.flatten())


def test_text_use_and_owner_path():
    seg = S.segment(RULES, structural_overrides={"source_bound_notes": [dict(NOTE, use="text", owner_label="2/2")]})
    r2 = node(seg, "2")
    sub2 = [c for c in r2.children if c.label == "2"][0]
    assert "SINDH AMENDMENT" in sub2.text and not r2.amendment_note


def test_bound_note_fails_closed():
    for bad in (dict(NOTE, owner_kind="clause"), dict(NOTE, source_prefix="SINDH"), dict(NOTE, use="other"),
                {k: v for k, v in NOTE.items() if k != "end_prefix"}):
        with pytest.raises(ValueError, match="malformed"):
            S.segment(RULES, structural_overrides={"source_bound_notes": [bad]})
    with pytest.raises(ValueError, match="prefix not once"):
        S.segment(RULES, structural_overrides={"source_bound_notes": [dict(NOTE, source_prefix="NO SUCH WORDS HERE")]})
    with pytest.raises(ValueError, match="0 provision"):
        S.segment(RULES, structural_overrides={"source_bound_notes": [dict(NOTE, owner_label="9")]})
    with pytest.raises(ValueError, match="ends before it starts"):
        S.segment(RULES, structural_overrides={"source_bound_notes": [
            dict(NOTE, end_block_id=101, end_prefix="2. Fees.- (1)")]})


def test_worker_unites_bound_notes_in_print_order():
    other = dict(NOTE, source_block_id=102, source_prefix="BALUCHISTAN AMENDMENT")
    merged = W.reviewed_structural_overrides([], [_patch(source_bound_notes=[NOTE]),
                                                  _patch(source_bound_notes=[other, NOTE])])
    assert merged["source_bound_notes"] == [NOTE, other]
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        W.reviewed_structural_overrides([], [_patch(source_bound_notes=[dict(NOTE, extra=1)])])
