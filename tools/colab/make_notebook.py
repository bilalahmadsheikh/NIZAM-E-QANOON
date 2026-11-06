"""make_notebook.py : writes tools/colab/nizam_surya_colab.ipynb (run after editing the cells below).

The notebook runs the local queue's OCR engine (surya-ocr 0.22.1 + surya-2 GGUF @ 6a3a4c30 + llama.cpp b10516) on a
Colab GPU, reading tools/colab bundles from Google Drive and writing results back to Drive, resumably."""
import json
from pathlib import Path

cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s})


md("""# Nizam-e-Qanoon -- Surya OCR on a Colab GPU

Same engine as the local CPU queue (`surya-ocr 0.22.1` + `surya-2` GGUF at revision `6a3a4c30` + `llama.cpp b10516`),
built here with CUDA. Inputs and outputs live in Google Drive under `MyDrive/nizam-ocr/`, so a disconnect loses at most
the chunk in flight: **re-run all cells and it resumes**.

1. Select a Colab **GPU** runtime for this notebook; run *Colab: Mount Google Drive to Server*.
2. Put `in-1-pages.zip`, `in-2-small.zip`, `in-3-holes.zip`, `in-4-large.zip` in `MyDrive/nizam-ocr/`.
3. Run all cells. Results appear as `MyDrive/nizam-ocr/out/<stem>/results.json`; the last cell zips what is new.
4. Download the `out-*.zip` files into `E:/nizam-data/ocr/colab/returned/` -- the lead imports them.""")

code("""import os, json, re, shutil, subprocess, time, zipfile, pathlib
print(subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv'], capture_output=True, text=True).stdout)
if not pathlib.Path('/content/drive/MyDrive').exists():
    try:
        from google.colab import drive
        drive.mount('/content/drive')
    except Exception as e:
        print('Drive not mounted -- run "Colab: Mount Google Drive to Server", then re-run this cell.', e)
ROOT = pathlib.Path('/content/drive/MyDrive/nizam-ocr')
if not pathlib.Path('/content/drive/MyDrive').exists():
    ROOT = pathlib.Path('/content/nizam-ocr')
(ROOT / 'out').mkdir(parents=True, exist_ok=True)
LOG = ROOT / 'run.log'


def log(msg):
    line = time.strftime('%H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + chr(10))


print('ROOT', ROOT, sorted(p.name for p in ROOT.iterdir()))""")

code("""# 2. Surya, pinned to the local queue's version
r = subprocess.run('pip -q install "surya-ocr==0.22.1" pypdfium2', shell=True, capture_output=True, text=True)
print(r.stdout[-2000:], r.stderr[-2000:])
SURYA = shutil.which('surya_ocr')
print('surya_ocr:', SURYA)""")

code("""# 3. llama.cpp b10516 with CUDA (built once, then cached in Drive)
CACHED = ROOT / 'bin' / 'llama-server-b10516-cuda'
BIN = pathlib.Path('/content/llama-server')
if not CACHED.exists():
    cmd = ('rm -rf /content/llama.cpp && git clone -q --depth 1 --branch b10516 '
           'https://github.com/ggml-org/llama.cpp /content/llama.cpp && cd /content/llama.cpp && '
           'cmake -B build -DGGML_CUDA=ON -DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release '
           '-DCMAKE_CUDA_ARCHITECTURES="75;80;86;89" > /content/cmake.log 2>&1 && '
           'cmake --build build --target llama-server -j 8 > /content/build.log 2>&1')
    t0 = time.time()
    r = subprocess.run(cmd, shell=True)
    print('build exit', r.returncode, 'in', int(time.time() - t0), 's')
    if r.returncode:
        for f in ('/content/cmake.log', '/content/build.log'):
            if os.path.exists(f):
                print(open(f).read()[-3000:])
        raise SystemExit('llama.cpp build failed')
    CACHED.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy('/content/llama.cpp/build/bin/llama-server', CACHED)
shutil.copy(CACHED, BIN)
BIN.chmod(0o755)
print(subprocess.run([str(BIN), '--version'], capture_output=True, text=True).stderr[-400:])""")

