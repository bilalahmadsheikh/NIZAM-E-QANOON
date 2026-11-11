"""Doc9868 source-read amendment brackets, notifications and exact title locator.

These fixtures preserve the reviewed printed spellings, including ``1n``.
They exercise parser output and stale-evidence refusal without a database.
"""
import copy
import hashlib

import pytest

from nizam.corpus import segment as S


def block(bid, text, page=1, y=120):
    return dict(id=bid, text=text, page_no=page, y0=y,
                page_height=792, x0=70, x1=560)


RULES = [
    (2690058, 37, "40A", "[40A. Special procedure for collection of excise duty on [* * *] services provided by banking companies, financial institutions and non-banking finance companies . -- (1) The provisions of these rules shall apply for collection and payment of excise duty by persons providing or rendering financial services as[notified under the First Schedule to the Act]."),
    (2690211, 42, "41-C", "[41-C. ***]"),
    (2690502, 54, "48", "[48. Procedure for appeals to Commissioner (Appeals).-- (1) An appeal under section 33 of the Act shall be in the form and verified in the manner indicated in form prescribed under rule-48A."),
]


@pytest.mark.parametrize("bid,page,label,text", RULES, ids=["40A", "41-C", "48"])
@pytest.mark.parametrize("profile", ["default", "unreleased-v5"])
def test_reviewed_bare_bracket_rule_preserves_text_and_provenance(bid, page, label, text, profile):
    blocks = [block(1, "1. Previous rule.-- The previous text continues.", page, 60),
              block(bid, text, page),
              block(2, "99. Following rule.-- The following text applies.", page, 200)]
    original = copy.deepcopy(blocks)
    # Match the staged prefix: it ends before the separately cut sub-rule(1).
    opener = dict(source_block_id=bid, label=label,
                  source_prefix=text.partition(" (1)")[0][:80])
    seg = S.segment(blocks, detect_contents=False, profile=profile,
                    structural_overrides={"source_printed_rule_openers": [opener]})
    node = next(n for n in seg.flatten() if n.kind == "section" and n.label == label)
    assert node.first_block == bid and node.first_page == page and bid in node.blocks
    assert [n.label for n in seg.root.children if n.kind == "section"] == ["1", label, "99"]
    joined = " ".join(n.text for n in [node, *node.children] if n.text)
    assert ("***" in joined if label == "41-C" else "The provisions" in joined
            if label == "40A" else "An appeal under section 33" in joined)
    assert not node.text.startswith("[")
    assert blocks == original


@pytest.mark.parametrize("change", ["block", "prefix"])
def test_reviewed_bare_bracket_rule_refuses_stale_evidence(change):
    bid, page, label, text = RULES[0]
    opener = dict(source_block_id=bid, label=label, source_prefix=text[:80])
    if change == "block":
        opener["source_block_id"] += 1
    else:
        opener["source_prefix"] = opener["source_prefix"].replace("collection", "payment")
    with pytest.raises(ValueError, match="source printed rule opener"):
        S.segment([block(bid, text, page)], detect_contents=False,
                  structural_overrides={"source_printed_rule_openers": [opener]})


def test_bare_bracket_unstopped_opener_requires_reviewed_entry():
    # The printed-rule extension must not admit arbitrary unstopped brackets.
    text = "[48E Filing of affidavit regarding contrary facts. Where a fact is alleged."
    blocks = [block(1, "48. Previous rule.-- The previous text continues.", y=60),
              block(2, text)]
    plain = S.segment(blocks, detect_contents=False)
    assert not any(n.label == "48E" for n in plain.flatten())
    reviewed = S.segment(blocks, detect_contents=False,
                         structural_overrides={"source_printed_rule_openers": [
                             dict(source_block_id=2, label="48E", source_prefix=text)]})
    assert any(n.kind == "section" and n.label == "48E" and n.first_block == 2
               for n in reviewed.flatten())


def chapter_blocks(text="[Chapter XVI", bid=2691066):
    return [block(1, "80. Previous rule.-- The previous text continues.", 89, 60),
            block(bid, text, 89),
            block(2691070, "81. Interpretation and application.-- These rules apply to GLT units.", 89, 200)]


def test_reviewed_bare_bracket_chapter_owns_following_rule():
    blocks = chapter_blocks()
    original = copy.deepcopy(blocks)
    seg = S.segment(blocks, detect_contents=False,
                    structural_overrides={"source_chapter_opener_blocks": [2691066]})
    chapter = next(n for n in seg.root.children if n.kind == "chapter")
    assert chapter.label == "XVI" and chapter.first_block == 2691066
    assert [(n.kind, n.label) for n in chapter.children] == [("section", "81")]
    assert chapter.children[0].first_block == 2691070
    assert blocks == original


def test_unstaged_bare_bracket_chapter_does_not_open():
    seg = S.segment(chapter_blocks(), detect_contents=False)
    assert not any(n.kind == "chapter" for n in seg.flatten())
    assert [n.label for n in seg.root.children if n.kind == "section"] == ["80", "81"]


@pytest.mark.parametrize("blocks", [chapter_blocks(bid=2691067),
                                     chapter_blocks(text="[Chapter XVI unrelated prose")])
