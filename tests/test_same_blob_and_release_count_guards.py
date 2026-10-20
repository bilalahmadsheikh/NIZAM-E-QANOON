"""Two guards after doc 4419 (lead decision, 12 Oct 2026).

(a) nizam.workers.segment.same_blob_problem: observations of ONE blob must carry the same effective patch set and
    profile, checked before any build by the worker and the multi-expression materializer (fail closed).
(b) tools/released_count_guard.py: the post-replay sequence stops when a document holds more released expressions
    than at the signed baseline and no split plan or approval reason declares the rise.
"""
import json

from nizam.workers.segment import same_blob_problem
from tools.released_count_guard import newest_baseline, plan_expression_counts, undeclared_rises

A, B = "a" * 64, "b" * 64


def obs(sha, profile="default", patches=()):
    return {"sha256": sha, "profile": profile, "patches": set(patches)}


def test_same_blob_observations_with_equal_readings_pass():
    assert same_blob_problem({507: obs(A, patches={"p19", "p42"}), 132: obs(A, patches={"p19", "p42"})}) is None
    assert same_blob_problem({507: obs(A)}) is None
    # different blobs are separate documents' worth of evidence: no constraint between them here
    assert same_blob_problem({424: obs(A, patches={"x"}), 434: obs(B)}) is None


def test_a_same_blob_observation_lacking_readings_is_named():
    p = [json.dumps([19, "m", "b", "a", {}]), json.dumps([42, "m", "b", "a", {}])]
    problem = same_blob_problem({507: obs(A, patches=set(p)), 132: obs(A, patches={p[0]})})
    assert "observation 132 lacks 1 curation patch(es) on page(s) [42]" in problem
    assert "507" not in problem.split(";")[0].split("lacks")[0]


def test_a_same_blob_observation_lacking_a_toc_disposition_is_named():
    """Docs 4501 (assertion 162, s.34A omitted, on obs 434 only) and 2605 (34, 35 on obs 85 only)."""
    d = json.dumps([0, "34A", "omitted", 812345, 12])
    a = dict(obs(A), dispositions={d})
    b = dict(obs(A), dispositions=set())
    problem = same_blob_problem({434: a, 424: b})
    assert "observation 424 lacks 1 TOC disposition(s) (labels ['34A'])" in problem
    assert same_blob_problem({434: a, 424: dict(obs(A), dispositions={d})}) is None
    # a different disposition for the same row is a difference both ways
    other = json.dumps([0, "34A", "repealed", 812345, 12])
    problem = same_blob_problem({434: a, 424: dict(obs(A), dispositions={other})})
    assert "observation 424 lacks" in problem and "observation 434 lacks" in problem


def test_same_blob_observations_on_different_profiles_are_refused():
    problem = same_blob_problem({2415: obs(A, "unreleased-v4"), 2846: obs(A, "default")})
    assert "different profiles" in problem and "2415=unreleased-v4" in problem and "2846=default" in problem


def test_an_undeclared_rise_stops_the_sequence():
    before, now = {4419: 1, 31: 1}, {4419: 2, 31: 1}
    assert undeclared_rises(before, now, {}, {}) == [(4419, 1, 2)]
    # the replay's approval reason alone does not declare a rise ...
    assert undeclared_rises(before, now, {}, {4419: ["owner 12 Oct: underscore-dash fix, batch RE-a"]}) == [(4419, 1, 2)]
    # ... unless it says so
    assert undeclared_rises(before, now, {}, {4419: ["owner: split; new released expression E1"]}) == []


def test_a_split_plan_declares_its_expressions_only():
    assert undeclared_rises({4428: 1}, {4428: 2}, {4428: 2}, {}) == []
    assert undeclared_rises({4428: 1}, {4428: 3}, {4428: 2}, {}) == [(4428, 1, 3)]
    assert undeclared_rises({7: 0}, {7: 1}, {}, {}) == [(7, 0, 1)]            # a document newly released
    assert undeclared_rises({7: 2}, {7: 1}, {}, {}) == []                     # a fall is the withdrawal check's


def test_plan_counts_ignore_drafts_and_the_newest_baseline_is_found(tmp_path):
    (tmp_path / "doc-10.json").write_text(json.dumps({"document_id": 10, "expressions": [{}, {}]}))
    (tmp_path / "doc-11-DRAFT.json").write_text(json.dumps({"document_id": 11, "expressions": [{}]}))
    assert plan_expression_counts(tmp_path) == {10: 2}
    for n in (9, 53, 54):
        d = tmp_path / f"claude-baseline-{n}"
        d.mkdir()
        if n != 54:                                                         # 54 not signed yet: no files
            (d / "released.json").write_text("{}")
            (d / "manifest.json").write_text("{}")
    assert newest_baseline(tmp_path).name == "claude-baseline-53"
