"""Agent DC's round-2 rules (stage 3, 12 Oct 2026; docs/SEGMENTATION-PROFILES.md). Each is data-gated.

  owner_cited_label_reviewed_default  a reviewed `source_owner_cited_labels` entry is honoured in any profile; an entry
                                      may cite a lettered label ('47A') and name which print it relabels
                                      (`source_occurrence`; doc 2756 p25 prints '47.' twice).
  reviewed_schedule_heading           `source_schedule_heading_blocks`: a page-read Schedule display heading opens the
                                      Schedule (doc 2703 p7); fail-closed when a named block opens none.
  reviewed_repeal_stub_cut            `source_repeal_stub_cut_blocks`: profile rule bracketed_repeal_stub_cut's cut, in
                                      a reviewed block only (doc 2703 p7); fail-closed when a named block has no stub.
  reviewed_running_header_blocks      `source_running_header_blocks`: reviewed running titles leave the body (doc 4497,
                                      supplied by the materializer for the ESTACODE titles only).
"""
import pytest

from nizam.corpus import segment as S
from nizam.workers.segment import OWNER_CITED_LABEL_CHOICES, reviewed_structural_overrides
from tools.materialize_multi_instrument import _ESTACODE_RUNNING_TITLE, REJECTED_EDITORIAL_BOUNDARIES
from tools.record_curation_patch import STRUCTURAL_KEYS


def blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


def labels(seg):
    return [(n.kind, n.label) for n in seg.flatten()]


CITE = {"kind": "section", "printed_label": "47", "cited_label": "47A", "source_block_id": 243325,
        "owner_decision": {"export": "PENDING-2756.json", "document_id": 2756, "question_id": "q1"}}


def test_owner_cited_entries_may_be_lettered_and_name_an_occurrence():
    assert S._owner_cited_label_shape_ok(CITE)
    assert S._owner_cited_label_shape_ok(dict(CITE, source_occurrence=2))
    assert not S._owner_cited_label_shape_ok(dict(CITE, source_occurrence=1))     # 1 is the default; name >= 2
    assert not S._owner_cited_label_shape_ok(dict(CITE, cited_label="47a"))
    assert "cite-47A" in OWNER_CITED_LABEL_CHOICES


STUB = blocks("1. Short title. This Act may be called the Test Act.",
              "8. Registration. A society is registered.\n9. [Savings as to estates of soldiers.] Omitted by Act IV.\n"
              "10. [Repeals.] Rep. by the Repealing Act.")


def test_repeal_stub_cut_only_in_a_reviewed_block_and_fail_closed():
    cut = S.segment(STUB, structural_overrides={"source_repeal_stub_cut_blocks": [101]})
    assert ("section", "9") in labels(cut) and ("section", "10") in labels(cut)
    plain = labels(S.segment(STUB))
    assert labels(S.segment(STUB, structural_overrides={})) == plain
    with pytest.raises(ValueError, match="reviewed repeal stub cut found no stub"):
        S.segment(STUB, structural_overrides={"source_repeal_stub_cut_blocks": [100]})


def test_a_reviewed_schedule_heading_that_opens_nothing_fails_closed():
    with pytest.raises(ValueError, match="reviewed schedule heading opened no schedule"):
        S.segment(STUB, structural_overrides={"source_schedule_heading_blocks": [100]})


def test_reviewed_running_header_blocks_leave_the_body():
    title = "CHAPTER-2 ESTACODE (EDITION-2021) Page -17"
    b = blocks("1. Short title. These rules may be called the Test Rules.", title,
               "2. Definitions. In these rules the Board means the Board.")
    plain = " ".join(n.text or "" for n in S.segment(b).flatten())
    gone = " ".join(n.text or "" for n in S.segment(b, structural_overrides={"source_running_header_blocks": [101]}).flatten())
    assert "ESTACODE" not in gone
    assert labels(S.segment(b, structural_overrides={"source_running_header_blocks": [101]}))[:1] == [("section", "1")]
    assert plain != gone or "ESTACODE" not in plain


def test_the_materializer_knows_the_estacode_running_titles_and_the_e1_note():
    for t in ("CHAPTER-2 ESTACODE (EDITION-2021) Page -17", "Page - 18 ESTACODE (EDITION-2021) CHAPTER-2",
              "INDEX ESTACODE (EDITION-2021) Page-968", "Page-969 ESTACODE (EDITION-2021) INDEX"):
        assert _ESTACODE_RUNNING_TITLE.fullmatch(t)
    assert not _ESTACODE_RUNNING_TITLE.fullmatch("CHAPTER-2 ESTACODE (EDITION-2021) Page -17 1.1 Rules")
    assert 885517 in REJECTED_EDITORIAL_BOUNDARIES


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


@pytest.mark.parametrize("key", ["source_schedule_heading_blocks", "source_repeal_stub_cut_blocks"])
def test_the_worker_unites_the_round2_keys_and_the_recorder_knows_them(key):
    assert reviewed_structural_overrides([], [_patch(**{key: [12]}), _patch(**{key: [10]})])[key] == [10, 12]
    with pytest.raises(ValueError, match=key):
        reviewed_structural_overrides([], [_patch(**{key: ["x"]})])
    assert key in STRUCTURAL_KEYS
