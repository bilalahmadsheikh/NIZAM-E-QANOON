"""Split catalogue reading into agent-sized shards (read-only for the corpus).

    shard_catalogue.py defects --pages 45     inventory.json -> shards/defects-NN.json
    shard_catalogue.py audit --pages 60       frozen audit sample -> shards/audit-NN.json

A shard keeps a document together unless the document alone exceeds the page
budget, so a reader sees every defect of an instrument side by side. Each shard
lists the page images it needs with their SHA-256; results go to
shards/<name>.result.json and are merged later.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".artifacts" / "catalogue"
SHARDS = OUT / "shards"
AUDIT = Path("/mnt/e/nizam-data/s7-audit")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def defects(budget: int) -> None:
    inventory = json.loads((OUT / "inventory.json").read_text(encoding="utf-8"))
    groups: list[list[dict]] = []
    current: list[dict] = []
    pages = 0
    for inst in inventory:
        need = {p for d in inst["defects"] for p in d["pages"]}
        if not inst["defects"]:
            continue
        if current and pages + len(need) > budget:
            groups.append(current)
            current, pages = [], 0
        if len(need) > budget:
            # A compendium alone overflows a shard: split its defects by page.
            chunk, chunk_pages = [], set()
            for d in sorted(inst["defects"], key=lambda x: min(x["pages"] or [0])):
                if chunk and len(chunk_pages | set(d["pages"])) > budget:
                    groups.append([dict(inst, defects=chunk)])
                    chunk, chunk_pages = [], set()
                chunk.append(d)
                chunk_pages |= set(d["pages"])
            if chunk:
                groups.append([dict(inst, defects=chunk)])
            continue
        current.append(inst)
        pages += len(need)
    if current:
        groups.append(current)
    SHARDS.mkdir(parents=True, exist_ok=True)
    for n, group in enumerate(groups, 1):
        name = f"defects-{n:02d}"
        total = len({(i["document_id"], p) for i in group for d in i["defects"] for p in d["pages"]})
        (SHARDS / f"{name}.json").write_text(json.dumps(
            {"shard": name, "pages": total, "instruments": group}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{name}: {len(group)} instruments, "
              f"{sum(len(i['defects']) for i in group)} defects, {total} pages")


def audit(budget: int) -> None:
    sample = json.loads(sorted(AUDIT.glob("sample-*.json"))[-1].read_text(encoding="utf-8"))
    verdicts_path = AUDIT / "verdicts.json"
    done = json.loads(verdicts_path.read_text(encoding="utf-8")) if verdicts_path.exists() else {}
    rows = [r for r in sample["rows"] if r["adjudication_id"] not in done]
    rows.sort(key=lambda r: (r["document_id"], r["source_page"] or 0))
    groups, current, seen = [], [], set()
    for r in rows:
        need = {(r["document_id"], p) for p in (r["source_page"], r["canonical_source_page"]) if p}
        if current and len(seen | need) > budget:
            groups.append(current)
            current, seen = [], set()
        current.append(r)
        seen |= need
    if current:
        groups.append(current)
    SHARDS.mkdir(parents=True, exist_ok=True)
    for n, group in enumerate(groups, 1):
        for r in group:
            r["renders"] = []
            for p in sorted({p for p in (r["source_page"], r["canonical_source_page"]) if p}):
                stem = AUDIT / f"audit-doc{r['document_id']}-p{p}"
                existing = sorted(AUDIT.glob(f"audit-doc{r['document_id']}-p{p}-*.png"))
                if not existing:
                    subprocess.run(["pdftoppm", "-f", str(p), "-l", str(p), "-r", "110", "-png",
                                    f"/mnt/e/nizam-data/{r['object_key']}", str(stem)],
                                   check=False, capture_output=True)
                    existing = sorted(AUDIT.glob(f"audit-doc{r['document_id']}-p{p}-*.png"))
                if existing:
                    r["renders"].append({"page": p, "file": str(existing[0]), "sha256": _sha(existing[0])})
        name = f"audit-{n:02d}"
        (SHARDS / f"{name}.json").write_text(json.dumps(
            {"shard": name, "rows": group}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{name}: {len(group)} rows, "
              f"{len({(r['document_id'], x['page']) for r in group for x in r['renders']})} pages")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["defects", "audit"])
    ap.add_argument("--pages", type=int, default=45)
    a = ap.parse_args()
    (defects if a.what == "defects" else audit)(a.pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
