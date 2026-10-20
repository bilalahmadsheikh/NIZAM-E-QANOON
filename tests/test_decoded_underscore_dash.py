"""Rule `decoded_underscore_dash` (stage 3, owner 12 Oct 2026; agent DE; docs/SEGMENTATION-PROFILES.md).

Some PDFs map the em dash glyph to '__'/'___' in the text layer, so a heading's closing dash hides sub-section (1)
('1. Short title.___(1) This Act ...'). The rule is gated PER OBSERVATION by a reviewed glyph declaration
`source_decoded_underscore_dash` = {glyph, runs_dash, runs_underscore, ink_sample} and inert without one:
  glyph 'decoded' (the page prints a dash): dash-context runs read as U+2014 in the derived text, and (1) after a
      heading-closing dash on the same line is cut;
  glyph 'typed' (the page prints underscores; owner Q2): the text keeps every underscore and only (1) is cut.
"""
import pytest

from nizam.corpus import segment as S
from nizam.workers.segment import decoded_underscore_dash_ok, reviewed_structural_overrides

KEY = "source_decoded_underscore_dash"
DECODED = {"glyph": "decoded", "runs_dash": 3, "runs_underscore": 0,
           "ink_sample": [{"page": 1, "pos": 0.6, "context": "x.[___](1)"}]}
TYPED = {"glyph": "typed", "runs_dash": 0, "runs_underscore": 3,
         "ink_sample": [{"page": 1, "pos": -0.1, "context": "x.[__] (1)"}]}


