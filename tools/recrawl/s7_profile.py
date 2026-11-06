import collections, json, re
rows = [json.loads(l) for l in open("/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/s7-units.jsonl", encoding="utf-8")]
def cls(r):
    dp, kp = r["demoted_path"], r["kept_path"]
    in_div = re.search(r"\.(sch|form|app|annex|table|pt|ch)_", dp) and not re.search(r"\.(sch|form|app|annex|table)_", kp)
    dl, kl = r["demoted_len"], r["kept_len"]
    if dl >= 500 and kl < dl / 2: return "STUB: demoted carries the law (guard refuses accept)"
    if re.search(r"\.(sch|form|app|annex)_", dp): return "demoted inside a schedule/form/appendix"
    if dl < 120 and kl >= 2 * dl: return "demoted is a short line, kept carries the text"
    if kl < 60 and dl > 3 * kl: return "kept is a short line (contents-like), demoted carries the text"
    return "comparable"
if __name__ == "__main__":
  c = collections.Counter(cls(r) for r in rows)
  for k, v in c.most_common(): print(v, k)
  inst = collections.Counter(r["instrument_id"] for r in rows)
  print("instruments", len(inst), "with 1 open unit:", sum(1 for v in inst.values() if v == 1))
  print("lanes", collections.Counter(r["lane"] for r in rows))
