"""The override keys of profile rules `unlabelled_schedule_opener`,
`quoted_table_row_text` (doc 691) and `printed_heading_override` (docs 1003,
999) through the worker's merge, the recorder's key check and the
multi-instrument dry run (docs/SEGMENTATION-PROFILES.md)."""
from __future__ import annotations

import json

import pytest

from nizam.workers.segment import (printed_heading_shape_ok, quoted_table_row_blocks_shape_ok,
                                   reviewed_structural_overrides,
                                   unlabelled_schedule_opener_shape_ok)
from tools import materialize_multi_instrument as materializer
from tools.record_curation_patch import READING_KEYS, STRUCTURAL_KEYS, reading_key_problem

DECISION = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-06-c.json",
            "document_id": 691, "question_id": "q2"}
OPENER = {"source_block_id": 29856, "label": "SCHEDULE", "source_text": "Name of the Department ...",
          "owner_decision": DECISION}
HEADING = {"label": "7", "source_block_id": 47280, "use": "heading",
           "heading": "Punishment of prosecution of Revenue officers no bar to civil remedies.",
           "owner_decision": dict(DECISION, document_id=1003)}


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


def test_shapes():
    assert unlabelled_schedule_opener_shape_ok(OPENER)
    for bad in ({k: v for k, v in OPENER.items() if k != "owner_decision"},
                dict(OPENER, source_block_id="29856"), dict(OPENER, source_text=" "),
                dict(OPENER, owner_decision={"export": "x.json", "document_id": 691}),
                dict(OPENER, extra=1)):
        assert not unlabelled_schedule_opener_shape_ok(bad), bad
    assert printed_heading_shape_ok(HEADING)
    assert printed_heading_shape_ok(dict(HEADING, use="marginal_note"))
    for bad in (dict(HEADING, use="title"), dict(HEADING, heading=""), dict(HEADING, source_block_id=0),
                {k: v for k, v in HEADING.items() if k != "owner_decision"}):
        assert not printed_heading_shape_ok(bad), bad
    assert quoted_table_row_blocks_shape_ok([29651, 29659])
    for bad in ([], [29651, 29651], ["29651"], [0], 29651):
        assert not quoted_table_row_blocks_shape_ok(bad), bad


def test_worker_unites_page_scoped_lists_and_refuses_disagreement():
    merged = reviewed_structural_overrides([], [
        _patch(source_quoted_table_row_blocks=[30, 10]), _patch(source_quoted_table_row_blocks=[20]),
        _patch(source_unlabelled_schedule_openers=[OPENER]), _patch(source_unlabelled_schedule_openers=[OPENER]),
        _patch(source_printed_headings=[HEADING]),
        _patch(source_printed_headings=[dict(HEADING, label="12", use="marginal_note")])])
    assert merged["source_quoted_table_row_blocks"] == [10, 20, 30]
    assert merged["source_unlabelled_schedule_openers"] == [OPENER]
    assert [h["label"] for h in merged["source_printed_headings"]] == ["7", "12"]
    with pytest.raises(ValueError, match="conflicting reviewed unlabelled schedule opener"):
        reviewed_structural_overrides([], [_patch(source_unlabelled_schedule_openers=[OPENER]),
                                           _patch(source_unlabelled_schedule_openers=[
                                               dict(OPENER, source_text="other")])])
    with pytest.raises(ValueError, match="conflicting reviewed printed heading"):
        reviewed_structural_overrides([], [_patch(source_printed_headings=[HEADING]),
                                           _patch(source_printed_headings=[dict(HEADING, heading="x y")])])
    for bad in (_patch(source_quoted_table_row_blocks=[]),
                _patch(source_unlabelled_schedule_openers=[dict(OPENER, owner_decision=None)]),
                _patch(source_printed_headings=[dict(HEADING, use="title")])):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            reviewed_structural_overrides([], [bad])


def test_recorder_refuses_unknown_keys_rather_than_dropping_them():
    reading = {"document_id": 691, "page_no": 9, "match_text": "Name of the Department", "before_text": "a",
               "after_text": "a", "observed": "p9 prints the column heads", "render": "r.png",
               "render_sha256": "0" * 64, "source_unlabelled_schedule_openers": [OPENER]}
    assert reading_key_problem(reading) is None
    assert reading_key_problem(dict(reading, source_quoted_table_row_blocks=[1],
                                    source_printed_headings=[HEADING])) is None
    assert "unknown reading key(s) ['source_unlabeled_schedule_openers']" in reading_key_problem(
        dict(reading, source_unlabeled_schedule_openers=[OPENER]))
    # a harness copy may only repeat the reading's own structural keys
    copy = {"structural_overrides": {"source_unlabelled_schedule_openers": [OPENER]}}
    assert reading_key_problem(dict(reading, evidence=copy)) is None
    assert reading_key_problem(dict(reading, evidence={"structural_overrides": {
        "source_apparatus_blocks": [5]}})) is not None
    assert reading_key_problem(dict(reading, evidence=[1])) is not None
    # the recorder, the worker and the dry run know the same structural keys
    assert STRUCTURAL_KEYS <= READING_KEYS
    assert set(materializer.STRUCTURAL_PATCH_KEYS) == STRUCTURAL_KEYS


SUFFIX = {"kind": "section", "label": "2", "source_block_ids": [47146, 47148],
          "owner_decision": dict(DECISION, document_id=999, question_id="q1")}


