"""receiver.py [PORT] : local endpoint the Colab browser page posts OCR results to (127.0.0.1 only).

The Colab runtime cannot reach this machine, but the Colab page open in the owner's browser can reach localhost (that
is how colab-mcp connects). A notebook cell reads each finished results.json on the runtime and has the page POST it
here: POST /result?stem=<stem> with the results.json text as the body. It is written to
E:/nizam-data/ocr/colab/output/<stem>/results.json (the layout tools/colab/import_returned.sh imports), only if it
parses as JSON keyed by that stem. GET /done lists the stems already received, so the notebook can skip them.
CORS and Chrome's private-network preflight are answered for the Colab origins only."""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

OUT = Path(r"E:\nizam-data\ocr\colab\output")
STEM = re.compile(r"\d{1,6}(?:-page\d{1,4})?")
ORIGIN = re.compile(r"https://(colab\.research\.google\.com|[a-z0-9-]+-colab\.googleusercontent\.com)")


class H(BaseHTTPRequestHandler):
    def _cors(self):
        o = self.headers.get("Origin", "")
        print(f"{self.command} {self.path[:60]} origin={o!r}", flush=True)
        # Colab renders cell outputs in sandboxed frames, whose origin is 'null'
        if ORIGIN.fullmatch(o) or o == "null":
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        if urlparse(self.path).path != "/done":
            self.send_response(404); self._cors(); self.end_headers(); return
        done = sorted(p.parent.name for p in OUT.glob("*/results.json"))
        body = json.dumps(done).encode()
        self.send_response(200); self._cors(); self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        q = parse_qs(urlparse(self.path).query)
        stem = (q.get("stem") or [""])[0]
        data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            assert urlparse(self.path).path == "/result" and STEM.fullmatch(stem)
            obj = json.loads(data.decode("utf-8"))
            assert isinstance(obj, dict) and list(obj) == [stem] and isinstance(obj[stem], list)
        except Exception as e:  # noqa: BLE001
            self.send_response(400); self._cors(); self.end_headers(); self.wfile.write(str(e).encode()); return
        d = OUT / stem; d.mkdir(parents=True, exist_ok=True)
        tmp = d / "results.json.tmp"; tmp.write_bytes(data); tmp.replace(d / "results.json")
        print(f"received {stem}: {len(obj[stem])} page(s), {len(data)} bytes", flush=True)
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"listening on 127.0.0.1:{port}, writing to {OUT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
