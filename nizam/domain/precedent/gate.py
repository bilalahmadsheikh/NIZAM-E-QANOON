"""The precedent gate (S2, D-174; docs/ANSWER-COMPOSITION.md §5 stage 3 step 6): whether a precedent context is good
enough to be CITED in an answer, or only discovery.

The rule was fixed before any score existed (evals/results/precedent-gate-rule-2026-11-27.json):
  * a forum veto first: the question asks what a named forum held and that forum is not a recorded court (a tribunal,
    a family court, an ombudsman) -> COURT_NOT_HELD, nothing searched for display;
  * then, per profile (the dense space precedent search read: cpu or gpu), p = sigmoid(w . z + b) over the first
    presented judgments' features (FEATURES); pass iff p >= tau. No calibration for the profile -> abstain
    (PRECEDENT_GATE_UNCALIBRATED): an uncalibrated gate never passes anything (INV-2).
The calibration (gate_calibration.json beside this file) is written by evals/precedent_gate_fit.py on dev only.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

PRESENTED = 5                      # the judgments an answer may cite (the rule's unit)
CALIBRATION = Path(__file__).with_name("gate_calibration.json")
FEATURES = ("top", "margin", "agree", "binding_top")
GENERATORS = frozenset({"bm25", "dense", "cited", "case", "law"})      # "binding" is a vote, not a generator

# "what has the Federal Service Tribunal held", "what did the Family Court decide", "how has the Banking Court ruled"
_FORUM_NOUN = (r"(?:Tribunal|Court|Ombuds(?:man|person)|Mohtasib|Commission|Board|Authority|Controller|Council|"
               r"Bench|Adjudicator)")
# the question words in any case ("What has ..."); the forum's own name keeps its capitals, so "the court held" in
# passing is not a forum
_FORUM_ASK = re.compile(
    r"\b(?i:what|how|when|whether)\s+(?i:has|have|had|did|do|does|would)\s+(?i:the\s+)?"
    r"(?P<forum>(?:[A-Z][\w&'\-]*\s+){0,6}?" + _FORUM_NOUN +
    r"(?:\s+(?:(?:of|at|in)\s+)?[A-Z][\w\-]*(?:\s+[A-Z][\w\-]*)?)?)"
    r"\s+(?i:held|hold|decided|decide|ruled|rule|said|say|found|find|determined)\b")
_FORUM_JUDGMENTS = re.compile(
    r"\b(?i:judgments?|decisions?|rulings?|orders?|case[- ]law)\s+(?i:of|by|from)\s+(?i:the\s+)?"
    r"(?P<forum>(?:[A-Z][\w&'\-]*\s+){0,6}?" + _FORUM_NOUN + r")\b")


def forum_asked(question: str) -> str | None:
    """the forum whose decisions the question asks for, as printed, or None"""
    m = _FORUM_ASK.search(question or "") or _FORUM_JUDGMENTS.search(question or "")
    return " ".join(m.group("forum").split()) if m else None


def forum_veto(conn, question: str) -> dict | None:
    """the question asks what a forum held, and that forum is not one of the recorded courts"""
    from nizam.retrieval.precedent import courts_named
    forum = forum_asked(question)
    if not forum:
        return None
    if courts_named(conn, f"what has the {forum} held"):          # a recorded court, by its name or an alias
        return None
    return dict(forum=forum, reason="the question asks what this forum decided; its decisions are not held")


def features(items) -> dict:
    """the rule's features over the first PRESENTED items (PrecedentItem, presented order)"""
    head = list(items)[:PRESENTED]
    if not head:
        return {f: None for f in FEATURES}
    top = head[0]
    return {"top": float(top.score),
            "margin": float(top.score - head[1].score) if len(head) > 1 else 0.0,
            "agree": float(len(set(top.generators) & GENERATORS)),
            "binding_top": 1.0 if (top.authority or {}).get("status") == "binding" else 0.0}


@lru_cache(maxsize=4)
def _calibration(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"version": None, "profiles": {}}


def calibration(path: Path | None = None) -> dict:
    return _calibration(str(path or CALIBRATION))


def decide(feats: dict, profile: str, cal: dict | None = None) -> dict:
    """{"decision": pass | abstain, "code"?, "p"?, "tau"?, "profile", "calibration"}"""
    cal = cal if cal is not None else calibration()
    m = (cal.get("profiles") or {}).get(profile)
    out = {"profile": profile, "calibration": cal.get("version"), "features": feats}
    if not m:
        return {**out, "decision": "abstain", "code": "PRECEDENT_GATE_UNCALIBRATED"}
    if feats.get("top") is None:
        return {**out, "decision": "abstain", "code": "NO_PRECEDENT_FOUND"}
    z = sum(w * ((feats[f] - mu) / sd) for f, w, mu, sd in zip(m["features"], m["coef"], m["mean"], m["scale"]))
    z += m["intercept"]
    p = 1.0 / (1.0 + math.exp(-z)) if z >= -700 else 0.0
    out.update(p=round(p, 6), tau=m["tau"])
    return {**out, "decision": "pass"} if p >= m["tau"] else {**out, "decision": "abstain",
                                                              "code": "INSUFFICIENT_PRECEDENT"}