code("""# 4. the model, pinned to the revision the local queue uses
from huggingface_hub import hf_hub_download
REV = '6a3a4c30e5e74446d4f8b6afd05b2f2da970f470'
m = hf_hub_download('datalab-to/surya-ocr-2-gguf', 'surya-2.gguf', revision=REV)
mm = hf_hub_download('datalab-to/surya-ocr-2-gguf', 'surya-2-mmproj.gguf', revision=REV)
os.environ.update(SURYA_GGUF_LOCAL_MODEL_PATH=m, SURYA_GGUF_LOCAL_MMPROJ_PATH=mm, LLAMA_CPP_BINARY=str(BIN),
                  SURYA_INFERENCE_PARALLEL=os.environ.get('SURYA_INFERENCE_PARALLEL', '4'))
print(m)
print(mm)""")

code("""# 5. unpack the input zips (folder name = priority order)
IN = pathlib.Path('/content/in')
for z in sorted(ROOT.glob('in-*.zip')):
    d = IN / z.stem[3:]
    if not d.exists():
        d.mkdir(parents=True)
        zipfile.ZipFile(z).extractall(d)
    print(d.name, len(list(d.glob('*.pdf'))), 'pdfs')""")

code("""# 6. read every PDF in 20-page chunks, results straight into Drive; anything already done is skipped
import pypdfium2
CH = 20


def run_one(pdf):
    stem = pdf.stem
    final = ROOT / 'out' / stem / 'results.json'
    if final.exists():
        return 'skip'
    n = len(pypdfium2.PdfDocument(str(pdf)))
    merged = []
    for s in range(0, n, CH):
        e = min(s + CH, n) - 1
        part = ROOT / 'chunks' / stem / f'p{s + 1}-{e + 1}'
        rj = part / stem / 'results.json'
        if not rj.exists():
            t0 = time.time()
            r = subprocess.run([SURYA, str(pdf), '--page_range', f'{s}-{e}', '--output_dir', str(part), '--keep_server'],
                               capture_output=True, text=True)
            if r.returncode or not rj.exists():
                log(f'FAIL {stem} pp{s + 1}-{e + 1}: {r.stderr[-500:]}')
                shutil.rmtree(part, ignore_errors=True)
                return 'fail'
            log(f'  {stem} pp{s + 1}-{e + 1} in {time.time() - t0:.0f}s')
        res = json.loads(rj.read_text(encoding='utf-8'))[stem]
        if [x['page'] for x in res] != list(range(1, e - s + 2)):
            log(f'FAIL {stem} pp{s + 1}-{e + 1}: page numbers {[x["page"] for x in res]}')
            return 'fail'
        for i, x in enumerate(res):
            x['page'] = s + 1 + i
            merged.append(x)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.with_name('results.json.tmp')
    tmp.write_text(json.dumps({stem: merged}, ensure_ascii=False), encoding='utf-8')
    tmp.replace(final)
    shutil.rmtree(ROOT / 'chunks' / stem, ignore_errors=True)
    return f'done {n}p'


for folder in sorted(IN.iterdir()):
    pdfs = sorted(folder.glob('*.pdf'))
    log(f'=== {folder.name}: {len(pdfs)} pdfs')
    for pdf in pdfs:
        t0 = time.time()
        st = run_one(pdf)
        if st != 'skip':
            log(f'{pdf.stem}: {st} in {time.time() - t0:.0f}s')
log('=== all folders finished')""")

code("""# 7. zip results not yet packaged -> MyDrive/nizam-ocr/out-<time>.zip (download it; safe to run any time,
#    including in a second session while cell 6 is still running in the first)
done_file = ROOT / 'packaged.txt'
done = set(done_file.read_text().split()) if done_file.exists() else set()
new = [d for d in sorted((ROOT / 'out').iterdir()) if (d / 'results.json').exists() and d.name not in done]
if new:
    z = ROOT / time.strftime('out-%Y%m%d-%H%M%S.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for d in new:
            zf.write(d / 'results.json', f'{d.name}/results.json')
    done_file.write_text(chr(10).join(sorted(done | {d.name for d in new})))
    print(z.name, len(new), 'results')
else:
    print('nothing new')""")

for c in cells:
    lines = c["source"].split("\n")
    c["source"] = [l + "\n" for l in lines[:-1]] + [lines[-1]]
nb = {"cells": cells,
      "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
Path(__file__).with_name("nizam_surya_colab.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("written")