def blocks(*texts):
    return [{"id": 1000 + i, "text": t, "page_no": 1, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


BLOCKS = blocks(
    "1. Short title and commencement.___(1) This Act may be called the Test Act.\n"
    "(2) It extends to the whole of Pakistan.",
    "2. Definitions.__ In this Act, unless there is anything repugnant in the subject or context,___\n"
    "(a) \"Board\" means the Board; and\n(b) \"day\" means a day.",
    "3. Powers.__ (1) The Board may make rules. Village ___ Tracking no.___\n(2) The rules may provide for___")


def tree(overrides):
    return [(n.kind, n.label, n.heading or "", n.text or "")
            for n in S.segment(BLOCKS, structural_overrides=overrides).flatten()]


def test_inert_without_a_declaration():
    plain = tree(None)
    assert tree({}) == plain
    assert ("subsection", "1") not in [(k, label) for k, label, _h, _t in plain]
    assert plain[0][3].startswith("Short title and commencement.___(1) This Act")


def test_decoded_reads_the_dash_and_cuts_subsection_1():
    built = tree({KEY: DECODED})
    assert built[0] == ("section", "1", "", "Short title and commencement.—")
    assert built[1] == ("subsection", "1", "", "This Act may be called the Test Act.")
    assert built[3][3] == "Definitions.— In this Act, unless there is anything repugnant in the subject or context,—"
    # a run inside a form line keeps its underscores; a block-final run stays as extracted
    assert built[7] == ("subsection", "1", "", "The Board may make rules. Village ___ Tracking no.—")
    assert built[8] == ("subsection", "2", "", "The rules may provide for___")


def test_typed_keeps_every_underscore_and_only_cuts_subsection_1():
    built = tree({KEY: TYPED})
    assert built[0] == ("section", "1", "", "Short title and commencement.___")
    assert built[1] == ("subsection", "1", "", "This Act may be called the Test Act.")
    assert "—" not in "".join(text for *_rest, text in built)


@pytest.mark.parametrize("bad", [
    dict(DECODED, runs_underscore=1),                    # decoded needs no underscore ink
    dict(TYPED, runs_dash=2),                            # typed needs no dash ink
    dict(DECODED, glyph="other"),
    dict(DECODED, ink_sample=[]),
    {k: v for k, v in DECODED.items() if k != "ink_sample"},
])
def test_a_malformed_declaration_fails_closed(bad):
    assert not decoded_underscore_dash_ok(bad)
    with pytest.raises(ValueError, match="source_decoded_underscore_dash"):
        S.segment(BLOCKS, structural_overrides={KEY: bad})


def _patch(value):
    return {"evidence": {"structural_overrides": {KEY: value}}}


def test_the_worker_takes_one_declaration_per_observation():
    assert reviewed_structural_overrides([], [_patch(DECODED), _patch(dict(DECODED))])[KEY] == DECODED
    with pytest.raises(ValueError, match="conflicting"):
        reviewed_structural_overrides([], [_patch(DECODED), _patch(dict(DECODED, runs_dash=4))])
    with pytest.raises(ValueError, match="unsupported"):
        reviewed_structural_overrides([], [_patch(dict(DECODED, runs_underscore=1))])
    assert KEY not in reviewed_structural_overrides([], [])


# ---- `typed_runs` (lead 12 Oct; docs 3853, 4385): a decoded page that also prints a few REAL underscores
TYPED_RUN = {"block_id": 1000, "left": "commencement."}
DECODED_WITH_TYPED = dict(DECODED, runs_underscore=1, typed_runs=[TYPED_RUN])


def test_a_named_typed_run_keeps_its_underscores_and_still_cuts_subsection_1():
    built = tree({KEY: DECODED_WITH_TYPED})
    assert built[0] == ("section", "1", "", "Short title and commencement.___")      # printed underscores kept
    assert built[1] == ("subsection", "1", "", "This Act may be called the Test Act.")
    # every other run is decoded as before
    assert built[3][3] == "Definitions.— In this Act, unless there is anything repugnant in the subject or context,—"


def test_without_typed_runs_the_build_is_unchanged():
    assert tree({KEY: DECODED}) == tree({KEY: dict(DECODED)})
    assert tree({KEY: DECODED})[0] == ("section", "1", "", "Short title and commencement.—")


@pytest.mark.parametrize("bad", [
    dict(DECODED, typed_runs=[TYPED_RUN]),                                  # runs_underscore must count them
    dict(TYPED, typed_runs=[TYPED_RUN]),                                    # only with glyph 'decoded'
    dict(DECODED_WITH_TYPED, typed_runs=[]),
    dict(DECODED, runs_underscore=2, typed_runs=[TYPED_RUN, TYPED_RUN]),    # distinct
    dict(DECODED_WITH_TYPED, typed_runs=[{"block_id": 1000}]),
])
def test_a_malformed_typed_runs_declaration_is_refused(bad):
    assert not decoded_underscore_dash_ok(bad)


def test_a_named_run_that_is_not_found_exactly_once_fails_closed():
    missing = dict(DECODED_WITH_TYPED, typed_runs=[{"block_id": 1000, "left": "no such text"}])
    with pytest.raises(ValueError, match="typed run"):
        S.segment(BLOCKS, structural_overrides={KEY: missing})


# ---- `keep_first_subsection_blocks` (agent DE, docs 4036 4424 4463; owner 12 Oct): in named blocks the heading run
# before (1) stays as extracted and (1) is not cut (regions with a known structural defect; paths stay as released)
def test_keep_first_subsection_blocks_leaves_the_named_heading_run_and_does_not_cut():
    kept = tree({KEY: dict(DECODED, keep_first_subsection_blocks=[1000])})
    assert kept[0][0] == "section" and kept[0][3].startswith("Short title and commencement.___(1) This Act")
    assert ("subsection", "1") not in [(k, label) for k, label, _h, _t in kept[:2]]
    # every other block is decoded as usual
    assert kept[2][3].startswith("Definitions.—") or any(t.startswith("Definitions.—") for *_x, t in kept)


def test_keep_first_subsection_blocks_shape_and_fail_closed():
    assert not decoded_underscore_dash_ok(dict(DECODED, keep_first_subsection_blocks=[]))
    assert not decoded_underscore_dash_ok(dict(DECODED, keep_first_subsection_blocks=[5, 5]))
    with pytest.raises(ValueError, match="keep_first_subsection_blocks"):
        S.segment(BLOCKS, structural_overrides={KEY: dict(DECODED, keep_first_subsection_blocks=[1001])})


def test_order_suffix_label_is_data_gated_for_default_observations():
    # agent DE (docs 3500, 4225): the profile rule OR a reviewed source_order_suffix_labels spec on the observation
    assert S._order_suffix_on() is False
    import inspect
    assert 'profile_rule("order_suffix_label")' not in inspect.getsource(S._segment)
