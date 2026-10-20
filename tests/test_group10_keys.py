"""Group 10 ports (16 Oct 2026, builder BZ; one combined full released A/B is the gate): agent JE's rules 8-12, agent K4's
A-F (E = agent JC's bare_label_over_first_item), agent K5's MS/CO/TU and agent K3's A-D. These tests pin the wiring the
builder owns -- every new key reaches the worker merge, the recorder and the multi-instrument dry run; keyed lists merge
by their key and refuse a disagreement; the recorder checks cited owner answers -- and the builder's fix to K4 rule C
(its check no longer raises inside segment()'s finally block)."""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BLOCK = ["source_heading_line_stub_blocks", "source_quote_span_end_blocks", "source_percent_clause_blocks",
         "source_marked_subsection_cut_blocks", "source_chapter_opener_blocks",
         "source_section_word_part_blocks", "source_dash_label_section_blocks"]
KEYED = {"source_paired_repeal_stubs": "body_block_id", "source_quoted_appendix_labels": "block_id",
         "source_note_owner_blocks": "block_id", "source_heading_lines": "label"}
JE_KEYS = ["source_printed_rule_openers", "source_set_aside_units", "source_hyphen_rule_numbers"]
OD = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 3602,
      "question_id": "q1"}


def _patch(i, **overrides):
    return {"id": f"p{i}", "page_no": i, "match_text": "x", "before_text": "x", "after_text": "x",
            "evidence": {"structural_overrides": overrides}}


SAMPLES = {
    "source_paired_repeal_stubs": lambda n: {"body_block_id": n, "contents_block_id": n + 1, "labels": ["2", "3"],
                                             "owner_decision": OD},
    "source_quoted_appendix_labels": lambda n: {"block_id": n, "printed": "A-1", "label": "A-1"},
    "source_note_owner_blocks": lambda n: {"block_id": n, "owner_block_id": n + 1, "owner_label": "22A",
                                           "owner_kind": "section"},
    "source_heading_lines": lambda n: {"label": str(n), "source_block_id": n, "heading": "Heading.",
                                       "owner_decision": OD},
}


def test_every_group10_key_is_known_everywhere():
    from tools import materialize_multi_instrument as mat
    from tools import record_curation_patch as rcp
    for key in BLOCK + list(KEYED) + JE_KEYS:
        assert key in rcp.STRUCTURAL_KEYS and key in rcp.GENERIC_STRUCTURAL_KEYS, key
        assert key in mat.STRUCTURAL_PATCH_KEYS, key
    assert set(mat.STRUCTURAL_PATCH_KEYS) == set(rcp.STRUCTURAL_KEYS)


@pytest.mark.parametrize("key", BLOCK)
def test_block_lists_merge_and_refuse_malformed(key):
    from nizam.workers.segment import reviewed_structural_overrides
    merged = reviewed_structural_overrides(None, [_patch(1, **{key: [11, 12]}), _patch(2, **{key: [12, 13]})])
    assert merged[key] == [11, 12, 13]
    for bad in ([], [0], ["7"], [5, 5]):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            reviewed_structural_overrides(None, [_patch(1, **{key: bad})])


@pytest.mark.parametrize("key", sorted(KEYED))
def test_keyed_lists_merge_by_key_and_refuse_a_disagreement(key):
    from nizam.workers.segment import reviewed_structural_overrides
    one, two = SAMPLES[key](100), SAMPLES[key](200)
    merged = reviewed_structural_overrides(None, [_patch(1, **{key: [one]}), _patch(2, **{key: [two]})])
    assert sorted(str(v[KEYED[key]]) for v in merged[key]) == sorted([str(one[KEYED[key]]), str(two[KEYED[key]])])
    clash = dict(one, **({"heading": "Other."} if key == "source_heading_lines" else
                         {"owner_label": "23"} if key == "source_note_owner_blocks" else
                         {"label": "B-1"} if key == "source_quoted_appendix_labels" else {"labels": ["4", "5"]}))
    with pytest.raises(ValueError, match="conflicting reviewed"):
        reviewed_structural_overrides(None, [_patch(1, **{key: [one]}), _patch(2, **{key: [clash]})])
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides(None, [_patch(1, **{key: [dict(one, stray=1)]})])


def test_the_recorder_checks_cited_owner_answers_of_group10_keys():
    src = (ROOT / "tools/record_curation_patch.py").read_text(encoding="utf-8")
    branch = src[src.index("bz_owned = [v for k in"):src.index("generic = {k: r.get(k)")]
    for key in ("source_paired_repeal_stubs", "source_quoted_appendix_labels", "source_heading_lines"):
        assert f'"{key}"' in branch
    assert 'owner_decision_answer(v["owner_decision"], doc)' in branch and "refused.append" in branch


def test_k4_rule_names_join_unreleased_v4_and_the_choices_are_admitted():
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    from nizam.workers.segment import OWNER_CITED_LABEL_CHOICES
    assert {"paired_repeal_stub", "heading_line_stub_cut", "reviewed_quote_span_end", "reviewed_quoted_appendix_label",
            "bare_label_over_first_item", "reviewed_percent_clause_cut"} <= SEGMENTATION_PROFILES["unreleased-v4"]
    assert {"printed-42A", "same-as-42A"} <= OWNER_CITED_LABEL_CHOICES


def test_k4_rule_c_no_longer_raises_inside_the_finally_block():
    # The prototype raised in segment()'s finally block (skipping every later context-variable reset, the active
    # profile rules included) and called sys.exc_info() in a module that never imports sys.
    src = (ROOT / "nizam/corpus/segment.py").read_text(encoding="utf-8")
    assert "sys.exc_info()" not in src
    reset = src.index("        _ACTIVE_PROFILE_RULES.reset(token)\n    # agK4 rule C")
    check = src.index('raise ValueError(f"source quote span end blocks reached by no open quoted span')
    assert check > reset


def test_recorder_and_worker_key_owner_cited_prints_alike():
    # doc 4498 (16 Oct): the worker merges owner-cited entries per (block, printed label, kind, occurrence, prefix)
    # since JE's rules 10 and 13, so several unnumbered openers may share one block; the recorder's distinct-print
    # check must use the same key, else it refuses readings the parser accepts. 'sequence' (4498 q4/q6) is admitted.
    from nizam.workers.segment import OWNER_CITED_LABEL_CHOICES
    rec = (ROOT / "tools/record_curation_patch.py").read_text(encoding="utf-8")
    wk = (ROOT / "nizam/workers/segment.py").read_text(encoding="utf-8")
    assert 'v.get("source_occurrence", 1),\n                              v.get("source_prefix")) for v in owner_cited}' in rec
    assert 'item.get("source_occurrence", 1),' in wk and 'item.get("source_prefix"))' in wk
    assert "sequence" in OWNER_CITED_LABEL_CHOICES
