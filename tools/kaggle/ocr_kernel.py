# Nizam-e-Qanoon: Surya OCR on a Kaggle GPU (script kernel, pushed by tools/kaggle/push.sh).
# Engine identical to the local queue: surya-ocr 0.22.1 + surya-2 GGUF @ 6a3a4c30 + llama.cpp b10516, built here with
# CUDA for the Kaggle GPUs only (P100 = sm_60, T4 = sm_75) so the build is short. Inputs: the private dataset
# <user>/nizam-ocr-inputs (in-<priority>.zip, possibly unpacked by Kaggle into folders), restricted to the groups named
# in GROUPS. Outputs: /kaggle/working/out/<stem>/results.json -- fetched by `kaggle kernels output`. Stems whose results
# already exist in an attached previous-output dataset are skipped.
import json, os, pathlib, shutil, subprocess, time, zipfile

GROUPS = os.environ.get("NZ_GROUPS", "__GROUPS__").split(",")
IN = pathlib.Path("/kaggle/input"); WORK = pathlib.Path("/kaggle/temp/nz"); OUT = pathlib.Path("/kaggle/working/out")
WORK.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
LOG = pathlib.Path("/kaggle/working/run.log")


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode:
        log(f"FAILED: {cmd[:120]}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        raise SystemExit(1)
    return r.stdout


# --- engine ---------------------------------------------------------------------------------------------------
log("gpu probe: " + subprocess.run("ls /dev/nvidia* 2>&1; nvidia-smi -L 2>&1; which nvcc 2>&1; python -c 'import torch;"
                                    "print(torch.cuda.is_available())' 2>&1", shell=True, capture_output=True,
                                    text=True).stdout.replace("\n", " | "))
if not pathlib.Path("/dev/nvidia0").exists():
    log("no GPU attached to this session (Kaggle attaches one only to a phone-verified account); stopping"); raise SystemExit(1)
sh('pip -q install "surya-ocr==0.22.1" pypdfium2')
SURYA = shutil.which("surya_ocr")
BIN = pathlib.Path("/kaggle/temp/llama-server")
t0 = time.time()
# The Kaggle image has no unversioned libcuda.so where FindCUDAToolkit looks, so CUDA::cuda_driver is not found (v5
# failed at generate); point CMake at the driver library itself: the toolkit's stub, else the installed driver.
# (v6: neither lib64/stubs nor the ldconfig cache had it -- search the toolkit's targets/ stubs and the mounted driver)
CUDA_DRV = sh("(find /usr/local/cuda* -name 'libcuda.so' -path '*stubs*' 2>/dev/null; "
              "find / -xdev \\( -name 'libcuda.so' -o -name 'libcuda.so.1' \\) 2>/dev/null) | head -1").strip()
if not CUDA_DRV:
    log("no libcuda found anywhere: " + sh("ls /usr/local/ /usr/local/cuda/lib64 2>&1 | head -40").replace("\n", " ")); raise SystemExit(1)
log(f"CUDA driver library: {CUDA_DRV}")
sh("rm -rf /kaggle/temp/llama.cpp && git clone -q --depth 1 --branch b10516 https://github.com/ggml-org/llama.cpp /kaggle/temp/llama.cpp"
   " && cd /kaggle/temp/llama.cpp && cmake -B build -DGGML_CUDA=ON -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF"
   f' -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES="60;75" -DCUDA_cuda_driver_LIBRARY={CUDA_DRV}'
   ' > /kaggle/working/cmake.log 2>&1'
   f" && cmake --build build --target llama-server -j {os.cpu_count()} > /kaggle/working/build.log 2>&1"
   " || (tail -30 /kaggle/working/cmake.log; tail -40 /kaggle/working/build.log 2>/dev/null; false)")
shutil.copy("/kaggle/temp/llama.cpp/build/bin/llama-server", BIN); BIN.chmod(0o755)
log(f"llama.cpp b10516 CUDA (sm_60, sm_75) built in {time.time() - t0:.0f}s")
from huggingface_hub import hf_hub_download
REV = "6a3a4c30e5e74446d4f8b6afd05b2f2da970f470"
os.environ.update(
    SURYA_GGUF_LOCAL_MODEL_PATH=hf_hub_download("datalab-to/surya-ocr-2-gguf", "surya-2.gguf", revision=REV),
    SURYA_GGUF_LOCAL_MMPROJ_PATH=hf_hub_download("datalab-to/surya-ocr-2-gguf", "surya-2-mmproj.gguf", revision=REV),
    LLAMA_CPP_BINARY=str(BIN), SURYA_INFERENCE_PARALLEL=os.environ.get("SURYA_INFERENCE_PARALLEL", "4"),
    # with a GPU present Surya auto-selects its vllm backend, which needs Docker (run a v8: every document failed in
    # vllm._resolve_docker_binary); the engine is llama.cpp b10516, as locally
    SURYA_INFERENCE_BACKEND="llamacpp")
log("engine ready")

# --- inputs ---------------------------------------------------------------------------------------------------
done = {p.parent.name for p in IN.glob("**/out/*/results.json")}          # an attached previous output, if any
log(f"{len(done)} stems already done in attached outputs")


def group_pdfs(g):
    """PDFs of group g, whether Kaggle kept in-<g>.zip as a file or unpacked it into a folder."""
    pdfs = []
    for z in IN.glob(f"**/in-{g}.zip"):
        if z.is_file():
            dst = WORK / "in" / g
            if not dst.exists():
                dst.mkdir(parents=True); zipfile.ZipFile(z).extractall(dst)
            pdfs += sorted(dst.glob("*.pdf"))
        elif z.is_dir():
            pdfs += sorted(z.glob("**/*.pdf"))
    for d in IN.glob(f"**/in-{g}"):
        if d.is_dir():
            pdfs += sorted(d.glob("**/*.pdf"))
    if not pdfs and len(GROUPS) == 1:
        # a dataset holding a single zip may be unpacked by Kaggle straight into the dataset's root (run c read 0
        # pdfs): with one group asked for, its pdfs are every pdf of the input datasets -- never of an attached run
        pdfs = sorted(p for p in IN.glob("**/*.pdf") if "nizam-ocr-run-" not in str(p) and "/out/" not in str(p))
    seen, out = set(), []
    for p in pdfs:
        if p.stem not in seen:
            seen.add(p.stem); out.append(p)
    return out


# --- read -----------------------------------------------------------------------------------------------------
import pypdfium2 as pdfium
CH = 20


def run_one(pdf):
    stem = pdf.stem; final = OUT / stem / "results.json"
    if final.exists() or stem in done:
        return "skip"
    n = len(pdfium.PdfDocument(str(pdf))); merged = []
    for s in range(0, n, CH):
        e = min(s + CH, n) - 1; part = WORK / "work" / stem / f"p{s + 1}-{e + 1}"; rj = part / stem / "results.json"
        if not rj.exists():
            r = subprocess.run([SURYA, str(pdf), "--page_range", f"{s}-{e}", "--output_dir", str(part), "--keep_server"],
                               capture_output=True, text=True)
            if r.returncode or not rj.exists():
                log(f"FAIL {stem} pp{s + 1}-{e + 1}: {r.stderr[-300:]}"); return "fail"
        res = json.loads(rj.read_text(encoding="utf-8"))[stem]
        if [x["page"] for x in res] != list(range(1, e - s + 2)):
            log(f"FAIL {stem} pp{s + 1}-{e + 1}: page numbers"); return "fail"
        for i, x in enumerate(res):
            x["page"] = s + 1 + i; merged.append(x)
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_text(json.dumps({stem: merged}, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(WORK / "work" / stem, ignore_errors=True)
    return f"{n}p"


t_all = time.time(); n_done = 0; pages = 0
DEADLINE = t_all + float(os.environ.get("NZ_HOURS", "__HOURS__")) * 3600   # kg.sh KG_HOURS; < Kaggle's 12 h limit
for g in GROUPS:
    pdfs = group_pdfs(g); log(f"=== {g}: {len(pdfs)} pdfs")
    for pdf in pdfs:
        if time.time() > DEADLINE:
            log("=== deadline reached; stopping cleanly"); break
        t0 = time.time(); st = run_one(pdf)
        if st not in ("skip", "fail"):
            n_done += 1; pages += int(st[:-1])
            log(f"{g} {pdf.stem}: {st} in {time.time() - t0:.0f}s ({n_done} docs, {pages} pages)")
log(f"=== finished: {n_done} docs, {pages} pages in {(time.time() - t_all) / 60:.0f} min")
