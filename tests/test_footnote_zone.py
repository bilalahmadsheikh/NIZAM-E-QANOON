"""tools/recrawl/footnote_zone.py: page footnotes are found below the printed rule, never law text (15 Nov 2026)."""
import importlib.util
from pathlib import Path

import pymupdf

spec = importlib.util.spec_from_file_location(
    "footnote_zone", Path(__file__).resolve().parents[1] / "tools" / "recrawl" / "footnote_zone.py")
fz = importlib.util.module_from_spec(spec); spec.loader.exec_module(fz)


def page_with(rule_y=None, underline_y=None):
    """A 612x792 page: law at 12pt, a heading underline and/or a footnote rule, a 9pt note under the rule."""
    doc = pymupdf.open(); page = doc.new_page(width=612, height=792)
    page.insert_text((140, 300), "6. Powers and functions of the Foundation.- (1) The Foundation shall", fontsize=12)
    page.insert_text((140, 330), "(a) to provide low cost accommodation to the Members;", fontsize=12)
    if underline_y:
        page.draw_line((140, underline_y), (330, underline_y))
    if rule_y:
        page.draw_line((140, rule_y), (290, rule_y))
        page.insert_text((140, rule_y + 20), "1 Sec. 6 subs. by the AJ&K Press Foundation (Amdt.) Act, 2018.", fontsize=9)
        page.insert_text((150, rule_y + 40), "(a) to provide low cost accommodation to the members;", fontsize=9)
    return doc, page


def test_a_footnote_rule_is_found_and_a_short_stroke_high_on_the_page_is_not():
    _, page = page_with(rule_y=600)
    assert [round(y) for y in fz.rules_on(page)] == [600]
    _, top = page_with(underline_y=150)                # above the top quarter: never a footnote rule
    assert fz.rules_on(top) == []


def test_a_ruled_table_is_not_a_footnote_zone():
    """doc 10912 pp5-11: a schedule in small type, ruled; its horizontal lines are not footnote rules."""
    doc = pymupdf.open(); page = doc.new_page(width=612, height=792)
    page.draw_line((143, 499), (469, 499)); page.draw_line((143, 520), (469, 520))
    for x in (143, 171, 346, 469):
        page.draw_line((x, 499), (x, 520))
    page.insert_text((150, 512), "6 Services provided by property developers 9818.1000", fontsize=9)
    assert fz.rules_on(page) == []


def test_block_size_reads_the_spans_inside_the_block():
    _, page = page_with(rule_y=600)
    spans = fz.span_sizes(page)
    assert fz.block_size(spans, 135, 285, 600, 305) == 12.0
    assert fz.block_size(spans, 135, 605, 600, 625) == 9.0


def test_a_block_fusing_a_law_line_with_the_note_is_not_small():
    """doc 11262 p2: one extracted block holds the law's last 12pt line and the 9pt note below the rule."""
    _, page = page_with(rule_y=320)                    # the rule falls between the two law lines' 12pt text and the note
    spans = fz.span_sizes(page)
    fused = (135, 318, 600, 365)                       # '(a) to provide ...' at 12pt plus the 9pt note lines
    assert fz.block_size(spans, *fused) == 9.0         # most characters are the note's ...
    assert fz.block_size(spans, *fused, largest=True) == 12.0   # ... but a law-sized span is inside: never set aside


def blk(i, y0, y1, text):
    return (i, 1, y0, y1, text, "body")


LAW = [blk(1, 288, 302, "6. Powers and functions of the Foundation.- (1) The Foundation shall"),
       blk(2, 318, 332, "(a) to provide low cost accommodation to the Members;")]
NOTE = [blk(3, 608, 622, "1 Sec. 6 subs. by the AJ&K Press Foundation (Amdt.) Act, 2018."),
        blk(4, 628, 642, "(a) to provide low cost accommodation to the members;"),
        blk(5, 760, 772, "567")]


def test_the_zone_is_the_small_text_below_the_rule_and_never_the_folio():
    rule, zone, opens = fz.page_zone(LAW + NOTE, [600.0], {3, 4, 5}, False)
    assert rule == 600.0 and opens and [b[0] for b in zone] == [3, 4]


def test_an_underline_followed_by_law_sized_text_is_not_a_footnote_rule():
    rule, zone, opens = fz.page_zone(LAW, [310.0], set(), False)          # nothing small below it
    assert rule is None and zone == [] and not opens


def test_small_text_under_a_rule_needs_a_note_marker_or_a_continued_zone():
    table = [blk(6, 608, 622, "District Seats Poonch 10 Kotli 5"), blk(7, 628, 642, "Muzaffarabad 6 Mirpur 7")]
    assert fz.page_zone(LAW + table, [600.0], {6, 7}, False)[1] == []
    assert [b[0] for b in fz.page_zone(LAW + table, [600.0], {6, 7}, True)[1]] == [6, 7]   # a note run on


def test_the_rule_is_the_highest_stroke_with_only_notes_below_it():
    """doc 10092 p6: strokes at 263 (heading underline in the law), 446 (the footnote rule), 505 (an underline inside
    the reproduced original); the note opening '1 Sec. 6 subs. by' between 446 and 505 belongs to the zone."""
    law = [blk(1, 250, 260, "6. Powers and functions"), blk(2, 270, 430, "(1) The Foundation shall ...")]
    notes = [blk(3, 458, 489, "1 Sec. 6 subs. by the AJ&K Press Foundation (Amdt.) Act, 2018."),
             blk(4, 495, 503, "“6. Aims and Objectives of the Foundation:"), blk(5, 510, 530, "(a) to provide ...")]
    rule, zone, _ = fz.page_zone(law + notes, [263.0, 446.0, 505.0], {3, 4, 5}, False)
    assert rule == 446.0 and [b[0] for b in zone] == [3, 4, 5]


def test_a_block_straddling_the_rule_neither_blocks_the_zone_nor_joins_it():
    """doc 9958 p2: a 12pt law block runs past the rule (fused with the note under it)."""
    straddle = [blk(1, 300, 470, "3[“(3) Fund.- (1) There shall be established a fund ...")]
    notes = [blk(2, 480, 500, "1 The word “Welfare” omitted by Ibid.")]
    rule, zone, opens = fz.page_zone(straddle + notes, [428.0], {2}, False)
    assert rule == 428.0 and opens and [b[0] for b in zone] == [2]


def test_a_one_line_note_whose_marker_lifts_it_above_the_rule_is_below_it():
    lifted = [blk(8, 630, 642, "1 Ins. by the Removal from Service (Special Powers) (Amdt.) Act, 2002")]
    assert [b[0] for b in fz.page_zone(LAW + lifted, [638.0], {8}, False)[1]] == [8]
