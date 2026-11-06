"""deleg_answer.py DOC QID CHOICE QUESTION NOTE : append one delegated answer to
.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json (owner chat delegation 25 Oct 2026:
the lead takes the recommended option and records it). Refuses a second answer for the same document and question."""
import hashlib, json, sys
from pathlib import Path
p = Path("/mnt/e/Nizam_e_Qanoon/.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json")
d = json.loads(p.read_text(encoding="utf-8"))
doc, qid, choice, question, note = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
assert not any(a["document_id"] == doc and a["question_id"] == qid for a in d["answers"]), "already answered"
card = {"document_id": doc, "question_id": qid, "question": question, "recommended": choice}
d["answers"].append({"document_id": doc, "question_id": qid, "card": card,
                     "card_sha256": hashlib.sha256(json.dumps(card, sort_keys=True).encode()).hexdigest(),
                     "choice": choice, "reviewed_page_images": True, "note": note})
d["answer_count"] = len(d["answers"])
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("answers:", d["answer_count"])
