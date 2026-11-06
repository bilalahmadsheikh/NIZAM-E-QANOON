"""OCR verification must apply equally to Latin and Arabic-script output."""

from nizam.workers.verify_ocr import _page_read_covers, _words_per_page

import json
from contextlib import contextmanager

import pytest

from nizam.workers import verify_ocr


def test_yield_uses_recorded_ocr_words_not_english_regex_tokens():
    # 240 Urdu words over four pages are still 60 words/page even when an
    # English-only legal vocabulary would find zero tokens.
    assert _words_per_page("240", 4) == 60


def test_missing_or_zero_page_metadata_is_safe():
    assert _words_per_page(None, 4) == 0
    assert _words_per_page("not-a-number", 4) == 0
    assert _words_per_page(100, 0) == 0


def test_page_read_review_must_cover_every_page():
    # doc 02 §4's human review below the confidence threshold: one render digest per page, or it reviews nothing
    two = {"render_sha256": ["a" * 64, "b" * 64]}
    assert _page_read_covers(two, 2)
    assert not _page_read_covers(two, 3)
    assert not _page_read_covers({"render_sha256": []}, 0)
    assert not _page_read_covers({"render_sha256": ["short"]}, 1)
    assert not _page_read_covers(None, 1)
    assert not _page_read_covers({"render_sha256": "a" * 64}, 1)


def _reading(text="The Court shall make the order under this Act."):
    return [("instrument-id", 12229, "act.s_1", None, "section", "1", "Orders", 1, 1, 2342211, text)]


def _review(rows, **changes):
    detail = {"method": verify_ocr.REVIEWED_PROVISIONS_METHOD, "document_id": 8743,
              "render_sha256": ["a" * 64, "b" * 64, "c" * 64, "d" * 64],
              "reviewed_provisions_sha256": verify_ocr._provision_reading_sha256(rows)}
    return {**detail, **changes}


@pytest.mark.parametrize("changes", [
    {"document_id": 8744}, {"document_id": "8743"},
    {"render_sha256": ["a" * 64]}, {"reviewed_provisions_sha256": "0" * 64},
    {"render_sha256": ["nothex" * 10 + "xxxx"] * 4},
    {"render_sha256": ["a" * 64] * 5},
    {"method": "lead-full-page-read"},
])
def test_reviewed_rate_rejects_missing_or_mismatched_evidence(changes):
    rows = _reading()
    assert verify_ocr._reviewed_legal_rate(_review(rows, **changes), 4, 8743, rows) is None


@pytest.mark.parametrize("column,new_value", [
    (0, "another-instrument"), (1, 12230), (2, "act.s_2"),
    (3, "act.s_9"), (4, "clause"), (5, "2"), (6, "Changed heading"),
    (7, 2), (8, 2), (9, 2342212), (10, "A later, unaudited reading."),
])
def test_review_is_stale_after_any_bound_identity_tree_or_text_change(column, new_value):
    rows = _reading();detail = _review(rows)
    changed = [list(rows[0])];changed[0][column] = new_value
    assert verify_ocr._reviewed_legal_rate(detail, 4, 8743, changed) is None


def test_empty_or_low_quality_reviewed_reading_is_not_automatically_accepted():
    assert verify_ocr._reviewed_legal_rate(_review([]), 4, 8743, []) is None
    rows = _reading("")
    assert verify_ocr._reviewed_legal_rate(_review(rows), 4, 8743, rows) is None
    rows = _reading("xxyy zzzz qqqq")
    assert verify_ocr._reviewed_legal_rate(_review(rows), 4, 8743, rows) == 0


def test_current_table_vocabulary_review_preserves_threshold_and_requires_exact_tree():
    rows=_reading('CALCIUM CYANAMIDE | Revenue | 25 per cent. ad valorem | ..')
    detail=_review(rows,purpose='ocr-table-document',table_review='source_checked_article_names_and_duty_cells')
    assert verify_ocr._reviewed_legal_rate(detail,4,8743,rows)<verify_ocr.MIN_LEGAL_RATE
    assert verify_ocr._reviewed_table_allowed(detail,4,8743,rows,'E4')
    assert not verify_ocr._reviewed_table_allowed(detail,4,8743,_reading('Changed duty.'),'E4')
    assert not verify_ocr._reviewed_table_allowed(detail,5,8743,rows,'E4')
    assert not verify_ocr._reviewed_table_allowed(detail,4,8744,rows,'E4')
    assert not verify_ocr._reviewed_table_allowed({**detail,'table_review':'unchecked'},4,8743,rows,'E4')
    for lane in ['E2','E3']:
        assert not verify_ocr._reviewed_table_allowed(detail,4,8743,rows,lane)
    assert verify_ocr.MIN_LEGAL_RATE==.25


def test_legacy_table_assertion_semantics_unchanged():
    assert verify_ocr._reviewed_table_allowed({'method':'lead-full-page-read'},4,8743,[],'E4')


