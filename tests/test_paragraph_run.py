"""Rule `reviewed_paragraph_run` (D-140): a provision that prints its own numbered paragraphs with the same
"N. Heading.-" grammar as the units around it, indented one step -- the AJK Interim Constitution 1974's Art. 4(4)
"The Rights", paragraphs 1-24 at x0 216 against the Articles' 144. Without a reading the walk files paragraph N after
Article 3 as Article N and the real Articles as clauses; with it, the run is rebuilt under its owner. Also D-140's
quoted Schedule part heading ("‘PART-A’"). Pure: synthetic blocks, no database."""
import pytest

from nizam.corpus.segment import paragraph_run_shape_ok, segment

ROWS = [  # (x0, text) -- page breaks every 12 rows
    (144, "1. Short title.- (1) This Constitution may be called the Test Interim Constitution."),
    (144, "2. Definitions.- In the Constitution, unless the context otherwise requires, words bear their meaning."),
    (144, "3. Fundamental Rights.- (1) Any law inconsistent with the rights conferred by this Article shall be void."),
    (180, "(2) No law shall be made which takes away or abridges the rights so conferred."),
    (180, "(3) The Rights"),
    (216, "1. Security of person.- No person shall be deprived of liberty save in accordance with law."),       # 6
    (216, "2. Safeguard as to arrest.- (1) No person who is arrested shall be detained without being informed."),
    (252, "(2) Every person who is arrested shall be produced before the nearest Magistrate."),
    (252, "(3) Nothing in sub-paragraphs (1) and (2) shall apply to any person,-"),
    (252, "(a) who for the time being is an enemy alien; or"),
    (252, "(b) who is arrested under any law providing for preventive detention."),
    (216, "3. Freedom of movement.- Every State Subject shall have the right to move freely throughout the State."),
    (216, "4. Freedom of trade.- Every State Subject may carry on any lawful trade or business:"),
    (250, "Provided that nothing in this paragraph shall prevent,-"),
    (250, "(a) the regulation of any trade or profession by a licensing system; or"),
    (250, "(b) the carrying on, by Government, of any trade or business."),
    (216, "5. Protection against double punishment.- No person shall,-"),
    (262, "(i) be prosecuted or punished for the same offence more than once; or"),
    (262, "(ii) when accused of an offence, be compelled to be a witness against himself."),                    # 19
    (144, "4. President.- There shall be a President, elected by the members of the Assembly."),
    (144, "5. Oath of President.- Before entering upon office, the President shall make oath before the Chief Justice."),
    (144, "6. Prime Minister.- There shall be a Prime Minister, elected by the members of the Assembly."),
]
OWNER, FIRST, LAST = 5, 6, 19
OPENERS = [6, 7, 12, 13, 17]


def _blocks(rows=ROWS):
    out = []
    for i, (x0, text) in enumerate(rows, start=1):
        page, slot = divmod(i - 1, 12)
        out.append({"id": i, "text": text, "page_no": page + 1, "y0": 90.0 + 40 * slot, "page_height": 792.0,
                    "x0": float(x0), "x1": 470.0})
    return out


def _spec(**change):
    spec = {"owner_block_id": OWNER, "owner_label": "3", "owner_kind": "subsection",
            "opener_block_ids": list(OPENERS), "run_block_ids": list(range(FIRST, LAST + 1))}
    spec.update(change)
    return spec


def _unsettled(seg):
    return [d for d in seg.repeated_label_decisions if not d.get("settled_by_review")]


def _child(node, kind, label):
    found = [c for c in node.children if c.kind == kind and c.label == label]
    assert len(found) == 1, [(c.kind, c.label) for c in node.children]
    return found[0]


def test_without_a_reading_the_paragraphs_collide_with_the_articles():
    seg = segment(_blocks())
    tops = [(c.kind, c.label) for c in seg.root.children]
    assert _unsettled(seg) or tops != [("section", str(n)) for n in range(1, 7)]