def test_order_suffix_key_shape_merge_and_recorder():
    from nizam.workers.segment import order_suffix_label_shape_ok
    assert order_suffix_label_shape_ok(SUFFIX)
    # agent K4 rule `order_suffix_one_block_section` (group 20, doc 3696 E4): a SECTION group may name one block once
    # per print, as a clause group may; the segmenter honours it only under that profile rule (fail-closed elsewhere)
    assert order_suffix_label_shape_ok(dict(SUFFIX, source_block_ids=[47146, 47146]))
    for bad in (dict(SUFFIX, kind="proviso"), dict(SUFFIX, source_block_ids=[47146]),
                dict(SUFFIX, source_block_ids=[47146, 47146, 47148]), dict(SUFFIX, label=""),
                {k: v for k, v in SUFFIX.items() if k != "owner_decision"}):
        assert not order_suffix_label_shape_ok(bad), bad
    merged = reviewed_structural_overrides([], [_patch(source_order_suffix_labels=[SUFFIX]),
                                               _patch(source_order_suffix_labels=[SUFFIX])])
    assert merged["source_order_suffix_labels"] == [SUFFIX]
    with pytest.raises(ValueError, match="conflicting reviewed order suffix"):
        reviewed_structural_overrides([], [_patch(source_order_suffix_labels=[SUFFIX]),
                                           _patch(source_order_suffix_labels=[
                                               dict(SUFFIX, source_block_ids=[47146, 47150])])])
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides([], [_patch(source_order_suffix_labels=[dict(SUFFIX, kind="proviso")])])
    # sub-sections (doc 1034 s.5's two '(2)'): admitted, and two sections' duplicate (2)s coexist --
    # the merge keys on the first print, the recorder on the blocks named
    sub = dict(SUFFIX, kind="subsection", source_block_ids=[47146, 47148])
    other = dict(sub, source_block_ids=[47160, 47162])
    assert order_suffix_label_shape_ok(sub)
    merged = reviewed_structural_overrides([], [_patch(source_order_suffix_labels=[sub]),
                                               _patch(source_order_suffix_labels=[other, sub])])
    assert merged["source_order_suffix_labels"] == [sub, other]
    from tools.record_curation_patch import order_suffix_groups_ok
    assert order_suffix_groups_ok([sub, other]) and order_suffix_groups_ok([SUFFIX])
    assert not order_suffix_groups_ok([sub, dict(other, source_block_ids=[47148, 47162])])  # a block in two groups
    assert not order_suffix_groups_ok([]) and not order_suffix_groups_ok([dict(sub, kind="proviso")])
    with pytest.raises(ValueError, match="conflicting reviewed order suffix"):
        reviewed_structural_overrides([], [_patch(source_order_suffix_labels=[sub]),
                                           _patch(source_order_suffix_labels=[
                                               dict(sub, source_block_ids=[47146, 47150])])])
    assert "source_order_suffix_labels" in STRUCTURAL_KEYS
    assert reading_key_problem({"document_id": 999, "page_no": 2, "match_text": "m", "before_text": "b",
                                "after_text": "b", "observed": "x", "source_order_suffix_labels": [SUFFIX]}) is None


def test_dry_run_shapes_new_keys_and_checks_the_cited_answer(tmp_path):
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [
        {"document_id": 691, "question_id": "q2", "choice": "rows-by-serial"}]}), encoding="utf-8")
    cited = dict(OPENER, owner_decision=dict(DECISION, export=str(export)))
    readings = [{"document_id": 691, "page_no": 9, "match_text": "m", "before_text": "b", "after_text": "b",
                 "source_unlabelled_schedule_openers": [cited], "source_quoted_table_row_blocks": [5]}]
    shaped = materializer.unrecorded_readings(readings, [], 691)
    assert shaped[0]["evidence"] == {"structural_overrides": {
        "source_unlabelled_schedule_openers": [cited], "source_quoted_table_row_blocks": [5]}}
    missing = dict(readings[0], source_unlabelled_schedule_openers=[
        dict(cited, owner_decision=dict(DECISION, export=str(export), question_id="q9"))])
    with pytest.raises(ValueError, match="holds 0 answers"):
        materializer.unrecorded_readings([missing], [], 691)


NAMED_ROW = {"source_block_id": 54441, "schedule_block_id": 54428, "label": "Cane Commissioner (BS-19)",
             "source_text": "Food Department Office of Cane Commissioner Punjab Cane Commissioner (BS-19) ...",
             "owner_decision": dict(DECISION, export=DECISION["export"].replace("-06-c", "-07-e"),
                                    document_id=1121, question_id="q2")}