class _VerificationCursor:
    def __init__(self, rows, review, words, lane, table_review=None):
        self.rows, self.review, self.words, self.lane = rows, review, words, lane
        self.table_review = table_review
        self.result = [];self.verification = None

    def __enter__(self):return self
    def __exit__(self, *args):pass

    def execute(self, sql, args=()):
        if "FROM document d" in sql:
            self.result = [(8743, "source-sha", 4, 10000, .532, "en", self.words,
                            "Privy Council Appeals Act", self.lane, {"mixed_ocr":{"candidate_ids":[1]}}, "eng")]
        elif "FROM page_ocr_candidate" in sql:self.result = [(p,100,.532) for p in range(1,5)]
        elif "FROM text_block" in sql:self.result = [("xxyy zzzz qqqq",)]
        elif "detail->>'purpose'='ocr-table-document'" in sql:
            self.result = [(92,self.table_review)] if self.table_review is not None else []
        elif "SELECT id, detail FROM extraction_assertion" in sql:self.result = [(91, self.review)]
        elif "FROM extraction_assertion" in sql:self.result = []
        elif "FROM instrument i JOIN provision p" in sql:self.result = self.rows
        elif "INSERT INTO extraction_verification" in sql:
            self.verification = dict(outcome=args[2],problems=json.loads(args[3]),detail=json.loads(args[4]))
        elif "UPDATE document" in sql:pass
        else:raise AssertionError(sql)

    def fetchall(self):return self.result
    def fetchone(self):return self.result[0] if self.result else None


def _run_verification(monkeypatch, rows, review, words="400", lane="E4", table_review=None):
    cursor = _VerificationCursor(rows, review, words, lane, table_review)
    class Connection:
        def cursor(self):return cursor
        def commit(self):pass
    @contextmanager
    def connect():yield Connection()
    monkeypatch.setattr(verify_ocr,"connect",connect)
    monkeypatch.setattr(verify_ocr.sys,"argv",["verify_ocr", "--document-id", "8743"])
    code = verify_ocr.main()
    return code,cursor.verification


def test_verifier_scores_exact_reviewed_text_and_retains_raw_metric(monkeypatch):
    rows = _reading()
    code,result = _run_verification(monkeypatch,rows,_review(rows))
    assert code == 0 and result["outcome"] == "passed"
    assert result["detail"]["raw_legal_token_rate"] == 0
    assert result["detail"]["curated_legal_token_rate"] >= verify_ocr.MIN_LEGAL_RATE
    assert result["detail"]["page_read_assertion_id"] == 91
    assert result["detail"]["reviewed_provisions_sha256"] == _review(rows)["reviewed_provisions_sha256"]


@pytest.mark.parametrize('case',['exact','stale','incomplete','low-yield','E3'])
def test_current_tariff_table_exception_is_scoped_and_cannot_clear_other_failures(monkeypatch,case):
    rows=_reading('CALCIUM CYANAMIDE | Revenue | 25 per cent. ad valorem | ..')
    review=_review(rows);table=_review(rows,purpose='ocr-table-document',table_review='source_checked_article_names_and_duty_cells')
    words='20'if case=='low-yield'else'400';lane='E3'if case=='E3'else'E4'
    if case=='stale':table['reviewed_provisions_sha256']='0'*64
    if case=='incomplete':table['render_sha256']=table['render_sha256'][:1]
    code,result=_run_verification(monkeypatch,rows,review,words,lane,table)
    assert (code==0)==(case=='exact')
    assert (result['detail']['table_source_review_assertion_id']==92)==(case=='exact'or case=='low-yield')


@pytest.mark.parametrize("case", ["stale", "incomplete", "legacy", "still-garbled", "low-yield"])
def test_verifier_cannot_clear_an_unresolved_quality_failure(monkeypatch, case):
    rows = _reading();review = _review(rows);words = "400"
    if case == "stale":rows = _reading("This text changed after review.")
    if case == "incomplete":review["render_sha256"] = ["a" * 64]
    if case == "legacy":review["method"] = "lead-full-page-read"
    if case == "still-garbled":rows = _reading("xxyy zzzz qqqq");review = _review(rows)
    if case == "low-yield":words = "20"
    code,result = _run_verification(monkeypatch,rows,review,words)
    assert code == 1 and result["outcome"] == "review" and result["problems"]


@pytest.mark.parametrize("lane", ["E2", "E3"])
def test_curated_whole_document_score_is_not_used_for_other_ocr_lanes(monkeypatch, lane):
    rows = _reading()
    code,result = _run_verification(monkeypatch,rows,_review(rows),lane=lane)
    assert code == 1 and result["outcome"] == "review"
    assert result["detail"]["curated_legal_token_rate"] is None
    assert result["detail"]["raw_legal_token_rate"] == 0
