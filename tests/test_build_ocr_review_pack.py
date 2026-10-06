"""Pure checks for the read-only human OCR review-pack builder."""
import json

import pytest

from tools.build_ocr_review_pack import prepare_page, result_pages
from tools.validate_ocr_review_export import validate


def test_result_pages_sort_and_refuse_duplicate(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"3800": [
        {"page": 2, "blocks": []}, {"page": 1, "blocks": []},
    ]}), encoding="utf-8")
    assert [page["page"] for page in result_pages(path, 3800)] == [1, 2]
    path.write_text(json.dumps({"3800": [
        {"page": 1, "blocks": []}, {"page": 1, "blocks": []},
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="repeated page"):
        result_pages(path, 3800)


def test_prepare_page_preserves_block_order_and_text_hash():
    result = {"page": 3, "blocks": [
        {"reading_order": 2, "html": "<p>Second</p>", "bbox": [1, 2, 3, 4]},
        {"reading_order": 1, "html": "<p>First</p>", "bbox": [0, 1, 2, 3]},
        {"reading_order": 3, "html": "", "bbox": [0, 0, 1, 1]},
    ]}
    page = prepare_page(result, "Stored text", None)
    assert page["candidate_text"] == "First\n\nSecond"
    assert page["stored_text"] == "Stored text"
    assert page["image"] == "images/page-003.png"
    assert len(page["blocks"]) == 2
    assert len(page["candidate_text_sha256"]) == 64
    assert page["candidate_id"] is None


def test_export_validator_rejects_stale_or_unchecked_decision(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "page-001.png").write_bytes(b"image")
    manifest = {
        "schema": "nizam.ocr_page_review.v1", "document_id": 3800,
        "source_sha256": "s" * 64, "result_sha256": "r" * 64,
        "candidate_engine": "surya", "source_page_count": 1,
        "candidate_page_count": 1,
        "pages": [{"page_no": 1, "candidate_text_sha256": "t" * 64,
                   "candidate_id": None, "image": "images/page-001.png"}],
    }
    export = {key: manifest[key] for key in (
        "schema", "document_id", "source_sha256", "result_sha256",
        "candidate_engine", "source_page_count", "candidate_page_count")}
    export.update({"reviewer_name": "Reviewer", "reviewed_unresolved": [],
                   "undecided_candidate_pages": [], "decisions": [{
                       "document_id": 3800, "page_no": 1,
                       "candidate_text_sha256": "t" * 64,
                       "candidate_id": None, "reviewed_source_image": True,
                       "source_image": "images/page-001.png",
                       "decision": "accepted", "reason": "",
                   }]})
    assert validate(export, manifest, tmp_path) == []
    export["decisions"][0]["reviewed_source_image"] = False
    assert any("checkbox" in error for error in validate(export, manifest, tmp_path))
    export["decisions"][0]["reviewed_source_image"] = True
    export["result_sha256"] = "x" * 64
    assert any("result_sha256" in error for error in validate(export, manifest, tmp_path))
