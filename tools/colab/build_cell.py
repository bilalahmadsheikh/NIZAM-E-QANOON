"""build_cell.py MANIFEST.json OUT.py : agent_run.py with the URL manifest embedded (gz+b64), ready to paste into one
Colab cell."""
import base64, gzip, sys
from pathlib import Path
src = Path(__file__).with_name("agent_run.py").read_text(encoding="utf-8")
b64 = base64.b64encode(gzip.compress(Path(sys.argv[1]).read_bytes(), 9)).decode()
Path(sys.argv[2]).write_text(src.replace('"__MANIFEST__"', repr(b64)), encoding="utf-8", newline="\n")
compile(Path(sys.argv[2]).read_text(encoding="utf-8"), "cell", "exec")
print(sys.argv[2], len(b64), "manifest chars")