def test_named_schedule_row_key_shape_merge_and_recorder(tmp_path):
    # profile rule `named_schedule_row` (docs 1078, 1121; owner decisions 2026-10-07)
    from nizam.workers.segment import NAMED_SCHEDULE_ROW_CHOICES, named_schedule_row_shape_ok
    assert named_schedule_row_shape_ok(NAMED_ROW)
    for bad in ({k: v for k, v in NAMED_ROW.items() if k != "owner_decision"},
                {k: v for k, v in NAMED_ROW.items() if k != "schedule_block_id"},
                dict(NAMED_ROW, schedule_block_id=54441), dict(NAMED_ROW, source_block_id="54441"),
                dict(NAMED_ROW, label=" "), dict(NAMED_ROW, source_text=""),
                dict(NAMED_ROW, owner_decision={"export": "x.json", "document_id": 1121}),
                dict(NAMED_ROW, extra=1)):
        assert not named_schedule_row_shape_ok(bad), bad
    # the worker unites the page-scoped lists and refuses disagreement
    other = dict(NAMED_ROW, source_block_id=54446, label="Additional Cane Commissioner (BS-18)")
    merged = reviewed_structural_overrides([], [_patch(source_named_schedule_rows=[NAMED_ROW]),
                                               _patch(source_named_schedule_rows=[NAMED_ROW, other])])
    assert merged["source_named_schedule_rows"] == [NAMED_ROW, other]
    with pytest.raises(ValueError, match="conflicting reviewed named schedule row 54441"):
        reviewed_structural_overrides([], [_patch(source_named_schedule_rows=[NAMED_ROW]),
                                           _patch(source_named_schedule_rows=[dict(NAMED_ROW, label="x y")])])
    for bad in (_patch(source_named_schedule_rows=[]),
                _patch(source_named_schedule_rows=[dict(NAMED_ROW, owner_decision=None)])):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            reviewed_structural_overrides([], [bad])
    # the recorder and the dry run know the key
    assert "source_named_schedule_rows" in STRUCTURAL_KEYS
    assert "source_named_schedule_rows" in materializer.STRUCTURAL_PATCH_KEYS
    assert reading_key_problem({"document_id": 1121, "page_no": 2, "match_text": "m", "before_text": "b",
                                "after_text": "b", "observed": "x",
                                "source_named_schedule_rows": [NAMED_ROW]}) is None
    # the cited answer must exist AND be one whose choice asks for rows by post name
    assert NAMED_SCHEDULE_ROW_CHOICES == {"schedule-rows-by-post", "rows-by-post", "rows-by-group"}
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [
        {"document_id": 1121, "question_id": "q1", "choice": "release-as-is"},
        {"document_id": 1121, "question_id": "q2", "choice": "rows-by-post"}]}), encoding="utf-8")
    cited = dict(NAMED_ROW, owner_decision=dict(NAMED_ROW["owner_decision"], export=str(export)))
    reading = {"document_id": 1121, "page_no": 2, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_named_schedule_rows": [cited]}
    shaped = materializer.unrecorded_readings([reading], [], 1121)
    assert shaped[0]["evidence"] == {"structural_overrides": {"source_named_schedule_rows": [cited]}}
    wrong = dict(reading, source_named_schedule_rows=[
        dict(cited, owner_decision=dict(cited["owner_decision"], question_id="q1"))])
    with pytest.raises(ValueError, match="cites choice 'release-as-is'"):
        materializer.unrecorded_readings([wrong], [], 1121)
    from tools.record_curation_patch import named_row_decision_check
    named_row_decision_check([cited], 1121)
    with pytest.raises(ValueError, match="q1 choice 'release-as-is', not one asking for rows by post name"):
        named_row_decision_check(wrong["source_named_schedule_rows"], 1121)
    with pytest.raises(ValueError, match="holds 0 answers"):
        named_row_decision_check([dict(cited, owner_decision=dict(cited["owner_decision"], question_id="q9"))],
                                 1121)


ROW_LINK_DECISION = dict(DECISION, export=DECISION["export"].replace("-06-c", "-07-e"), document_id=1368,
                         question_id="q1")
ROW_LINKS = [{"ordinal": 0, "printed_label": "1", "unit_label": None, "owner_decision": ROW_LINK_DECISION},
             {"ordinal": 1, "printed_label": "2", "unit_label": "1", "owner_decision": ROW_LINK_DECISION}]


def test_contents_row_links_key_shape_merge_and_recorder(tmp_path):
    # profile rule `reviewed_contents_alignment` (doc 1368; owner decision 2026-10-07 q1)
    from nizam.workers.segment import contents_row_link_shape_ok, contents_row_links_ok
    assert all(contents_row_link_shape_ok(v) for v in ROW_LINKS) and contents_row_links_ok(ROW_LINKS)
    for bad in (dict(ROW_LINKS[1], ordinal=-1), dict(ROW_LINKS[1], ordinal="1"), dict(ROW_LINKS[1], unit_label=""),
                dict(ROW_LINKS[1], printed_label=" "), dict(ROW_LINKS[1], extra=1),
                {k: v for k, v in ROW_LINKS[1].items() if k != "owner_decision"}):
        assert not contents_row_link_shape_ok(bad), bad
    for bad in ([], [ROW_LINKS[1], ROW_LINKS[1]],                                         # a row twice
                [ROW_LINKS[1], dict(ROW_LINKS[1], ordinal=2, printed_label="3")]):          # a unit twice
        assert not contents_row_links_ok(bad), bad
    # one page-read list: patches must agree
    merged = reviewed_structural_overrides([], [_patch(source_contents_row_links=ROW_LINKS),
                                               _patch(source_contents_row_links=ROW_LINKS)])
    assert merged["source_contents_row_links"] == ROW_LINKS
    with pytest.raises(ValueError, match="conflicting reviewed structural override source_contents_row_links"):
        reviewed_structural_overrides([], [_patch(source_contents_row_links=ROW_LINKS),
                                           _patch(source_contents_row_links=ROW_LINKS[:1])])
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides([], [_patch(source_contents_row_links=[dict(ROW_LINKS[0], ordinal=None)])])
    assert "source_contents_row_links" in STRUCTURAL_KEYS
    assert "source_contents_row_links" in materializer.STRUCTURAL_PATCH_KEYS
    # the dry run checks the cited answer
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [{"document_id": 1368, "question_id": "q1", "choice": "body"}]}),
                      encoding="utf-8")
    cited = [dict(v, owner_decision=dict(v["owner_decision"], export=str(export))) for v in ROW_LINKS]
    reading = {"document_id": 1368, "page_no": 1, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_contents_row_links": cited}
    assert materializer.unrecorded_readings([reading], [], 1368)[0]["evidence"] == {
        "structural_overrides": {"source_contents_row_links": cited}}
    with pytest.raises(ValueError, match="holds 0 answers"):
        materializer.unrecorded_readings([dict(reading, source_contents_row_links=[
            dict(cited[0], owner_decision=dict(cited[0]["owner_decision"], question_id="q9"))])], [], 1368)


CAPTION = {"source_block_id": 52998, "caption": "GREEN BELT GROUP", "level": 2,
           "owner_decision": dict(DECISION, export=DECISION["export"].replace("-06-c", "-07-e"), document_id=1106,
                                  question_id="q3")}


def test_schedule_group_caption_key_shape_merge_and_recorder(tmp_path):
    # profile rule `schedule_group_caption` (doc 1106; owner decision 2026-10-07 q3 'rows-by-group')
    from nizam.workers.segment import (NAMED_SCHEDULE_ROW_CHOICES, SCHEDULE_GROUP_CAPTION_CHOICES,
                                       schedule_group_caption_shape_ok)
    assert schedule_group_caption_shape_ok(CAPTION) and schedule_group_caption_shape_ok(dict(CAPTION, level=1))
    for bad in (dict(CAPTION, level=3), dict(CAPTION, level="2"), dict(CAPTION, caption=" "),
                dict(CAPTION, source_block_id=0), dict(CAPTION, extra=1),
                {k: v for k, v in CAPTION.items() if k != "owner_decision"}):
        assert not schedule_group_caption_shape_ok(bad), bad
    other = dict(CAPTION, source_block_id=53013, caption="TISSUCULTURE GROUP")
    merged = reviewed_structural_overrides([], [_patch(source_schedule_group_captions=[CAPTION]),
                                               _patch(source_schedule_group_captions=[other, CAPTION])])
    assert merged["source_schedule_group_captions"] == [CAPTION, other]
    # keyed per (block, caption) since agent K4's rule R (one block may print several captions: doc 3730 p21)
    with pytest.raises(ValueError, match=r"conflicting reviewed schedule group caption \(52998, 'GREEN BELT GROUP'\)"):
        reviewed_structural_overrides([], [_patch(source_schedule_group_captions=[CAPTION]),
                                           _patch(source_schedule_group_captions=[dict(CAPTION, level=1)])])
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides([], [_patch(source_schedule_group_captions=[dict(CAPTION, level=0)])])
    assert "source_schedule_group_captions" in STRUCTURAL_KEYS
    assert "source_schedule_group_captions" in materializer.STRUCTURAL_PATCH_KEYS
    # 'rows-by-group' admits named rows (rows with no serial under a caption) and captions
    assert "rows-by-group" in NAMED_SCHEDULE_ROW_CHOICES and SCHEDULE_GROUP_CAPTION_CHOICES == {"rows-by-group", "rows-by-serial", "release-as-is", "body", "one-schedule-rows-by-group",
                                                                                    # doc 4053 q3 (delegated, 16 Oct)
                                                                                    "table-under-caption"}
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [
        {"document_id": 1106, "question_id": "q1", "choice": "split"},
        {"document_id": 1106, "question_id": "q3", "choice": "rows-by-group"}]}), encoding="utf-8")
    cited = dict(CAPTION, owner_decision=dict(CAPTION["owner_decision"], export=str(export)))
    from tools.record_curation_patch import _label_without_stop, group_caption_decision_check
    group_caption_decision_check([cited], 1106)
    wrong = dict(cited, owner_decision=dict(cited["owner_decision"], question_id="q1"))
    with pytest.raises(ValueError, match="q1 choice 'split', not one asking for rows by group caption"):
        group_caption_decision_check([wrong], 1106)
    reading = {"document_id": 1106, "page_no": 5, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_schedule_group_captions": [cited]}
    assert materializer.unrecorded_readings([reading], [], 1106)[0]["evidence"] == {
        "structural_overrides": {"source_schedule_group_captions": [cited]}}
    with pytest.raises(ValueError, match="schedule group caption cites choice 'split'"):
        materializer.unrecorded_readings([dict(reading, source_schedule_group_captions=[wrong])], [], 1106)
    # lead decision (8 Oct): a named row's label drops the cell's closing stop
    assert _label_without_stop("Superintendent") == "Superintendent"
    assert _label_without_stop("Superintendent .") == "Superintendent"
    assert _label_without_stop("Asstt. Research Officer") == "Asstt. Research Officer"


def test_plan_source_anomalies_are_validated_and_kept():
    # lead decision (8 Oct, doc 1106): the plan's printed oddities reach the manifest
    from tools.materialize_multi_instrument import load_plan
    plan = load_plan(1106)
    assert plan is not None and 1106 not in materializer.PRIMARY_DOCUMENTS
    anomalies = [a["printed"] for e in plan["expressions"] for a in e.get("source_anomalies") or []]
    assert anomalies == ["THE DIRECTORATE OF LORICULTURE", "Dated Lahore, the 17th April, 1996", "4."]


OWNER_CITED = [{"kind": "section", "printed_label": None, "cited_label": "3", "source_block_id": 63197,
                "source_prefix": "\"29 - In the absence of an agreement",
                "owner_decision": dict(DECISION, export=DECISION["export"].replace("-06-c", "-08-f"),
                                       document_id=1225, question_id="q1")},
               {"kind": "section", "printed_label": "3", "cited_label": "4", "source_block_id": 63232,
                "owner_decision": dict(DECISION, export=DECISION["export"].replace("-06-c", "-08-f"),
                                       document_id=1225, question_id="q1")}]


def test_owner_cited_label_key_shape_merge_and_recorder(tmp_path):
    # profile rule `owner_cited_label` (doc 1225; owner decision 2026-10-08 export -f q1 'contents')
    from nizam.workers.segment import OWNER_CITED_LABEL_CHOICES, owner_cited_label_shape_ok
    from tools.record_curation_patch import owner_cited_block_problem, owner_cited_decision_check
    opener, relabel = OWNER_CITED
    assert owner_cited_label_shape_ok(opener) and owner_cited_label_shape_ok(relabel)
    for bad in ({k: v for k, v in opener.items() if k != "source_prefix"},     # an opener needs its printed words
                dict(opener, source_prefix="short"), dict(relabel, source_prefix="\"29 - In the absence"),
                dict(relabel, printed_label="none"), dict(relabel, printed_label="3."),
                dict(relabel, cited_label="3"), dict(relabel, cited_label="4a"), dict(relabel, kind="clause"),
                dict(relabel, source_block_id=0), {k: v for k, v in relabel.items() if k != "owner_decision"}):
        assert not owner_cited_label_shape_ok(bad), bad
    # agent DC round 2 (doc 2756 s.47A, owner 12 Oct 'cite-47A'): a lettered cited label is an inserted section
    assert owner_cited_label_shape_ok(dict(relabel, cited_label="4A"))
    # united across patches, deduplicated by the print they name
    merged = reviewed_structural_overrides([], [_patch(source_owner_cited_labels=[opener]),
                                               _patch(source_owner_cited_labels=[relabel, opener])])
    assert merged["source_owner_cited_labels"] == [opener, relabel]
    with pytest.raises(ValueError, match="conflicting reviewed owner cited label"):
        reviewed_structural_overrides([], [_patch(source_owner_cited_labels=[relabel]),
                                           _patch(source_owner_cited_labels=[dict(relabel, cited_label="5")])])
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides([], [_patch(source_owner_cited_labels=[dict(relabel, kind="clause")])])
    assert "source_owner_cited_labels" in STRUCTURAL_KEYS
    assert "source_owner_cited_labels" in materializer.STRUCTURAL_PATCH_KEYS
    # the cited answer must be the contents numbering
    assert OWNER_CITED_LABEL_CHOICES == {"contents", "open-at-p3", "release-as-is", "rule-3", "assign", "rules",
                                         "number-1", "cite-47A", "repealed-stubs", "printed-6", "regulations", "other-copy",
                                         # doc 4149 q2 (export l; lead 15 Oct): the second '115' is cited s.115A
                                         "cite-115A",
                                         # doc 4426 q1/q2 (export j; delegated export, 15 Oct): 42A, 55A, 58A as printed
                                         "printed-42A", "same-as-42A",
                                         # doc 4498 q4/q6 (export l; 16 Oct): the body numbering stands
                                         "sequence",
                                         # doc 4588 q1 (owner 18 Oct; group 36): rules 29 and 46 under pasted slips
                                         "owner-numbered"}
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [{"document_id": 1225, "question_id": "q1", "choice": "contents"},
                                              {"document_id": 1225, "question_id": "q2", "choice": "body"}]}),
                      encoding="utf-8")
    cited = dict(relabel, owner_decision=dict(relabel["owner_decision"], export=str(export)))
    owner_cited_decision_check([cited], 1225)
    body = dict(cited, owner_decision=dict(cited["owner_decision"], question_id="q2"))
    with pytest.raises(ValueError, match=r"q2 choice 'body', not one of \['assign', 'cite-115A', 'cite-47A', 'contents', 'number-1', 'open-at-p3', 'other-copy', 'owner-numbered', 'printed-42A', 'printed-6', 'regulations', 'release-as-is', 'repealed-stubs', 'rule-3', 'rules', 'same-as-42A', 'sequence'\]"):
        owner_cited_decision_check([body], 1225)
    reading = {"document_id": 1225, "page_no": 6, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_owner_cited_labels": [cited]}
    assert materializer.unrecorded_readings([reading], [], 1225)[0]["evidence"] == {
        "structural_overrides": {"source_owner_cited_labels": [cited]}}
    with pytest.raises(ValueError, match="owner cited label cites choice 'body'"):
        materializer.unrecorded_readings([dict(reading, source_owner_cited_labels=[body])], [], 1225)
    # one page, one reading: the block is on the page and prints the number (or the opener's words) there
    page = {63232: "3. Amendment of Sindh Act X of 1985. In the said Act ...",
            63197: "(ii) for section 29 ... :- \"29 - In the absence of an agreement to the contrary ..."}
    assert owner_cited_block_problem(relabel, page) is None and owner_cited_block_problem(opener, page) is None
    assert "not on the reading's page" in owner_cited_block_problem(dict(relabel, source_block_id=1), page)
    assert "not printed" in owner_cited_block_problem(dict(relabel, printed_label="7"), page)
    assert "not printed" in owner_cited_block_problem(relabel, {63232: "23. Amendment ..."})  # not '23.
    assert "not exactly once" in owner_cited_block_problem(
        opener, {63197: opener["source_prefix"] + " ... " + opener["source_prefix"]})


SPAN_1431 = {"owner_block_id": 83372, "schedule_block_id": 83376, "source_text": "SCHEDULE", "resume_block_id": 83996,
             "owner_decision": dict(DECISION, export=DECISION["export"].replace("-06-c", "-08-f"),
                                    document_id=1431, question_id="q2")}


def test_doc1431_keys_shape_merge_and_recorder(tmp_path):
    # profile rules `substituted_schedule_items`, `not_running_header_blocks`, `level_cell_blocks`
    # (doc 1431; owner decision 2026-10-08 export -f q2 's2-text')
    from nizam.workers.segment import (SUBSTITUTED_SCHEDULE_CHOICES, block_id_list_ok, level_cell_block_shape_ok,
                                       substituted_schedule_items_shape_ok)
    from tools.record_curation_patch import doc1431_block_problem, substituted_schedule_decision_check
    assert substituted_schedule_items_shape_ok(SPAN_1431)
    for bad in (dict(SPAN_1431, resume_block_id=83376), dict(SPAN_1431, source_text=" "),
                dict(SPAN_1431, owner_block_id="83372"), {k: v for k, v in SPAN_1431.items() if k != "owner_decision"},
                dict(SPAN_1431, extra=1)):
        assert not substituted_schedule_items_shape_ok(bad), bad
    assert block_id_list_ok([83394, 83408]) and not block_id_list_ok([]) and not block_id_list_ok([1, 1])
    pair = {"cell_block_id": 83380, "row_block_id": 83381}
    assert level_cell_block_shape_ok(pair)
    for bad in (dict(pair, row_block_id=83380), dict(pair, cell_block_id=0), dict(pair, extra=1)):
        assert not level_cell_block_shape_ok(bad), bad
    merged = reviewed_structural_overrides([], [
        _patch(source_substituted_schedule_items=[SPAN_1431], source_not_running_header_blocks=[83408, 83394]),
        _patch(source_not_running_header_blocks=[83423], source_level_cell_blocks=[pair]),
        _patch(source_level_cell_blocks=[pair, {"cell_block_id": 83387, "row_block_id": 83388}])])
    assert merged["source_substituted_schedule_items"] == [SPAN_1431]
    assert merged["source_not_running_header_blocks"] == [83394, 83408, 83423]
    assert [v["cell_block_id"] for v in merged["source_level_cell_blocks"]] == [83380, 83387]
    with pytest.raises(ValueError, match="conflicting reviewed level cell 83380"):
        reviewed_structural_overrides([], [_patch(source_level_cell_blocks=[pair]),
                                           _patch(source_level_cell_blocks=[dict(pair, row_block_id=83382)])])
    with pytest.raises(ValueError, match="conflicting reviewed substituted schedule 83376"):
        reviewed_structural_overrides([], [_patch(source_substituted_schedule_items=[SPAN_1431]),
                                           _patch(source_substituted_schedule_items=[dict(SPAN_1431,
                                                                                          resume_block_id=83997)])])
    for bad in (_patch(source_not_running_header_blocks=[]), _patch(source_level_cell_blocks=[{"cell_block_id": 1}]),
                _patch(source_substituted_schedule_items=[dict(SPAN_1431, owner_decision=None)])):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            reviewed_structural_overrides([], [bad])
    for key in ("source_substituted_schedule_items", "source_not_running_header_blocks", "source_level_cell_blocks"):
        assert key in STRUCTURAL_KEYS and key in materializer.STRUCTURAL_PATCH_KEYS
    # the span's answer must be 's2-text'
    assert SUBSTITUTED_SCHEDULE_CHOICES == {"s2-text"}
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [{"document_id": 1431, "question_id": "q1", "choice": "printed"},
                                              {"document_id": 1431, "question_id": "q2", "choice": "s2-text"}]}),
                      encoding="utf-8")
    cited = dict(SPAN_1431, owner_decision=dict(SPAN_1431["owner_decision"], export=str(export)))
    substituted_schedule_decision_check([cited], 1431)
    wrong = dict(cited, owner_decision=dict(cited["owner_decision"], question_id="q1"))
    with pytest.raises(ValueError, match="q1 choice 'printed', not 's2-text'"):
        substituted_schedule_decision_check([wrong], 1431)
    reading = {"document_id": 1431, "page_no": 3, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_substituted_schedule_items": [cited]}
    assert materializer.unrecorded_readings([reading], [], 1431)[0]["evidence"] == {
        "structural_overrides": {"source_substituted_schedule_items": [cited]}}
    with pytest.raises(ValueError, match="substituted schedule cites choice 'printed'"):
        materializer.unrecorded_readings([dict(reading, source_substituted_schedule_items=[wrong])], [], 1431)
    # blocks: N and O on the reading's page; M's schedule block there, owner/resume in the document in order
    position = {83372: 10, 83376: 14, 83380: 18, 83381: 19, 83394: 30, 83996: 600}
    page = {83376: {"text": "SCHEDULE \n"}, 83380: {"text": "Forty paisa."}, 83381: {"text": "1. ACK"},
            83394: {"text": "Exemptions"}}
    ok = doc1431_block_problem([SPAN_1431], [83394], [pair], position, page, 83376, "SCHEDULE \n")
    assert ok is None
    assert "not on the reading's page" in doc1431_block_problem(None, [83408], None, position, page, 83376, "x")
    assert "not on the reading's page" in doc1431_block_problem(
        None, None, [{"cell_block_id": 83380, "row_block_id": 83500}], position, page, 83376, "x")
    assert "source_text" in doc1431_block_problem([dict(SPAN_1431, source_text="SCHEDULE I")], None, None,
                                                  position, page, 83376, "SCHEDULE \n")
    assert "outside the document" in doc1431_block_problem([dict(SPAN_1431, resume_block_id=99999)], None, None,
                                                           position, page, 83376, "SCHEDULE \n")
    assert "reading order" in doc1431_block_problem([dict(SPAN_1431, owner_block_id=83394)], None, None,
                                                    position, page, 83376, "SCHEDULE \n")


def test_recorder_refuses_a_repeated_locator_in_one_file():
    # doc 1431 p29: two identity readings shared a locator; the table holds one patch per locator, so the
    # second failed at --apply after the dry run had passed
    from tools.record_curation_patch import repeated_locators
    a = {"document_id": 1431, "page_no": 29, "match_text": "(i) when", "before_text": "(i) when"}
    assert repeated_locators([a, dict(a, page_no=30), dict(a, before_text="(i)")]) == set()
    assert repeated_locators([a, dict(a, page_no=30), dict(a, source_level_cell_blocks=[])]) == {2}


def test_doc1457_plumbing_continuation_clause_suffix_and_choices(tmp_path):
    # doc 1457 (owner decisions 8 Oct: q3 'open-at-p3', q4 'keep-both')
    from nizam.workers.segment import (ORDER_SUFFIX_CHOICES, OWNER_CITED_LABEL_CHOICES, order_suffix_label_shape_ok,
                                       owner_cited_label_shape_ok)
    from tools.record_curation_patch import (order_suffix_decision_check, owner_cited_block_problem,
                                             owner_cited_decision_check)
    q3 = dict(DECISION, export=str(tmp_path / "e.json"), document_id=1457, question_id="q3")
    q4 = dict(q3, question_id="q4")
    cont = {"kind": "section", "printed_label": "6", "cited_label": "6", "source_block_id": 86106,
            "continues_opened": True, "owner_decision": q3}
    assert owner_cited_label_shape_ok(cont)
    assert not owner_cited_label_shape_ok(dict(cont, continues_opened=False))
    assert not owner_cited_label_shape_ok({k: v for k, v in cont.items() if k != "continues_opened"})  # 6 -> 6
    clause = {"kind": "clause", "label": "i", "source_block_ids": [86210, 86215], "owner_decision": q4}
    assert order_suffix_label_shape_ok(clause) and not order_suffix_label_shape_ok(dict(clause, kind="item"))
    assert owner_cited_block_problem(cont, {86106: "1[6. 2[\"(2) Where the Speaker"}) is None
    assert OWNER_CITED_LABEL_CHOICES == {"contents", "open-at-p3", "release-as-is", "rule-3", "assign", "rules",
                                         "number-1", "cite-47A", "repealed-stubs", "printed-6", "regulations", "other-copy",
                                         # doc 4149 q2 (export l; lead 15 Oct): the second '115' is cited s.115A
                                         "cite-115A",
                                         # doc 4426 q1/q2 (export j; delegated export, 15 Oct): 42A, 55A, 58A as printed
                                         "printed-42A", "same-as-42A",
                                         # doc 4498 q4/q6 (export l; 16 Oct): the body numbering stands
                                         "sequence",
                                         # doc 4588 q1 (owner 18 Oct; group 36): rules 29 and 46 under pasted slips
                                         "owner-numbered"} and ORDER_SUFFIX_CHOICES == {"keep-both"}
    (tmp_path / "e.json").write_text(json.dumps({"answers": [
        {"document_id": 1457, "question_id": "q3", "choice": "open-at-p3"},
        {"document_id": 1457, "question_id": "q4", "choice": "keep-both"},
        {"document_id": 1457, "question_id": "q1", "choice": "body"}]}), encoding="utf-8")
    owner_cited_decision_check([cont], 1457)
    order_suffix_decision_check([clause], 1457)
    with pytest.raises(ValueError, match=r"q1 choice 'body', not one of \['assign', 'cite-115A', 'cite-47A', 'contents', 'number-1', 'open-at-p3', 'other-copy', 'owner-numbered', 'printed-42A', 'printed-6', 'regulations', 'release-as-is', 'repealed-stubs', 'rule-3', 'rules', 'same-as-42A', 'sequence'\]"):
        owner_cited_decision_check([dict(cont, owner_decision=dict(q3, question_id="q1"))], 1457)
    with pytest.raises(ValueError, match="q3 choice 'open-at-p3', not 'keep-both'"):
        order_suffix_decision_check([dict(clause, owner_decision=q3)], 1457)
    reading = {"document_id": 1457, "page_no": 12, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_order_suffix_labels": [dict(clause, owner_decision=q3)]}
    with pytest.raises(ValueError, match="order suffix cites choice 'open-at-p3'"):
        materializer.unrecorded_readings([reading], [], 1457)


def test_reading_cited_pages_include_a_verified_additional_render():
    # doc 1457 s.20: an order-suffix group's prints stand on p11 and p12
    from tools.record_curation_patch import reading_cited_pages
    base = {"render": ".artifacts/x/renders/doc1457-p12.png"}
    assert reading_cited_pages(base, 1457, 12) == {12}
    assert reading_cited_pages(dict(base, additional_render=".artifacts/x/renders/doc1457-p11.png"), 1457, 12) == {11, 12}
    assert reading_cited_pages(dict(base, additional_render=".artifacts/x/renders/doc1456-p11.png"), 1457, 12) == {12}
    assert reading_cited_pages(dict(base, additional_render="strip-p11.png"), 1457, 12) == {12}


def test_unlabelled_appendix_opener_label_and_choice(tmp_path):
    # profile rule `unlabelled_appendix_opener` (doc 1491; owner decision 2026-10-08 export -g q1)
    from nizam.workers.segment import APPENDIX_OPENER_CHOICES, UNLABELLED_OPENER_LABELS
    from tools.record_curation_patch import unlabelled_opener_decision_check
    assert APPENDIX_OPENER_CHOICES == {"appendix-rows-by-serial", "appendix-rows"} and UNLABELLED_OPENER_LABELS == {"SCHEDULE", "APPENDIX"}
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [
        {"document_id": 1491, "question_id": "q1", "choice": "appendix-rows-by-serial"},
        {"document_id": 1491, "question_id": "q2", "choice": "rows-by-serial"}]}), encoding="utf-8")
    cite = {"export": str(export), "document_id": 1491, "question_id": "q1"}
    opener = {"source_block_id": 88500, "label": "APPENDIX", "source_text": "INDEX ...", "owner_decision": cite}
    unlabelled_opener_decision_check([opener], 1491)
    unlabelled_opener_decision_check([dict(opener, label="SCHEDULE", owner_decision=dict(cite, question_id="q2"))], 1491)
    with pytest.raises(ValueError, match="'APPENDIX' cites q2 choice 'rows-by-serial', not one asking for appendix rows"):
        unlabelled_opener_decision_check([dict(opener, owner_decision=dict(cite, question_id="q2"))], 1491)
    with pytest.raises(ValueError, match="label 'ANNEX' is not one of"):
        unlabelled_opener_decision_check([dict(opener, label="ANNEX")], 1491)
    reading = {"document_id": 1491, "page_no": 14, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_unlabelled_schedule_openers": [dict(opener, owner_decision=dict(cite, question_id="q2"))]}
    with pytest.raises(ValueError, match="unlabelled APPENDIX opener cites choice 'rows-by-serial'"):
        materializer.unrecorded_readings([reading], [], 1491)


def test_doc1626_half_paren_key_and_one_block_order_suffix():
    # profile rules `half_paren_clause_label` and `order_suffix_one_block` (doc 1626; owner decision 2026-10-08 q3)
    from nizam.workers.segment import order_suffix_label_shape_ok
    from tools.record_curation_patch import order_suffix_groups_ok
    merged = reviewed_structural_overrides([], [_patch(source_half_paren_clause_blocks=[101082]),
                                               _patch(source_half_paren_clause_blocks=[101090, 101082])])
    assert merged["source_half_paren_clause_blocks"] == [101082, 101090]
    for bad in ([], [101082, 101082], ["101082"]):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            reviewed_structural_overrides([], [_patch(source_half_paren_clause_blocks=bad)])
    assert "source_half_paren_clause_blocks" in STRUCTURAL_KEYS
    assert "source_half_paren_clause_blocks" in materializer.STRUCTURAL_PATCH_KEYS
    group = {"kind": "clause", "label": "c", "source_block_ids": [101082, 101082],
             "owner_decision": dict(DECISION, document_id=1626, question_id="q3")}
    assert order_suffix_label_shape_ok(group) and order_suffix_groups_ok([group])
    assert order_suffix_label_shape_ok(dict(group, kind="section"))                # one block twice: clauses, and
    assert order_suffix_label_shape_ok(dict(group, kind="article"))                # since agent K4's rule O sections
    assert not order_suffix_label_shape_ok(dict(group, kind="paragraph"))          # and articles; nothing else
    assert not order_suffix_label_shape_ok(dict(group, source_block_ids=[101082, 101082, 101083]))
    other = dict(group, label="b", source_block_ids=[101082, 101090])
    assert not order_suffix_groups_ok([group, other])                              # a block in two groups


def test_doc1666_bracketed_print_and_index_row_plumbing():
    # doc 1666 (owner q1 'rule-3'): a '(N)' print; docs 1889/1635: index rows
    from nizam.workers.segment import contents_row_link_shape_ok, owner_cited_label_shape_ok
    from tools.record_curation_patch import owner_cited_block_problem
    cite = dict(DECISION, export=DECISION["export"].replace("-06-c", "-08-h"), document_id=1666, question_id="q1")
    entry = {"kind": "section", "printed_label": "3", "cited_label": "3", "source_block_id": 105298,
             "printed_bracketed": True, "owner_decision": cite}
    assert owner_cited_label_shape_ok(entry)
    assert not owner_cited_label_shape_ok(dict(entry, cited_label="4"))
    assert not owner_cited_label_shape_ok(dict(entry, printed_bracketed=False))
    assert owner_cited_block_problem(entry, {105298: "(3) Authority to deal with cases ...:-"}) is None
    assert "bracketed print (3) not printed" in owner_cited_block_problem(entry, {105298: "3. Authority ..."})
    link = {"ordinal": 2, "printed_label": "3", "unit_label": "3", "owner_decision": cite}
    assert contents_row_link_shape_ok(link) and contents_row_link_shape_ok(dict(link, index_row=True))
    assert not contents_row_link_shape_ok(dict(link, index_row=False))
    assert not contents_row_link_shape_ok(dict(link, index_row="yes"))


def test_owner_cited_choice_rules_for_doc2191(tmp_path):
    # doc 2191 (owner decision 2026-10-10 export -i q1 'rules'): rules 19-35 printed '(19)'-'(35)' are held as rules
    from tools.record_curation_patch import owner_cited_decision_check
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [{"document_id": 2191, "question_id": "q1", "choice": "rules"},
                                              {"document_id": 2191, "question_id": "q2", "choice": "keep-2191"}]}),
                      encoding="utf-8")
    cite = {"export": str(export), "document_id": 2191, "question_id": "q1"}
    entry = {"kind": "section", "printed_label": "19", "cited_label": "19", "source_block_id": 167300,
             "printed_bracketed": True, "owner_decision": cite}
    owner_cited_decision_check([entry], 2191)
    with pytest.raises(ValueError, match="q2 choice 'keep-2191'"):
        owner_cited_decision_check([dict(entry, owner_decision=dict(cite, question_id="q2"))], 2191)


