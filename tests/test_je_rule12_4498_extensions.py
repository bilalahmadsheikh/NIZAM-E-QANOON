"""Agent JE's rule12 (doc 4498 q3-q7 extensions) checks (claude/agJE/proto/agJE-t12.py), ported by builder BZ, 16 Oct 2026, onto the live modules
(group 10 port). No database."""
import re
import sys

from nizam.corpus import segment as SEG
from nizam.shared import corpus_types as T
from nizam.workers import segment as W  # noqa: F401  (JE's checks may use it)
from tools import record_curation_patch as REC  # noqa: F401
L = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-14-l.json", "document_id": 4498}
ok = 0
def check(cond, what):
    global ok
    assert cond, what
    ok += 1
def blk(i, text, p=1, y=40.0):
    return {"id": i, "text": text, "page_no": p, "x0": 72.0, "x1": 480.0, "y0": y, "page_height": 842.0}
def flat(seg):
    return [(n.kind, n.label) for n in seg.flatten()]
def secs(seg):
    return [l for k, l in flat(seg) if k == "section"]
def region(last=2, body=4):
    return {"first_block_id": 1, "last_block_id": last, "body_start_block_id": body, "rows": "sections"}

# --- q3: an opener cited as compound rule 14-1 (the copy prints '(d)')
d3 = [blk(1, "CONTENTS \n", y=10), blk(2, "13-1. Promotion \n14-1. Command and precedence \n14-2. Salutes \n", y=30),
      blk(4, "CHAPTER XIII \nPROMOTIONS \n", p=2, y=10), blk(5, "13-1. Promotion.- Promotion is by selection. \n", p=2, y=30),
      blk(6, "CHAPTER XIV \nDISCIPLINE \n", p=3, y=10),
      blk(7, "NOTE:-- Certain rules of conduct are reproduced here. \n", p=3, y=20),
      blk(8, "(d) \nCommand and precedence.- (1) Command amongst police officers shall be by rank. \n", p=3, y=40),
      blk(9, "14-2. Salutes.- Saluting is by drill. \n", p=3, y=60)]
op = {"kind": "section", "printed_label": None, "cited_label": "14-1", "source_block_id": 8,
      "source_prefix": "Command and precedence.-", "owner_decision": dict(L, question_id="q3")}
check(SEG._owner_cited_label_shape_ok(op), "opener with compound cite accepted")
# (prototype check 'today refuses' dropped at the port: the live module now IS the rule)
on3 = SEG.segment(d3, structural_overrides={"source_contents_region": region(), "source_hyphen_rule_numbers": {"chapters": [13, 14]},
                                             "source_owner_cited_labels": [op]})
check(secs(on3) == ["13-1", "14-1", "14-2"], flat(on3))
p3 = {n.label: p for n, p in SEG.assign_paths(on3, "pb") if n.kind == "section"}
check(p3["14-1"].endswith("s_14_1__pnone") and T.printed_label(p3["14-1"], "14-1") == "", p3)

# --- q5: a three-part print '23-18.1' cited 23-21 with its contents heading
d5 = [blk(1, "CONTENTS \n", y=10),
      blk(2, "23-18. Hue and cry notices \n23-19. Dissemination \n23-20. Register of absconders \n"
             "23-21. Register showing progress of action \n23-22. Register of offenders \n", y=30),
      blk(4, "CHAPTER XXIII \nPREVENTION \n", p=2, y=10),
      blk(5, "23-18. Hue and cry notices.- Notices are issued. \n", p=2, y=20),
      blk(6, "23-18. Dissemination.- Intelligence is spread. \n", p=2, y=40),
      blk(7, "23-18. Register of absconders.- A register is kept. \n", p=2, y=60),
      blk(8, "23-18.1. Register showing progress of action.- The agency keeps it. \n", p=2, y=80),
      blk(9, "23-18. Register of offenders.- A register of offenders is kept. \n", p=2, y=100)]
Q5 = dict(L, question_id="q5")
def e5(b, cited, head, printed="23-18"):
    return {"kind": "section", "printed_label": printed, "cited_label": cited, "source_block_id": b,
            "owner_decision": Q5, "contents_heading": head}
ents = [e5(6, "23-19", "Dissemination"), e5(7, "23-20", "Register of absconders"),
        e5(8, "23-21", "Register showing progress of action", printed="23-18.1"), e5(9, "23-22", "Register of offenders")]
