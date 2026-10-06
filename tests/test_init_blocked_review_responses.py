import json

from tools.init_blocked_review_responses import initialize


def test_templates_mirror_questions_and_preserve_answer(tmp_path):
    (tmp_path / "questions" / "doc-118").mkdir(parents=True)
    (tmp_path / "manifest.json").write_text(json.dumps({
        "status": "ready", "counts": {"questions": 1}}), encoding="utf-8")
    case = {"case_id": "s7-118-real", "document_id": 118,
            "response_template": {"case_id": "s7-118-real", "verdict": None}}
    (tmp_path / "questions" / "doc-118" / "s7-118-real.json").write_text(
        json.dumps(case), encoding="utf-8")
    assert initialize(tmp_path) == {
        "questions": 1, "created": 1, "preserved_existing": 0}
    response = tmp_path / "responses" / "doc-118" / "s7-118-real.json"
    assert json.loads(response.read_text(encoding="utf-8")) == case["response_template"]
    response.write_text('{"case_id":"s7-118-real","verdict":"reparent"}\n', encoding="utf-8")
    assert initialize(tmp_path)["preserved_existing"] == 1
    assert json.loads(response.read_text(encoding="utf-8"))["verdict"] == "reparent"
