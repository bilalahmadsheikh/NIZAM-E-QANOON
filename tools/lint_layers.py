"""lint_layers.py : run the import-linter layer contracts (.importlinter) over the modules that exist today.

The contracts name every layer docs/01 §6 defines. Until L4 and L5 are built, nizam.generation and nizam.domain do
not exist and import-linter refuses a contract that names a missing module. This wrapper copies .importlinter,
removes each line naming a nizam module that is not in the tree (a layer, a source, a forbidden module, an
exemption), and runs lint-imports on the copy -- so the check is honest about today's code and tightens on its own
the day a layer appears. The removed names are printed, never hidden.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def exists(module: str) -> bool:
    p = ROOT / Path(*module.split("."))
    return p.is_dir() or p.with_suffix(".py").is_file()


def main() -> int:
    kept, dropped = [], set()
    for line in (ROOT / ".importlinter").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s+\(?(nizam(?:\.[a-z_]+)+)", line)
        if m:
            mod = m.group(1)
            # an exemption names a pattern (nizam.generation.providers.*): test its fixed package prefix
            if not exists(mod.removesuffix(".*") if "*" not in mod else mod.split(".*")[0]):
                dropped.add(mod)
                continue
        kept.append(line)
    if dropped:
        print("not built yet, left out of this run:", ", ".join(sorted(dropped)))
    with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False, encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")
    exe = Path(sys.executable).with_name("lint-imports")
    return subprocess.run([str(exe), "--config", f.name], cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
