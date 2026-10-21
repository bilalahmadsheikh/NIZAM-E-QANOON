"""Rule `equivalent_candidate_subtree_carry` (stage 3, owner 11 Oct 2026; agent DC; docs/SEGMENTATION-PROFILES.md).

An accepted S7 judgement (`accept_non_citable`) rests on the candidate row and its evidence, the label staying
citable in the canonical unit, and the two stub guards of tools/adjudicate_citation_preserving.py. An owner-approved
recut INSIDE either subtree changes none of those, so save() may carry the judgement when the candidate is the same
unit holding the same law and the canonical keeps its root without becoming a stub. Recorded append-only under a
distinct method (`carried_by_equivalent_candidate_subtree/1`), never upgrading the review basis.
"""
from nizam.storage import legal_write as LW


class Cursor:
    def __init__(self, matches):
        self.matches = matches

    def execute(self, *_args):
        pass

    def fetchall(self):
        return self.matches


ROW = ("old-candidate", "old-adjudication", "accept_non_citable", "machine_evidenced", "rationale", {},
       "oc", "ok", "nc", "nk")
ROOT_C = ("x.cl_1", "clause", "1", None, None, 2, 10)
ROOT_K = ("x.s_1", "section", "1", "Short title", None, 2, 5)


def sig(root, foot, words, chars, path, inst="new"):
    return (root, foot, words, chars, inst, path)


BASE = {"oc": sig(ROOT_C, [(10, "schedule_row", 50)], ["a"], 50, "x.cl_1", "old"),
        "nc": sig(ROOT_C, [(10, "schedule_row", 50)], ["a"], 50, "x.cl_1"),
        "ok": sig(ROOT_K, [(5, "body", 900)], ["b", "c"], 900, "x.s_1", "old"),
        "nk": sig(ROOT_K, [(5, "body", 900)], ["b", "c"], 900, "x.s_1")}
CANDIDATE_RECUT = {"oc": 1, "nc": 9, "ok": 2, "nk": 2}
CANONICAL_RECUT = {"oc": 1, "nc": 1, "ok": 2, "nk": 3}


def run(monkeypatch, exact, eq, rows=(ROW,), left=None):
    monkeypatch.setattr(LW, "_subtree_revision_signature", lambda _c, root: exact[root])
    monkeypatch.setattr(LW, "_subtree_equivalence_signature", lambda _c, root: eq[root])
    monkeypatch.setattr(LW, "_blocks_left_the_law", lambda _c, _inst, blocks: left(blocks) if left else None)
    return LW._matching_prior_acceptance(Cursor(list(rows)), "old-inst", "new-cand")


def test_exact_subtrees_carry_without_an_equivalence_key(monkeypatch):
    carried = run(monkeypatch, {"oc": 1, "nc": 1, "ok": 2, "nk": 2}, BASE)
    assert carried is not None and "equivalence" not in carried
    assert run(monkeypatch, {"oc": 1, "nc": 1, "ok": 2, "nk": 2}, BASE, rows=(ROW, ROW)) is None


def test_a_recut_canonical_with_the_same_root_carries(monkeypatch):
    """1382 s.3 / 2580 / 2703 / 4345 shape: a C1/C2 cut inside the kept section."""
    carried = run(monkeypatch, CANONICAL_RECUT, BASE)
    assert carried["equivalence"]["canonical"] == "same_root_not_stub"
    assert carried["equivalence"]["candidate"] == "exact"
    assert carried["review_basis"] == "machine_evidenced"           # no upgrade


def test_an_equivalent_candidate_carries(monkeypatch):
    assert run(monkeypatch, CANDIDATE_RECUT, BASE)["equivalence"]["candidate"] == "equivalent"


def test_a_candidate_holding_other_law_does_not_carry(monkeypatch):
    words = dict(BASE, nc=sig(ROOT_C, [(10, "schedule_row", 50)], ["a", "law"], 50, "x.cl_1"))
    grown = dict(BASE, nc=sig(ROOT_C, [(10, "schedule_row", 50), (11, "body", 40)], ["a"], 90, "x.cl_1"))
    role = dict(BASE, nc=sig(ROOT_C, [(10, "body", 50)], ["a"], 50, "x.cl_1"))      # 3305's footnote shape
    for eq in (words, grown, role):
        assert run(monkeypatch, CANDIDATE_RECUT, eq) is None


def test_blocks_that_left_the_law_may_leave_the_candidate(monkeypatch):
    """4451 shape: a running title the old candidate held is now assigned no law role."""
    eq = dict(BASE, oc=sig(ROOT_C, [(10, "schedule_row", 50), (12, "body", 15)], ["a", "the", "customs", "act"], 65,
                           "x.cl_1", "old"))
    carried = run(monkeypatch, CANDIDATE_RECUT, eq,
                  left=lambda b: {12: ["the", "customs", "act"]} if b == [12] else None)
    assert carried["equivalence"]["candidate"] == "equivalent_less_non_law_blocks"
    assert carried["equivalence"]["blocks_left_the_law"] == [12]
    assert run(monkeypatch, CANDIDATE_RECUT, eq, left=lambda b: None) is None            # still law elsewhere
    assert run(monkeypatch, CANDIDATE_RECUT, eq, left=lambda b: {12: ["the", "customs"]}) is None


def test_a_positional_suffix_renumber_carries_and_records_both_paths(monkeypatch):
    eq = dict(BASE, oc=sig(ROOT_C, [(10, "schedule_row", 50)], ["a"], 50, "x.cl_1_n92_1", "old"),
              nc=sig(ROOT_C, [(10, "schedule_row", 50)], ["a"], 50, "x.cl_1_n93_1"))
    carried = run(monkeypatch, CANDIDATE_RECUT, eq)
    assert carried["equivalence"]["paths_before"][0] == "x.cl_1_n92_1"
    assert carried["equivalence"]["paths_after"][0] == "x.cl_1_n93_1"


def test_a_changed_canonical_root_or_a_stub_does_not_carry(monkeypatch):
    heading = dict(BASE, nk=sig(("x.s_1", "section", "1", "Other heading", None, 2, 5), [(5, "body", 900)],
                                ["b", "c"], 900, "x.s_1"))
    assert run(monkeypatch, CANONICAL_RECUT, heading) is None
    stub = dict(BASE, nc=sig(ROOT_C, [(10, "schedule_row", 600)], ["a"], 600, "x.cl_1"),
                oc=sig(ROOT_C, [(10, "schedule_row", 600)], ["a"], 600, "x.cl_1", "old"),
                nk=sig(ROOT_K, [(5, "body", 200)], ["b"], 200, "x.s_1"))
    assert run(monkeypatch, CANONICAL_RECUT, stub) is None
    assert run(monkeypatch, {"oc": 1, "nc": 1, "ok": 2, "nk": 2}, stub) is not None    # exact path unchanged


def test_the_match_compares_paths_without_positional_suffixes():
    src = open(LW.__file__, encoding="utf-8").read()
    # below the three identity labels, which a reviewed identity correction rewrites (20 Oct 2026)
    assert src.count("regexp_replace(subpath(oldp.path,3)::text,'_n[0-9]+_[0-9]+','','g')") == 1
    assert src.count("regexp_replace(subpath(oldk.path,3)::text,'_n[0-9]+_[0-9]+','','g')") == 1
    assert "AND oldp.path=newp.path AND oldk.path=newk.path" not in src