check(all(SEG._owner_cited_label_shape_ok(x) for x in ents), "q5 shapes")
check(not SEG._owner_cited_label_shape_ok({k: v for k, v in ents[2].items() if k != "contents_heading"}),
      "a three-part print without contents_heading is refused")
on5 = SEG.segment(d5, structural_overrides={"source_contents_region": region(), "source_hyphen_rule_numbers": {"chapters": [23]},
                                             "source_owner_cited_labels": ents})
check(secs(on5) == ["23-18", "23-19", "23-20", "23-21", "23-22"], flat(on5))
p5 = {n.label: p for n, p in SEG.assign_paths(on5, "pb") if n.kind == "section"}
check(p5["23-21"].endswith("s_23_21__p23_18_1") and T.printed_label(p5["23-21"], "23-21") == "23-18.1", p5)
check(T.printed_label(p5["23-19"], "23-19") == "23-18", p5)
# without the entries the parse holds four 23-18 prints (the reason for q5)
plain5 = SEG.segment(d5, structural_overrides={"source_contents_region": region(), "source_hyphen_rule_numbers": {"chapters": [23]}})
check(("section", "23-18.1") in flat(plain5), flat(plain5))

# --- q6: contents prints the same misnumber ('23.12.  Inspection' in Chapter XXII) -> cited 22-12 with contents_label
d6 = [blk(1, "CONTENTS \n", y=10),
      blk(2, "22-11. Roll Calls \n23.12.  Inspection before duty \n22-13. Parades \n23-12. Treatment of sheets \n", y=30),
      blk(4, "CHAPTER XXII \nTHE POLICE STATION \n", p=2, y=10),
      blk(5, "22-11. Roll Calls.- A roll call is held. \n", p=2, y=20),
      blk(6, "23-12. Inspection before duty.- Officers are inspected. \n", p=2, y=40),
      blk(7, "22-13. Parades.- Parades are held. \n", p=2, y=60),
      blk(8, "CHAPTER XXIII \nPREVENTION \n", p=3, y=10),
      blk(9, "23-12. Treatment of sheets.- Sheets are treated. \n", p=3, y=30)]
Q6 = dict(L, question_id="q6")
e6 = {"kind": "section", "printed_label": "23-12", "cited_label": "22-12", "source_block_id": 6, "owner_decision": Q6,
      "contents_heading": "Inspection before duty", "contents_label": "23.12"}
check(SEG._owner_cited_label_shape_ok(e6), "q6 shape")
check(not SEG._owner_cited_label_shape_ok(dict(e6, contents_label="23.13")), "a contents label of another number is refused")
on6 = SEG.segment(d6, structural_overrides={"source_contents_region": region(), "source_hyphen_rule_numbers": {"chapters": [22, 23]},
                                             "source_owner_cited_labels": [e6]})
check(secs(on6) == ["22-11", "22-12", "22-13", "23-12"], flat(on6))
try:
    SEG.segment(d6, structural_overrides={"source_contents_region": region(), "source_hyphen_rule_numbers": {"chapters": [22, 23]},
                                           "source_owner_cited_labels": [dict(e6, contents_heading="Roll Calls")]})
    check(False, "wrong heading accepted")
except ValueError as x:
    check("no contents row" in str(x), x)
# the two-space dotted contents row opens as a row
check("23.12" in on6.toc, on6.toc)

# --- q7: bracket stubs
d7 = [blk(1, "CHAPTER III \nBUILDINGS \n", y=10),
      blk(2, "3-22. Disposal of claims.- Claims are disposed of. \n[3-23]   [Deleted by the Notifi. No. 7258/III, dated: 27.03.1983] \n"
             "3-24. Electricity.- Proposals are submitted. \n", y=30)]
on7 = SEG.segment(d7, structural_overrides={"source_hyphen_rule_numbers": {"chapters": [3]}})
s323 = next((n for n in on7.flatten() if n.label == "3-23"), None)
check(s323 is not None and "Deleted" in " ".join(s323.text_parts + [s323.heading or ""]), flat(on7))
check(secs(on7) == ["3-22", "3-23", "3-24"], flat(on7))
check(("section", "3-23") not in flat(SEG.segment(d7)), "ungated")


def test_agent_je_checks_all_ran():
    assert ok == 17, ok
