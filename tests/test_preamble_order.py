"""Rule `preamble_before_empty_division` (D-067, 17 Nov 2026).

Consolidated texts print 'PART I PRELIMINARY' (the PPC: 'CHAPTER I INTRODUCTION'), then the preamble, then section 1.
Before the rule, the preamble was appended to the root after that still-empty division and section 1 joined the
division, so document order (ordinal) read sections 1..n before the preamble printed above them. The rule moves only
sibling order; paths come from labels and do not change.
"""
from nizam.corpus import segment as S


def block(bid, text, page=1, y=100):
    return dict(id=bid, text=text, page_no=page, y0=y, page_height=792, x0=70, x1=560)


PREAMBLE = ("WHEREAS it is expedient to provide for the regulation of the matters hereinafter appearing; "
            "It is hereby enacted as follows:-")


def law(opener_blocks):
    return [*opener_blocks,
            block(20, PREAMBLE, y=200),
            block(30, "1. Short title and commencement. (1) This Act may be called the Example Act. "
                      "(2) It shall come into force at once.", y=300),
            block(40, "2. Definitions. In this Act, unless there is anything repugnant in the subject or "
                      "context, the following words have the meanings given.", y=400)]


def order(seg):
    return [(n.kind, n.label) for n in seg.flatten()]


def test_preamble_printed_under_an_empty_part_heading_comes_first():
    seg = S.segment(law([block(10, "PART I \nPRELIMINARY \n", y=100)]), detect_contents=False)
    kinds = order(seg)
    assert kinds.index(("preamble", "Preamble")) < kinds.index(("part", "I"))
    part = next(n for n in seg.root.children if n.kind == "part")
    assert [c.label for c in part.children if c.kind == "section"] == ["1", "2"]


def test_preamble_printed_under_an_empty_chapter_heading_comes_first():
    seg = S.segment(law([block(10, "CHAPTER I \nINTRODUCTION \n", y=100)]), detect_contents=False)
    kinds = order(seg)
    assert kinds.index(("preamble", "Preamble")) == 0
    assert kinds.index(("section", "1")) > kinds.index(("chapter", "I"))


def test_paths_do_not_change_when_the_preamble_moves():
    seg = S.segment(law([block(10, "PART I \nPRELIMINARY \n", y=100)]), detect_contents=False)
    paths = {p for _n, p in S.assign_paths(seg, "fed.act.y2000_o1")}
    assert {"fed.act.y2000_o1.pre_Preamble", "fed.act.y2000_o1.pt_I",
            "fed.act.y2000_o1.pt_I.s_1"} <= paths


# The pass itself, on hand-built trees: what it must leave alone.

def node(kind, label, first_block, children=()):
    n = S.Node(kind=kind, label=label, depth=1, first_block=first_block)
    for c in children:
        c.parent = n
        n.children.append(c)
    return n


def root_of(*children):
    root = S.Node(kind="root", label="", depth=0)
    for c in children:
        c.parent = root
        root.children.append(c)
    return root


BLOCKS = [{"id": i} for i in range(1, 100)]


def test_a_division_holding_a_unit_read_before_the_preamble_keeps_its_place():
    root = root_of(node("part", "I", 1, [node("section", "1", 2)]), node("preamble", "Preamble", 5))
    assert S.preamble_before_empty_division(root, BLOCKS) == 0
    assert [c.kind for c in root.children] == ["part", "preamble"]


def test_a_preamble_printed_after_a_section_keeps_its_place():
    root = root_of(node("section", "1", 1), node("preamble", "Preamble", 5))
    assert S.preamble_before_empty_division(root, BLOCKS) == 0


def test_a_schedule_is_never_jumped():
    root = root_of(node("schedule", "I", 1), node("preamble", "Preamble", 5))
    assert S.preamble_before_empty_division(root, BLOCKS) == 0


def test_nested_empty_headings_are_jumped_together():
    root = root_of(node("part", "I", 1, [node("chapter", "I", 2, [node("section", "1", 9)])]),
                   node("preamble", "Preamble", 5))
    assert S.preamble_before_empty_division(root, BLOCKS) == 1
    assert [c.kind for c in root.children] == ["preamble", "part"]


def test_a_repeated_division_label_is_never_jumped():
    # two root 'Part I's: the second's path is keyed by its position (pt_I_n1_1); moving would renumber it
    root = root_of(node("part", "I", 1), node("part", "I", 2, [node("section", "1", 9)]),
                   node("preamble", "Preamble", 5))
    assert S.preamble_before_empty_division(root, BLOCKS) == 0
    assert [c.kind for c in root.children] == ["part", "part", "preamble"]


def test_the_first_of_a_repeated_label_is_jumped_and_no_path_changes():
    # doc 5195's shape: 'Part I' (empty heading), the preamble, then later 'Part I's of schedules
    def build():
        return root_of(node("part", "I", 1, [node("section", "1", 9)]), node("preamble", "Preamble", 5),
                       node("part", "I", 20, [node("section", "1", 21)]),
                       node("part", "I", 30, [node("section", "1", 31)]))

    def paths(root):
        seg = S.Segmentation(root=root, toc={}, body_starts_page=1, toc_found=False)
        return {p for _n, p in S.assign_paths(seg, "x")}

    before = paths(build())
    moved = build()
    assert S.preamble_before_empty_division(moved, BLOCKS) == 1
    assert [c.kind for c in moved.children][:2] == ["preamble", "part"]
    assert paths(moved) == before


def test_reading_position_not_block_id_decides():
    # a re-read block carries a newer id but sits earlier on the page
    blocks = [{"id": 1}, {"id": 500}, {"id": 5}, {"id": 6}]
    root = root_of(node("part", "I", 1, [node("section", "1", 500)]), node("preamble", "Preamble", 5))
    assert S.preamble_before_empty_division(root, blocks) == 0
