"""A tree replay may preserve a reviewed S7 decision only on exact identity."""

from nizam.storage import legal_write


class Cursor:
    def __init__(self, matches):
        self.matches = matches

    def execute(self, *_args):
        pass

    def fetchall(self):
        return self.matches


ROW = ("old-candidate", "old-adjudication", "accept_non_citable",
       "machine_evidenced", "earlier source-dependent rationale", {},
       "old-candidate-node", "old-canonical-node",
       "new-candidate-node", "new-canonical-node")


def test_ambiguous_prior_candidate_cannot_be_carried():
    assert legal_write._matching_prior_acceptance(
        Cursor([ROW, ROW]), "old-instrument", "new-candidate") is None


def test_changed_candidate_subtree_cannot_be_carried(monkeypatch):
    signatures = {"old-candidate-node": ["old law"],
                  "new-candidate-node": ["different law"],
                  "old-canonical-node": ["same"],
                  "new-canonical-node": ["same"]}
    monkeypatch.setattr(legal_write, "_subtree_revision_signature",
                        lambda _cur, root: signatures[root])
    # Rule `equivalent_candidate_subtree_carry` (stage 3) then asks whether the recut candidate is the same unit
    # holding the same law (tests/test_equivalent_s7_carry.py); here it holds different words, so nothing carries.
    root = ("x.cl_1", "clause", "1", None, None, 2, 10)
    equivalence = {"old-candidate-node": (root, [(10, "body", 50)], ["old", "law"], 50, "old", "x.cl_1"),
                   "new-candidate-node": (root, [(10, "body", 50)], ["different", "law"], 50, "new", "x.cl_1"),
                   "old-canonical-node": (root, [], [], 0, "old", "x.s_1"),
                   "new-canonical-node": (root, [], [], 0, "new", "x.s_1")}
    monkeypatch.setattr(legal_write, "_subtree_equivalence_signature",
                        lambda _cur, root_id: equivalence[root_id])
    assert legal_write._matching_prior_acceptance(
        Cursor([ROW]), "old-instrument", "new-candidate") is None


def test_exact_candidate_and_canonical_subtrees_preserve_review_basis(monkeypatch):
    signatures = {"old-candidate-node": ["same candidate"],
                  "new-candidate-node": ["same candidate"],
                  "old-canonical-node": ["same canonical"],
                  "new-canonical-node": ["same canonical"]}
    monkeypatch.setattr(legal_write, "_subtree_revision_signature",
                        lambda _cur, root: signatures[root])
    carried = legal_write._matching_prior_acceptance(
        Cursor([ROW]), "old-instrument", "new-candidate")
    assert carried["resolution"] == "accept_non_citable"
    assert carried["review_basis"] == "machine_evidenced"