def test_the_run_is_rebuilt_under_its_owner_and_the_articles_follow_in_sequence():
    seg = segment(_blocks(), structural_overrides={"source_paragraph_runs": [_spec()]})
    assert [(c.kind, c.label) for c in seg.root.children] == [("section", str(n)) for n in range(1, 7)]
    assert not _unsettled(seg)
    rights = _child(_child(seg.root, "section", "3"), "subsection", "3")
    assert [(c.kind, c.label) for c in rights.children] == [("clause", str(n)) for n in range(1, 6)]
    one = _child(rights, "clause", "1")
    assert one.text.startswith("Security of person.- No person shall be deprived")
    two = _child(rights, "clause", "2")
    assert two.text == "Safeguard as to arrest.-"                  # its inline (1) opens the first sub-paragraph
    assert [c.label for c in two.children] == ["1", "2", "3"]
    assert [c.label for c in _child(two, "subsection", "3").children] == ["a", "b"]
    four = _child(rights, "clause", "4")
    proviso = _child(four, "proviso", "Provided")
    assert [c.label for c in proviso.children] == ["a", "b"]        # the open proviso takes its lettered items
    five = _child(rights, "clause", "5")
    assert [(c.kind, c.label) for c in five.children] == [("clause", "i"), ("clause", "ii")]   # siblings
    assert all(seg.block_roles[b][0] == "body" for b in range(FIRST, LAST + 1))
    assert _child(seg.root, "section", "4").text.startswith("President.- There shall be a President")


def test_an_opener_out_of_sequence_refuses_the_parse():
    rows = list(ROWS)
    rows[11] = (216, "7. Freedom of movement.- Every State Subject shall have the right to move freely.")   # block 12
    with pytest.raises(ValueError, match="does not print paragraph 3"):
        segment(_blocks(rows), structural_overrides={"source_paragraph_runs": [_spec()]})


def test_an_unnamed_opener_inside_the_run_refuses_the_parse():
    with pytest.raises(ValueError, match="opens a paragraph the reading does not name"):
        segment(_blocks(), structural_overrides={"source_paragraph_runs": [
            _spec(opener_block_ids=[6, 7, 12, 13])]})             # paragraph 5 (block 17) left unnamed


def test_a_wrong_owner_refuses_the_parse():
    with pytest.raises(ValueError, match="paragraph run owner"):
        segment(_blocks(), structural_overrides={"source_paragraph_runs": [_spec(owner_label="4")]})


def test_a_block_outside_the_body_refuses_the_parse():
    with pytest.raises(ValueError, match="not body text"):
        segment(_blocks(), structural_overrides={"source_paragraph_runs": [_spec(run_block_ids=list(range(6, 20)) + [99])]})


@pytest.mark.parametrize("change", [
    {"opener_block_ids": [6]},                              # one opener is not a run
    {"opener_block_ids": [6, 99]},                          # an opener outside the run
    {"run_block_ids": list(range(7, 20))},                  # the run must open on its first opener
    {"owner_kind": "clause"},
    {"run_block_ids": [5] + list(range(6, 20))},            # the owner is not part of its own run
])
def test_shape_refuses_a_malformed_reading(change):
    assert paragraph_run_shape_ok(_spec())
    assert not paragraph_run_shape_ok(_spec(**change))


def test_quoted_schedule_parts_open_inside_their_schedule():
    rows = [(144, "1. Short title.- This Act may be called the Test Act."),
            (144, "2. Definitions.- In this Act words bear their ordinary meaning."),
            (253, "1[THIRD SCHEDULE"),
            (286, "‘PART-A’"),
            (144, "1. The responsibilities of the Government under the Resolutions."),
            (144, "2. Defence and security of the State."),
            (272, "‘PART-B’"),
            (144, "1. Railways."),
            (144, "2. Mineral oil and natural gas.")]
    over = {"source_schedule_heading_blocks": [3],
            "source_printed_rule_openers": [
                {"source_block_id": 4, "label": "A", "kind": "part", "source_prefix": "‘PART-A’"},
                {"source_block_id": 7, "label": "B", "kind": "part", "source_prefix": "‘PART-B’"}]}
    seg = segment(_blocks(rows), structural_overrides=over)
    schedule = next(c for c in seg.root.children if c.kind == "schedule")
    assert [(c.kind, c.label) for c in schedule.children] == [("part", "A"), ("part", "B")]
    assert [c.label for c in schedule.children[1].children] == ["1", "2"]
    assert "’" not in (schedule.children[0].heading or "")