def test_owner_cited_choices_admitted_13_oct(tmp_path):
    # lead 13 Oct (owner export j): doc 4222 q1 'repealed-stubs' (4222 itself stays blocked) and doc 4154 q2
    # 'printed-6' (the section printed '7. 6.' is s.6) are owner-cited answers; an answer outside the closed set
    # is still refused.
    from nizam.workers.segment import OWNER_CITED_LABEL_CHOICES
    from tools.record_curation_patch import owner_cited_decision_check
    assert {"repealed-stubs", "printed-6"} <= OWNER_CITED_LABEL_CHOICES
    export = tmp_path / "decision-review-j.json"
    export.write_text(json.dumps({"answers": [
        {"document_id": 4222, "question_id": "q1", "choice": "repealed-stubs"},
        {"document_id": 4154, "question_id": "q2", "choice": "printed-6"},
        {"document_id": 4154, "question_id": "q3", "choice": "printed-7"}]}), encoding="utf-8")
    def entry(doc, q):
        return {"kind": "section", "printed_label": "7", "cited_label": "6", "source_block_id": 603000,
                "owner_decision": {"export": str(export), "document_id": doc, "question_id": q}}
    owner_cited_decision_check([entry(4222, "q1")], 4222)
    owner_cited_decision_check([entry(4154, "q2")], 4154)
    with pytest.raises(ValueError, match="q3 choice 'printed-7', not one of"):
        owner_cited_decision_check([entry(4154, "q3")], 4154)


def test_choices_admitted_13_oct_group4():
    # lead 13 Oct (owner export j): 3700 q1 'regulations' and 2985 q2 'other-copy' (owner-cited labels), 2611 q1 'body'
    # (schedule group captions), 2658 q1 'appendix-rows' (unlabelled APPENDIX opener; same effect as
    # 'appendix-rows-by-serial'). Any other answer is still refused.
    from nizam.workers.segment import (APPENDIX_OPENER_CHOICES, OWNER_CITED_LABEL_CHOICES,
                                       SCHEDULE_GROUP_CAPTION_CHOICES)
    assert {"regulations", "other-copy"} <= OWNER_CITED_LABEL_CHOICES
    assert "body" in SCHEDULE_GROUP_CAPTION_CHOICES and "appendix-rows" in APPENDIX_OPENER_CHOICES
    assert "body" not in APPENDIX_OPENER_CHOICES and "appendix-rows" not in SCHEDULE_GROUP_CAPTION_CHOICES
