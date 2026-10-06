from tools.blocked_review_progress import case_state


QUESTION = {"case_id": "s7-527-test", "response_template": {
    "case_id": "s7-527-test", "verdict": None},
    "workflow_lane": "repair_from_existing_source_review"}


def test_progress_does_not_conflate_template_with_accepted_review():
    state, _ = case_state(QUESTION, QUESTION["response_template"], set(), {}, False)
    assert state == "correction_required"


def test_progress_distinguishes_valid_answer_from_release():
    answer = {"case_id": "s7-527-test", "verdict": "candidate_belongs_under_other_parent"}
    assert case_state(QUESTION, answer, {QUESTION["case_id"]}, {}, False)[0] == (
        "response_validated")
    assert case_state(QUESTION, answer, {QUESTION["case_id"]}, {}, True)[0] == (
        "released")


def test_old_exact_blocker_can_clear_while_instrument_stays_blocked():
    answer = {"case_id": "s7-527-test", "verdict": "candidate_belongs_under_other_parent"}
    assert case_state(QUESTION, answer, {QUESTION["case_id"]}, {}, False,
                      blocker_current=False)[0] == "correction_verified"
