"""Does a court's decision bind another court, as at a date? (DECISION-LOG D-116, docs/PRECEDENT-MODEL.md §1.4)

    authority(deciding, receiving, as_of) -> Binding | NotBinding | NotRecorded

The rules are rows of `authority_rule` (migration 0118). Each one rests on the Constitution's own words, which audit
A24 checks are still printed in a released version. This module only reads them. It never infers a hierarchy from a
court's name or class, and it never says "persuasive", which is a doctrine and not a record.

`as_of` is the research date (docs/04 §6.1): a 2005 Supreme Court judgment asked about today is read under today's
Art. 189(2). A court, date or subject with no recorded rule is NotRecorded with the reason, and a precedent answer
then abstains on bindingness (INV-2). It may still show the judgment.

The receiving court is either a court code ('LHC', 'SC') or a subordinate court in a territory:
`Subordinate('punjab')`. A subordinate court is subordinate to the High Court of its territory (Art. 203,
`court_superintendence`).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Court:
    code: str
    court_class: str
    territory: str


@dataclass(frozen=True)
class Subordinate:
    """A court subordinate to a High Court: civil, sessions, special and the like, by territory."""
    territory: str


@dataclass(frozen=True)
class Rule:
    id: int
    deciding_court: str | None
    deciding_class: str | None
    receiving: str
    except_court: str | None
    subject: str
    subject_to: tuple[str, ...]
    valid_from: dt.date | None          # inclusive; None = unbounded
    valid_to: dt.date | None            # exclusive; None = unbounded
    basis: str
    source: dict = field(default_factory=dict, compare=False)
    # D-141: the territories the rule's printed words reach ("in Pakistan": Art. 1(2)(a)-(b) and the federal courts;
    # "in Azad Jammu and Kashmir"; "in the Gilgit-Baltistan"). A court outside them is not answered by the rule.
    territories: tuple[str, ...] = ()

    def in_force(self, day: dt.date) -> bool:
        return (self.valid_from is None or self.valid_from <= day) and (self.valid_to is None or day < self.valid_to)


@dataclass(frozen=True)
class Binding:
    rule: Rule

    @property
    def subject_to(self) -> tuple[str, ...]:
        return self.rule.subject_to


@dataclass(frozen=True)
class NotBinding:
    """Rules are recorded for the deciding court on that date, and none of them reaches the receiving court."""
    rules_considered: tuple[Rule, ...]


@dataclass(frozen=True)
class NotRecorded:
    reason: str


Receiver = str | Subordinate


def authority(deciding: str, receiving: Receiver, as_of: dt.date, *, courts: dict[str, Court], rules: list[Rule],
              superintendence: dict[str, str], subject: str = "all") -> Binding | NotBinding | NotRecorded:
    """Resolve one question of binding authority from recorded rules only.

    `superintendence` maps a territory to the code of its High Court. `subject` is 'all' or the jurisdiction the
    deciding judgment was given in ('shariat_chapter_3A' for a Federal Shariat Court decision under Chapter 3A).
    """
    decider = courts.get(deciding)
    if decider is None:
        return NotRecorded(f"{deciding} is not in the court registry (its constitutional text is not held)")
    if isinstance(receiving, str):
        if receiving not in courts:
            return NotRecorded(f"{receiving} is not in the court registry")
        if receiving == deciding:
            return NotRecorded(f"whether one bench of {deciding} binds another is case law, and no such rule is "
                               "recorded yet")

    # D-141: a rule speaks only for deciding courts inside its printed reach -- Art. 201's "a High Court" is a High
    # Court of Pakistan, never the High Court of Azad Jammu and Kashmir, whose own rule is its Art. 44-B
    applicable = tuple(r for r in rules
                       if (r.deciding_court == deciding or (r.deciding_court is None
                                                            and r.deciding_class == decider.court_class))
                       and decider.territory in r.territories
                       and r.in_force(as_of) and r.subject in ("all", subject))
    if not applicable:
        return NotRecorded(f"no binding rule is recorded for {deciding} decisions on {as_of.isoformat()}"
                           + ("" if subject == "all" else f" in {subject}"))
    where = receiving.territory if isinstance(receiving, Subordinate) else courts[receiving].territory
    within = tuple(r for r in applicable if where in r.territories)
    if not within:
        # "all other courts in Pakistan" does not say whether an AJK or GB court is one (Art. 1(2)(c) is not read
        # into a record), and an AJK rule does not speak of Punjab: not recorded, never guessed either way
        reach = sorted({t for r in applicable for t in r.territories})
        return NotRecorded(f"the binding rules recorded for {deciding} reach {', '.join(reach)}; whether they reach "
                           f"a court in {where} is not recorded")
    for r in within:
        if _reaches(r, decider, receiving, courts, superintendence):
            return Binding(r)
    # "binding on all courts subordinate to it" needs to know which High Court a subordinate court answers to
    # (Art. 203); a territory with none recorded (AJK, GB: their texts print no superintendence clause) is not
    # answered by such a rule. A rule reaching "all other courts in" the territory needs no superintendence.
    if (isinstance(receiving, Subordinate) and receiving.territory not in superintendence
            and any(r.receiving == "courts_subordinate_to_deciding" for r in within)):
        return NotRecorded(f"no High Court is recorded for the territory {receiving.territory}")
    return NotBinding(within)


def _reaches(rule: Rule, decider: Court, receiving: Receiver, courts: dict[str, Court],
             superintendence: dict[str, str]) -> bool:
    if rule.receiving == "all_other_courts":
        if isinstance(receiving, Subordinate):
            return True
        return receiving != decider.code and receiving != rule.except_court
    if rule.receiving == "courts_subordinate_to_deciding":
        return isinstance(receiving, Subordinate) and superintendence.get(receiving.territory) == decider.code
    if rule.receiving == "high_courts_and_their_subordinate_courts":
        return isinstance(receiving, Subordinate) or courts[receiving].court_class == "high_court"
    return False                        # 'same_court_smaller_bench' is resolved by bench, not by court


# --------------------------------------------------------------------------------------------- loading from L2

def load(cur) -> tuple[dict[str, Court], list[Rule], dict[str, str]]:
    """The standing (unwithdrawn) courts, rules and superintendence, read once per process."""
    cur.execute("SELECT code, court_class::text, territory::text FROM court WHERE withdrawn_at IS NULL")
    courts = {c: Court(c, k, t) for c, k, t in cur.fetchall()}
    cur.execute("""SELECT id, deciding_court, deciding_class, receiving, except_court, subject, subject_to,
                          lower(validity), upper(validity), basis,
                          jsonb_build_object('source_observation_id', source_observation_id,
                                             'source_expression_ordinal', source_expression_ordinal,
                                             'source_unit', source_unit, 'source_quote', source_quote,
                                             'source_paragraph_id', source_paragraph_id),
                          territories::text[]
                     FROM authority_rule WHERE withdrawn_at IS NULL ORDER BY id""")
    rules = [Rule(i, dc, dk, rc, ex, sj, tuple(st or ()), lo, hi, b, src, tuple(tr or ()))
             for i, dc, dk, rc, ex, sj, st, lo, hi, b, src, tr in cur.fetchall()]
    cur.execute("SELECT territory::text, high_court FROM court_superintendence WHERE withdrawn_at IS NULL")
    return courts, rules, dict(cur.fetchall())
