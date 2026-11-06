# Nizam-e-Qanoon: Surya OCR on a Colab GPU, driven through colab-mcp (pasted into one notebook cell by the lead).
# Same engine as the local queue: surya-ocr 0.22.1 + surya-2 GGUF @ 6a3a4c30 + llama.cpp b10516 (built here with CUDA).
# Inputs: MANIFEST (gz+b64 JSON from tools/colab/url_manifest.py) -- each item's official URL and SHA-256; the PDF is
# fetched from the portal and refused unless its SHA-256 matches the corpus record. Outputs: each results.json is
# POSTed by the browser page to the local receiver (tools/colab/receiver.py, 127.0.0.1:8765) -- nothing leaves the
# runtime otherwise. Re-running the cell resumes: stems the receiver already holds are skipped.
import base64, gzip, hashlib, json, os, shutil, subprocess, time, pathlib, urllib.request

MANIFEST = "__MANIFEST__"
PORT = 8765
ROOT = pathlib.Path("/content/nz"); (ROOT / "src").mkdir(parents=True, exist_ok=True); (ROOT / "out").mkdir(exist_ok=True)
LOG = ROOT / "run.log"


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode:
        log(f"FAILED: {cmd[:120]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
        raise SystemExit(1)
    return r.stdout


# --- 1. engine -------------------------------------------------------------------------------------------------
log(sh("nvidia-smi --query-gpu=name,memory.total --format=csv").strip())
if not shutil.which("surya_ocr"):
    sh('pip -q install "surya-ocr==0.22.1" pypdfium2')
SURYA = shutil.which("surya_ocr")
BIN = pathlib.Path("/content/llama-server")
if not BIN.exists():
    t0 = time.time()
    sh("rm -rf /content/llama.cpp && git clone -q --depth 1 --branch b10516 https://github.com/ggml-org/llama.cpp /content/llama.cpp"
       " && cd /content/llama.cpp && cmake -B build -DGGML_CUDA=ON -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF"
       ' -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES="75;80;86;89" > /content/cmake.log 2>&1'
       " && cmake --build build --target llama-server -j 8 > /content/build.log 2>&1")
    shutil.copy("/content/llama.cpp/build/bin/llama-server", BIN); BIN.chmod(0o755)
    log(f"llama.cpp b10516 CUDA built in {time.time() - t0:.0f}s")
from huggingface_hub import hf_hub_download
REV = "6a3a4c30e5e74446d4f8b6afd05b2f2da970f470"
os.environ.update(
    SURYA_GGUF_LOCAL_MODEL_PATH=hf_hub_download("datalab-to/surya-ocr-2-gguf", "surya-2.gguf", revision=REV),
    SURYA_GGUF_LOCAL_MMPROJ_PATH=hf_hub_download("datalab-to/surya-ocr-2-gguf", "surya-2-mmproj.gguf", revision=REV),
    LLAMA_CPP_BINARY=str(BIN), SURYA_INFERENCE_PARALLEL=os.environ.get("SURYA_INFERENCE_PARALLEL", "4"))
log("engine ready")

# --- 2. hand-off to this machine's receiver through the browser page -----------------------------------------
from google.colab import output


def receiver_done():
    js = f"fetch('http://127.0.0.1:{PORT}/done').then(r => r.text())"
    return set(json.loads(output.eval_js(js, timeout_sec=60)))


def send(stem, path):
    b64 = base64.b64encode(path.read_bytes()).decode()
    js = (f"fetch('http://127.0.0.1:{PORT}/result?stem={stem}', {{method: 'POST', "
          f"body: new TextDecoder().decode(Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0)))}})"
          ".then(r => r.status)")
    return output.eval_js(js, timeout_sec=120)


# --- 3. inputs: fetch from the official portal, verify SHA-256 -------------------------------------------------
import pypdfium2 as pdfium
items = json.loads(gzip.decompress(base64.b64decode(MANIFEST)))
UA = {"User-Agent": "Mozilla/5.0 (Nizam-e-Qanoon corpus re-OCR; verifies SHA-256 against the landed copy)"}


def fetch(item):
    dst = ROOT / "src" / f"{item['sha256']}.pdf"
    if dst.exists():
        return dst
    for url in item["urls"]:
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        except Exception as e:  # noqa: BLE001
            log(f"  fetch failed {item['stem']} {url[:90]}: {e}")
            continue
        if hashlib.sha256(data).hexdigest() == item["sha256"]:
            dst.write_bytes(data)
            return dst
        log(f"  sha256 mismatch {item['stem']} {url[:90]} (portal now serves a different file)")
    return None


def prepare(item):
    src = fetch(item)
    if src is None:
        return None
    if item["page"] is None:
        return src
    one = ROOT / "src" / f"{item['stem']}.pdf"
    if not one.exists():
        doc = pdfium.PdfDocument(str(src)); new = pdfium.PdfDocument.new()
        new.import_pages(doc, [item["page"] - 1])
        if item.get("rotate"):
            new[0].set_rotation((new[0].get_rotation() + 180) % 360)
        new.save(str(one))
    return one


# --- 4. read, 20-page chunks, send each finished document ------------------------------------------------------
CH = 20


def run_one(item, pdf):
    stem = item["stem"]; final = ROOT / "out" / stem / "results.json"
    if final.exists():
        return final
    work = ROOT / "work" / stem; shutil.copy(pdf, ROOT / f"{stem}.pdf")
    n = len(pdfium.PdfDocument(str(pdf))); merged = []
    for s in range(0, n, CH):
        e = min(s + CH, n) - 1; part = work / f"p{s + 1}-{e + 1}"; rj = part / stem / "results.json"
        if not rj.exists():
            r = subprocess.run([SURYA, str(ROOT / f"{stem}.pdf"), "--page_range", f"{s}-{e}", "--output_dir", str(part),
                                "--keep_server"], capture_output=True, text=True)
            if r.returncode or not rj.exists():
                log(f"FAIL {stem} pp{s + 1}-{e + 1}: {r.stderr[-400:]}"); return None
        res = json.loads(rj.read_text(encoding="utf-8"))[stem]
        if [x["page"] for x in res] != list(range(1, e - s + 2)):
            log(f"FAIL {stem} pp{s + 1}-{e + 1}: page numbers"); return None
        for i, x in enumerate(res):
            x["page"] = s + 1 + i; merged.append(x)
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_text(json.dumps({stem: merged}, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    return final


have = receiver_done()
todo = [it for it in items if it["stem"] not in have]
log(f"{len(items)} items, {len(have)} already received, {len(todo)} to do")
t_all = time.time(); done = 0
for it in todo:
    t0 = time.time(); pdf = prepare(it)
    if pdf is None:
        log(f"SKIP {it['stem']}: no verified copy fetched"); continue
    res = run_one(it, pdf)
    if res is None:
        continue
    st = send(it["stem"], res); done += 1
    log(f"{it['group']} {it['stem']}: sent ({st}) in {time.time() - t0:.0f}s -- {done}/{len(todo)}")
log(f"=== finished {done} in {(time.time() - t_all) / 60:.0f} min")
