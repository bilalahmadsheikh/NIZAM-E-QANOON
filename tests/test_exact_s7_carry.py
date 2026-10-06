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
