"""merge.py OUT IN1[:skipN] IN2 ... -- concatenate reading lists (a ':N' suffix drops the first N readings)"""
import json, sys
out = []
for a in sys.argv[2:]:
    p, _, k = a.partition(":")
    out += json.load(open(p, encoding="utf-8"))[int(k or 0):]
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "readings")