def test_reviewed_bare_bracket_chapter_refuses_missing_or_changed_opener(blocks):
    with pytest.raises(ValueError, match="source.chapter|source_chapter"):
        S.segment(blocks, detect_contents=False,
                  structural_overrides={"source_chapter_opener_blocks": [2691066]})


MAIN_INTRO = (
    "Notification No. S.R.O. 534(1)/2005, dated 6th June, 2005.--1n exercise of the powers conferred by "
    "[sub-section (3) of section 6, sub-section (5) of section 12 and] section 40 of the Federal Excise "
    "Act, 2005 [** *], the Federal Board of Revenue is pleased to make the following rules, namely:--")
FILING_INTRO = (
    "Notification No. S.R.O. 1185(1)/2005, dated 1st December, 2005.-In exercise of the powers conferred "
    "by sub-section (6) of section 4 of the Federal Excise Act, 2005, the Federal Board of Revenue is "
    "pleased to make the following rules, namely:--")
INTROS = [
    (2689371, 7, MAIN_INTRO, "4fb904c1396882cdca126b239b63c1e07a42a55270b7593593256bdcaefc2eb0"),
    (2691166, 94, FILING_INTRO, "1c76b02a6f805c5fbb64069cd33a4cea7336350ca22e8700188c8a388b66ba97"),
]


def parse_intro(bid, page, text):
    return S.segment([block(bid, text, page, 60),
                      block(bid + 1, "1. Short title.-- These rules apply.", page, 200)],
                     detect_contents=False, profile="unreleased-v5",
                     structural_overrides={"source_body_start_block": bid})


@pytest.mark.parametrize("bid,page,text,digest", INTROS)
def test_exact_reviewed_notification_is_preamble_before_rule_one(bid, page, text, digest):
    assert hashlib.sha256(text.encode()).hexdigest() == digest
    seg = parse_intro(bid, page, text)
    assert [n.kind for n in seg.root.children] == ["preamble", "section"]
    preamble = seg.root.children[0]
    assert preamble.text == text and preamble.first_block == bid and preamble.first_page == page


@pytest.mark.parametrize("bid,page,text,digest", INTROS)
@pytest.mark.parametrize("change", ["id", "page", "text"])
def test_notification_exception_rejects_other_id_page_or_words(bid, page, text, digest, change):
    if change == "id":
        bid += 10
    elif change == "page":
        page += 1
    else:
        text = text.replace("Federal Board", "Central Board")
    assert not S._is_source_preamble_intro_block(block(bid, text, page))
    assert not any(n.kind == "preamble" for n in parse_intro(bid, page, text).root.children)


def test_main_notification_literal_one_n_cannot_be_silently_corrected():
    text = MAIN_INTRO.replace("--1n exercise", "--In exercise")
    assert not S._is_source_preamble_intro_block(block(2689371, text, 7))
    assert not any(n.kind == "preamble" for n in parse_intro(2689371, 7, text).root.children)


TITLE = "FEDERAL EXCISE RULES, 2005 \n \n \n"


def title_patch():
    return dict(page_no=7, match_text=TITLE, before_text=TITLE,
                after_text="FEDERAL EXCISE RULES, 2005",
                evidence=dict(exact_block_locator=True, source_block_id=2689370))


def test_exact_block_api_changes_only_named_duplicate_and_preserves_extraction():
    blocks = [block(2689369, TITLE, 7), block(2689370, TITLE, 7)]
    original = copy.deepcopy(blocks)
    patch = title_patch()
    out, count = S._apply_curation_patches(blocks, [patch])
    assert count == 1 and out[0] == blocks[0]
    assert out[1]["text"] == patch["after_text"] and blocks == original
    with pytest.raises(ValueError, match="matched 2 blocks"):
        S._apply_curation_patches(blocks, [dict(patch, evidence={})])


@pytest.mark.parametrize("change", [
    {"page_no": 8}, {"match_text": "FEDERAL EXCISE RULES"},
    {"before_text": TITLE.strip()},
    {"evidence": {"exact_block_locator": True, "source_block_id": 9}},
    {"evidence": {"exact_block_locator": True, "source_block_id": "2689370"}},
    {"evidence": {"exact_block_locator": False, "source_block_id": 2689370}},
])
def test_exact_block_api_refuses_partial_stale_or_malformed_locator(change):
    with pytest.raises(ValueError):
        S._apply_curation_patches([block(2689370, TITLE, 7)], [dict(title_patch(), **change)])


def test_exact_block_assignment_preserves_expression_ownership():
    from tools.materialize_multi_instrument import assign_patches

    blocks = [block(2689369, TITLE, 7), block(2689370, TITLE, 7)]
    patch = title_patch()
    assigned, outside = assign_patches(blocks, [patch], {2689369: 0, 2689370: 1})
    assert assigned == {1: [patch]} and outside == []
    evidence = dict(patch["evidence"], structural_overrides={"source_apparatus_blocks": [2689369]})
    with pytest.raises(ValueError, match="structural overrides name"):
        assign_patches(blocks, [dict(patch, evidence=evidence)], {2689369: 0, 2689370: 1})
