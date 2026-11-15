"""Rule `reviewed_decimal_regulation_series` (doc 9911, CDA Employees Service Regulations, 15 Nov 2026).

A body numbering its regulations chapter.serial ('4.17.') prints numbered paragraphs '1.', '2.' inside them. Unflagged,
those paragraphs open as top-level sections that collide across regulations, and a run of them leaves a plain section
open that swallows every later decimal regulation as a clause. The page-read observation flag
`source_decimal_regulation_series` makes such a paragraph the open regulation's sub-regulation. Data-gated."""
import pytest

from nizam.corpus import segment as S
import nizam.workers.segment as W

# the printed shape of doc 9911 pp36-43: regulation, numbered paragraphs, next regulation, a run 6-13, next chapter
TEXTS = (
    "CHAPTER 04\nAPPOINTMENTS",
    "4.17.\nProcedure for Promotion.-",
    "1.\nPromotion to posts in basic scale 20 shall be made by the appointing authority.",
    "2.\nPromotion to posts in basic pay scale 17 to 19 shall be made by the appointing authority.",
    "4.18\nConditions of Promotion:-",
    "1.\nAn employee possessing such minimum qualifications shall be eligible for promotion.",
    "2.\nPromotion to a post shall be subject to passing of an examination.",
    "4.20-A\nPromotion policy.-",
    "6.\nCONDITIONS FOR SUPERSESSION:- An officer shall be recommended for supersession, if: -",
    "7.\nCONSIDERATION OF PROMOTION IN CASE SENIORITY IS SUB-JUDICE: The case shall be deferred.",
    "CHAPTER 05\nTRANSFER AND POSTING",
    "5.01.\nLiability to serve in any post:- An employee shall be liable to serve in any post.",
    "5.02.\nTransfer from one post to the other within the Authority:- The Authority may transfer an employee.",
)


def blocks():
    return [{"id": 100 + i, "text": t + "\n", "page_no": 1 + i // 6, "y0": 100 + 60 * (i % 6), "page_height": 800,
             "x0": 72, "x1": 520} for i, t in enumerate(TEXTS)]


def sections(seg):
    return [n.label for n in seg.flatten() if n.kind == "section"]


def children(seg, label):
    node = next(n for n in seg.flatten() if n.kind == "section" and n.label == label)
    return [(c.kind, c.label) for c in node.children]


def test_flagged_paragraphs_are_sub_regulations_and_later_regulations_stay_sections():
    on = S.segment(blocks(), structural_overrides={"source_decimal_regulation_series": True})
    assert sections(on) == ["4.17", "4.18", "4.20-A", "5.01", "5.02"]
    assert children(on, "4.17") == [("subsection", "1"), ("subsection", "2")]
    assert [label for kind, label in children(on, "4.20-A")] == ["6", "7"]


def test_a_schedule_inside_a_regulation_closes_at_the_next_regulation():
    texts = ("CHAPTER 04\nAPPOINTMENTS",
             "4.20-A\nPromotion policy.- The policy below applies.",
             "SCHEDULE-III\nQUANTIFYING THE PERFORMANCE EVALUATION REPORTS: -",
             "1.\nIn accordance with clause (a) the PERs shall be quantified.",
             "2.\nThe overall grading in the PERs are allocated the following marks.",
             "4.21.\nPromotion cannot be claimed on seniority alone.- No employee shall have a claim to promotion.",
             "CHAPTER 5\nPosting and Transfer",
             "5.01.\nLiability to serve in any post:- An employee shall be liable to serve in any post.")
    bl = [{"id": 200 + i, "text": t + "\n", "page_no": 1, "y0": 60 + 60 * i, "page_height": 800, "x0": 72, "x1": 520}
          for i, t in enumerate(texts)]
    on = S.segment(bl, structural_overrides={"source_decimal_regulation_series": True})
    assert sections(on) == ["4.20-A", "4.21", "5.01"]
    schedule = next(n for n in on.flatten() if n.kind == "schedule")
    assert [c.label for c in schedule.children] == ["1", "2"]


def test_a_wrapped_regulation_reference_is_text_not_an_opener():
    texts = ("CHAPTER 21\nPENSION",
             "21.18\nAn application for retirement on invalid pension. (1) An application shall be made to the authority "
             "specified in regulation",
             "21.38.",
             "21.19\nThe Power to grant invalid pension. If the incapacity is directly due to irregular habits, no pension.",
             "21.20\nCalculation.- The pension shall be calculated as provided in regulations",
             "21.27 to 21.32.",
             "21.21\nGratuity.- A gratuity is paid in a single sum.")
    bl = [{"id": 300 + i, "text": t + "\n", "page_no": 1, "y0": 60 + 60 * i, "page_height": 800, "x0": 72, "x1": 520}
          for i, t in enumerate(texts)]
    on = S.segment(bl, structural_overrides={"source_decimal_regulation_series": True})
    assert sections(on) == ["21.18", "21.19", "21.20", "21.21"]
    r20 = next(n for n in on.flatten() if n.kind == "section" and n.label == "21.20")
    assert "21.27 to 21.32" in " ".join(r20.text_parts)


def test_a_regulation_glued_into_the_block_before_opens_and_a_wrapped_reference_does_not():
    # doc 9911 p75: '8.05. Suspension etc.' is printed inside the block of 8.04's clause c; a reference inside a block
    # ('... the procedure indicated in regulation / 8.08 shall apply.') must stay text
    texts = ("CHAPTER 8\nDISCIPLINE",
             "8.04\nRetirement.- (1) An employee may be retired.\n"
             "c. engaged under a contract in accordance with the terms of the contract.\n"
             "8.05. Suspension etc. In case where an employee is accused of misconduct, he may be suspended.",
             "8.06. Procedure for disciplinary action.\n1. The authorized officer shall decide; the procedure in regulation\n"
             "8.08 shall apply.\n2. If no inquiry is needed he shall inform the accused.",
             "8.07. Procedure.\n1. On receipt of the report the authorized officer shall hear the accused.")
    bl = [{"id": 400 + i, "text": t + "\n", "page_no": 1, "y0": 60 + 90 * i, "page_height": 800, "x0": 72, "x1": 520}
          for i, t in enumerate(texts)]
    on = S.segment(bl, structural_overrides={"source_decimal_regulation_series": True})
    assert sections(on) == ["8.04", "8.05", "8.06", "8.07"]


def test_unflagged_the_parse_is_unchanged():
    off = S.segment(blocks())
    flagged = S.segment(blocks(), structural_overrides={"source_decimal_regulation_series": True})
    assert sections(off) != sections(flagged)          # the defect the flag repairs is real in the default parse


def test_the_flag_is_an_observation_flag_only():
    patch = lambda v: {"evidence": {"structural_overrides": {"source_decimal_regulation_series": v}}}
    assert W.reviewed_structural_overrides([], [patch(True), patch(True)])["source_decimal_regulation_series"] is True
    for bad in (1, "yes", [100]):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            W.reviewed_structural_overrides([], [patch(bad)])
    from tools import materialize_multi_instrument as materializer
    from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, STRUCTURAL_KEYS
    key = "source_decimal_regulation_series"
    assert key in STRUCTURAL_KEYS and key in GENERIC_STRUCTURAL_KEYS and key in materializer.STRUCTURAL_PATCH_KEYS
