"""Print each golden case's hard negatives and whether operative_provision serves them at the case's as_of/territory."""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "evals/golden/golden-pk-v1-set1.draft.jsonl")
for line in path.open(encoding="utf-8"):
    r = json.loads(line)
    for u in r["retrievalGold"]["hardNegatives"]:
        print(r["caseId"], r["scope"]["territory"], "|", u["instrument"][:52], u["label"], "| served:",
              u["operativeAtAsOfInTerritory"])
