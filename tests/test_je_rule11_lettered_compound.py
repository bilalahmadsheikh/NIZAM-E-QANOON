"""Agent JE's rule11 `owner_cited_lettered_compound_label` checks (claude/agJE/proto/agJE-t11.py), ported by builder BZ, 16 Oct 2026, onto the live modules
(group 10 port). No database."""
import re
import sys

from nizam.corpus import segment as SEG
from nizam.shared import corpus_types as T
from nizam.workers import segment as W  # noqa: F401  (JE's checks may use it)
from tools import record_curation_patch as REC  # noqa: F401
OD = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 4498, "question_id": "q2"}
ok = 0
def check(cond, what):
    global ok
    assert cond, what
    ok += 1
def blk(i, text, p=1, y=40.0):
    return {"id": i, "text": text, "page_no": p, "x0": 72.0, "x1": 480.0, "y0": y, "page_height": 842.0}
def flat(seg):
    return [(n.kind, n.label) for n in seg.flatten()]
def e(printed, cited, block, **kw):
    return dict({"kind": "section", "printed_label": printed, "cited_label": cited, "source_block_id": block,
                 "owner_decision": OD}, **kw)
BASE = {"source_contents_region": {"first_block_id": 1, "last_block_id": 2, "body_start_block_id": 4, "rows": "sections"},
        "source_hyphen_rule_numbers": {"chapters": [11, 21]}}
# --- shape
for good in (e("21-25", "21-25-A", 5), e("11-71A", "11-72-A", 5), e("11-71.B", "11-72-B", 5), e("27-14", "27-9", 5)):
    check(SEG._owner_cited_label_shape_ok(good), f"accept {good}")
for bad in (e("21-25", "21-25-AB", 5), e("21-25", "21-25a", 5), e("21-25", "21.25-A", 5), e("21-25A", "21-25A", 5),
            e("21-25", "22-25-A", 5)):
    check(not SEG._owner_cited_label_shape_ok(bad), f"refuse {bad}")
# --- 21-25 printed twice; the second is contents' 21-25.A
doc21 = [blk(1, "CONTENTS \n", y=10),
         blk(2, "21-24. Gazette \n21-25. Appointment to the Department \n21-25.A. Discipline in the Department \n21-26. Duties \n", y=30),
         blk(4, "CHAPTER XXI \nCRIMINAL INVESTIGATION \n", p=2, y=10),
         blk(5, "21-24. Gazette.- The gazette is published weekly. \n21-25. Appointment to the Department.- Officers are selected. \n", p=2, y=30),
         blk(6, "21-25. Discipline in the Department.- The Deputy Inspector-General controls discipline. \n", p=2, y=60),
         blk(7, "21-26. Duties.- The Department assists the districts. \n", p=2, y=90)]
on = SEG.segment(doc21, structural_overrides=dict(BASE, source_owner_cited_labels=[e("21-25", "21-25-A", 6)]))
secs = [l for k, l in flat(on) if k == "section"]
check(secs == ["21-24", "21-25", "21-25-A", "21-26"], secs)
paths = {n.label: p for n, p in SEG.assign_paths(on, "pb.rules") if n.kind == "section"}
check(paths["21-25-A"].endswith("__p21_25"), paths)
check(T.printed_label(paths["21-25-A"], "21-25-A") == "21-25", T.printed_label(paths["21-25-A"], "21-25-A"))
# --- the lettered run opens right after 11-71: prints 11-71A, 11-71B are contents' 11-72.A, 11-72.B
doc11 = [blk(1, "CONTENTS \n", y=10),
         blk(2, "11-71. Honoraria \n11-72.A. Compensatory allowance \n11-72.B. Leave allowance \n11-73. Exemption \n", y=30),
         blk(4, "CHAPTER XI \nALLOWANCES \n", p=2, y=10),
         blk(5, "11-71. Honoraria.- No officer may accept a fee. \n", p=2, y=30),
         blk(6, "11-71A.Compensatory allowance.- Allowances are granted. \n", p=2, y=50),
         blk(7, "11-71B. Leave allowance.- During leave the allowance is drawn. \n", p=2, y=70),
         blk(8, "11-73. Exemption.- Officers are exempted. \n", p=2, y=90)]
ents = [e("11-71A", "11-72-A", 6), e("11-71B", "11-72-B", 7)]
on11 = SEG.segment(doc11, structural_overrides=dict(BASE, source_owner_cited_labels=ents))
secs = [l for k, l in flat(on11) if k == "section"]
check(secs == ["11-71", "11-72-A", "11-72-B", "11-73"], secs)
p11 = {n.label: p for n, p in SEG.assign_paths(on11, "pb.rules") if n.kind == "section"}
check(p11["11-72-A"].endswith("__p11_71A") and T.printed_label(p11["11-72-A"], "11-72-A") == "11-71A", p11)
check(T.printed_label("x.s_11_72_A__p11_71_A", "11-72-A") == "11-71-A", "hyphen-letter marker")
check(T.printed_label("x.s_1_132__p1_32", "1.132") == "1.32", "plain compound reader unchanged")
# --- out of sequence: B cited straight after 11-71 (no A)
try:
    SEG.segment(doc11, structural_overrides=dict(BASE, source_owner_cited_labels=[e("11-71A", "11-72-B", 6)]))
    check(False, "B after 11-71 accepted")
except ValueError as x:
    check("out of sequence" in str(x), x)
# --- recorder page check: a lettered print is found in its block
check(REC.owner_cited_block_problem(e("11-71A", "11-72-A", 6), {6: "11-71A.Compensatory allowance.-"}) is None, "recorder")
check(REC.owner_cited_block_problem(e("11-71A", "11-72-A", 6), {6: "11-71.Compensatory"}) is not None, "recorder refuses")


def test_agent_je_checks_all_ran():
    assert ok == 19, ok
