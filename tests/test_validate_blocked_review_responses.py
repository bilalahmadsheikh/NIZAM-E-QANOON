import hashlib
import json
import sys

from tools.validate_blocked_review_responses import main, validate_one, validate_schema


def test_closed_response_schema_rejects_unknown_fields():
    schema = {"required": ["case_id"], "properties": {
        "case_id": {"type": "string", "minLength": 8}}}
    assert validate_schema({"case_id": "s7-118-test", "invented": True}, schema) == [
        "field not in response schema: invented"]


def test_limited_body_search_cannot_validate_absence(tmp_path):
    image = tmp_path / "page.png"
    image.write_bytes(b"official-page-test")
    sha = hashlib.sha256(image.read_bytes()).hexdigest()
    case = {
        "case_id": "toc-123-456",
        "defect_type": "unresolved_contents_promise",
        "allowed_verdicts": ["absent_in_official_source"],
        "images": [{"path": "page.png", "sha256": sha}],
        "how_found": {"body_search": {"coverage_limited": True}},
    }
    answer = {
        "case_id": "toc-123-456", "verdict": "absent_in_official_source",
        "observed_on_page": "The supplied page shows the contents entry only.",
        "exact_printed_text": "section 4 then section 6",
        "evidence_image_paths": ["page.png"],
        "reviewer_kind": "tool", "reviewer_id": "test-reader",
        "confidence": 0.9,
    }
    errors = validate_one(case, answer, tmp_path, {})
    assert any("limited" in error for error in errors)


def test_human_full_pdf_review_can_cover_limited_body_search(tmp_path):
    images = []
    for page in (1, 2):
        path = tmp_path / f"page-{page}.png"
        path.write_bytes(f"official-page-{page}".encode())
        images.append({"path": path.name, "page": page,
                       "role": "full_page",
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    case = {"case_id": "toc-306-1080645",
            "defect_type": "unresolved_contents_promise",
            "allowed_verdicts": ["absent_in_official_source"],
            "images": images, "source_pdf": {"page_count": 2},
            "how_found": {"body_search": {"coverage_limited": True}}}
    answer = {"case_id": case["case_id"],
              "verdict": "absent_in_official_source",
              "observed_on_page": "The complete two-page PDF ends after Section 2.",
              "exact_printed_text": "2. The Sindh Disposal of Urban Land Ordinance, 2002 is hereby repealed.",
              "evidence_image_paths": [item["path"] for item in images],
              "reviewer_kind": "human", "reviewer_id": "actual-reader",
              "confidence": 0.95}
    assert validate_one(case, answer, tmp_path, {}) == []


def test_rejects_unlisted_or_modified_images(tmp_path):
    image = tmp_path / "page.png"
    image.write_bytes(b"changed")
    case = {
        "case_id": "s7-123-456", "defect_type": "repeated_citation_label",
        "allowed_verdicts": ["candidate_noncitable"],
        "images": [{"path": "page.png", "sha256": "0" * 64}],
    }
    answer = {
        "case_id": "s7-123-456", "verdict": "candidate_noncitable",
        "observed_on_page": "The candidate is a printed marginal note.",
        "exact_printed_text": "marginal note",
        "evidence_image_paths": ["page.png"],
        "reviewer_kind": "tool", "reviewer_id": "test-reader",
        "confidence": 0.9,
    }
    assert any("SHA-256 changed" in error for error in
               validate_one(case, answer, tmp_path, {}))


def test_validator_discovers_nested_response_templates(tmp_path, monkeypatch, capsys):
    (tmp_path / "questions" / "doc-118").mkdir(parents=True)
    (tmp_path / "responses" / "doc-118").mkdir(parents=True)
    (tmp_path / "manifest.json").write_text(json.dumps({
        "status": "ready", "counts": {"questions": 1}}), encoding="utf-8")
    (tmp_path / "response-schema.json").write_text(json.dumps({
        "required": ["case_id", "verdict"], "properties": {
            "case_id": {"type": "string"},
            "verdict": {"type": ["string", "null"]}}}), encoding="utf-8")
    question = {"case_id": "s7-118-test", "document_id": 118,
                "needs_new_source_classification": True,
                "allowed_verdicts": ["candidate_belongs_under_other_parent"],
                "defect_type": "repeated_citation_label", "images": []}
    (tmp_path / "questions" / "doc-118" / "s7-118-test.json").write_text(
        json.dumps(question), encoding="utf-8")
    (tmp_path / "responses" / "doc-118" / "s7-118-test.json").write_text(
        json.dumps({"case_id": "s7-118-test", "verdict": None}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validator", "--pack", str(tmp_path), "--offline"])
    assert main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["responses_seen"] == 1
    assert "s7-118-test" in report["invalid_responses"]
