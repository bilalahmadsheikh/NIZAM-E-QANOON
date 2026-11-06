"""Record that a corpus-wide owner policy answer is applied to specific documents (lead-made, never the owner's export).

    python tools/recrawl/policy_apply.py {split|keep-both} DOC [DOC ...]
Appends per-document answers to .artifacts/decision-review/exports/policy-application-2026-10-22.json, each
citing the owner's export decision-review-2026-10-22-q22.json (document 0) q1 'split' / q2 'keep-both'. A per-document
citation is then {"export": <this file>, "document_id": DOC, "question_id": "q1"|"q2"}, which
nizam.workers.segment.owner_decision_answer accepts (exactly one answer per document and question)."""
import json, sys
from pathlib import Path
OWNER = ".artifacts/decision-review/exports/decision-review-2026-10-22-q22.json"
OUT = Path("/mnt/e/Nizam_e_Qanoon/.artifacts/decision-review/exports/policy-application-2026-10-22.json")
POLICY = {"split": ("q1", "q1"), "keep-both": ("q2", "q2")}
choice, docs = sys.argv[1], [int(x) for x in sys.argv[2:]]
owner_q, qid = POLICY[choice]
owner = json.loads((OUT.parent / Path(OWNER).name).read_text(encoding="utf-8-sig"))
ans = [a for a in owner["answers"] if a["document_id"] == 0 and a["question_id"] == owner_q]
assert len(ans) == 1 and ans[0]["choice"] == choice, "the owner export does not hold this policy answer"
d = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {
    "schema": "nizam.decision_review.policy_application.v1",
    "reviewer_name": "lead (applies the owner's corpus-wide answers; NOT an owner export)",
    "policy_export": OWNER, "policy_pack_sha256": owner.get("pack_sha256"), "answers": []}
have = {(a["document_id"], a["question_id"]) for a in d["answers"]}
for doc in docs:
    if (doc, qid) not in have:
        d["answers"].append({"document_id": doc, "question_id": qid, "choice": choice,
                             "applied_from": {"export": OWNER, "document_id": 0, "question_id": owner_q}})
OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{qid}: {len(docs)} document(s); citation export = .artifacts/decision-review/exports/{OUT.name}")
