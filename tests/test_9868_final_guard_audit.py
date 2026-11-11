"""Independent audit regressions for the final 9868 reviewed branches."""
import copy

import pytest

from nizam.corpus import segment as S


def block(bid, text, page=60, y=100):
    return dict(id=bid, text=text, page_no=page, y0=y,
                page_height=792, x0=70, x1=560)


K_PREFIX = "48K. Maintenance and preservation of registers.—"
K_TEXT = (K_PREFIX + " The following registers shall be maintained according to the format, namely:–\n"
          "S. No. | Name of Register\n1. | Appeals Register\n2. | Stay Application Register\n"
          "3. | Early hearing Register\n4. | Register for Compliance of Court\n"
          "FORMAT OF REGISTERS\nAPPEAL REGISTER\n"
          "S# | Appeal No. | Date of institution of Appeal\n(1) | (2) | (3)")


def table_blocks():
    return [block(1, "48J. Hearing of appeal or stay application.— The appellant shall be heard.", y=60),
            block(2691269, K_TEXT),
            block(2, "48L. Reports.— The Commissioner shall send the report.", page=61)]


@pytest.mark.parametrize("profile", ["default", "unreleased-v5"])
def test_exact_reviewed_rule_opens_before_its_own_numbered_table(profile):
    blocks = table_blocks()
    original = copy.deepcopy(blocks)
    assert S._is_numbered_table_header(K_TEXT)
    seg = S.segment(blocks, detect_contents=False, profile=profile,
                    structural_overrides={"source_printed_rule_openers": [
                        dict(source_block_id=2691269, label="48K", source_prefix=K_PREFIX)]})
    rules = [n for n in seg.flatten() if n.kind == "section"]
    assert [n.label for n in rules] == ["48J", "48K", "48L"]
    owner = rules[1]
    assert owner.first_block == 2691269 and owner.first_page == 60
    assert "Name of Register" in owner.text and "(1) | (2) | (3)" in owner.text
    assert "Register" not in rules[0].text
    assert blocks == original


def test_unreviewed_numbered_table_keeps_existing_owner():
    seg = S.segment(table_blocks(), detect_contents=False)
    rules = [n for n in seg.flatten() if n.kind == "section"]
    # With no reviewed opener or contents-proved close, existing table mode
    # keeps even the following printed rule within its current owner.
    assert [n.label for n in rules] == ["48J"]
    assert " ".join(K_TEXT.split()) in rules[0].text


@pytest.mark.parametrize("change", ["id", "prefix", "label"])
def test_table_guard_does_not_bypass_reviewed_opener_validation(change):
    spec = dict(source_block_id=2691269, label="48K", source_prefix=K_PREFIX)
    if change == "id":
        spec["source_block_id"] += 1
    elif change == "prefix":
        spec["source_prefix"] = K_PREFIX.replace("preservation", "destruction")
    else:
        spec["label"] = "48L"
    with pytest.raises(ValueError, match="source printed rule opener"):
        S.segment(table_blocks(), detect_contents=False,
                  structural_overrides={"source_printed_rule_openers": [spec]})


def annex_blocks(text="[ANNEX-I\n[See rule 84]\nDeclaration of tobacco received", bid=3):
    return [block(1, "89. Requirements.— The units shall declare the goods.", page=91),
            block(bid, text, page=92),
            block(4, "Name of factory: __________________", page=92, y=180)]


@pytest.mark.parametrize("opener", ["ANNEX-I", "[ANNEX-I", "111[ANNEX-I"])
@pytest.mark.parametrize("profile", ["default", "unreleased-v5"])
def test_reviewed_annex_accepts_bare_bracket_without_losing_content(opener, profile):
    blocks = annex_blocks(opener + "\n[See rule 84]\nDeclaration of tobacco received")
    original = copy.deepcopy(blocks)
    seg = S.segment(blocks, detect_contents=False, profile=profile,
                    structural_overrides={"source_division_openers": [
                        dict(source_block_id=3, kind="annexure", label="ANNEX-I")]})
    annex = next(n for n in seg.flatten() if n.kind == "annexure")
    assert annex.label == "ANNEX-I" and annex.first_block == 3
    content = (annex.heading or "") + " " + annex.text
    assert "See rule 84" in content and "Declaration of tobacco received" in content
    assert "Name of factory" in annex.text
    assert blocks == original


@pytest.mark.parametrize("text,label,bid", [
    ("[ANNEX-II\nDeclaration of tobacco received", "ANNEX-I", 3),
    ("[Appendix prose without an annex label", "ANNEX-I", 3),
    ("[ANNEX-I\nDeclaration of tobacco received", "ANNEX-I", 99),
])
def test_reviewed_bare_bracket_division_refuses_wrong_label_or_missing_id(text, label, bid):
    with pytest.raises(ValueError, match="source division opener"):
        S.segment(annex_blocks(text), detect_contents=False,
                  structural_overrides={"source_division_openers": [
                      dict(source_block_id=bid, kind="annexure", label=label)]})


def test_bare_bracket_division_with_no_review_does_not_gain_reviewed_label():
    seg = S.segment(annex_blocks(), detect_contents=False)
    assert not any(n.kind == "annexure" and n.label == "ANNEX-I" for n in seg.flatten())
