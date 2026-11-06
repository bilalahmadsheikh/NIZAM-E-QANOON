# Nizam-e-Qanoon: page pre-read v3 with a vision-language model on a Kaggle GPU (script kernel, pushed by
# tools/kaggle/kg.sh vlmpush with KG_VLMK=vlm3_kernel.py). Differences from vlm_kernel.py (v1/v2, Qwen2.5-VL-7B):
#   - the model is Qwen3-VL-8B-Instruct (__MODEL__ when templated);
#   - pages render at 200 DPI and are read in two crops at near full resolution: a two-column page is cut at its
#     central gutter (left column, then right), any other page at the blank row nearest its middle (top, then
#     bottom). v2 downscaled every page to ~1.25 MP before reading: digits were swapped ('465' -> '405', doc 9722 p5)
#     and table figures lost (p7);
#   - the benchmark documents (page-verified readings exist) are read first, so a run's agreement can be measured.
# Output: /kaggle/working/out/<doc>/vlm.json {"model", "dpi", "pages": {"<n>": {"body", "side_notes", "heads",
# "footnotes", "raw", "crops", "cut", "secs"}}}, written after every page.
#
# The reading is EVIDENCE FOR A REVIEWER, never a source of law: nothing is recorded until a reader has checked it
# against the page image (a VLM can write fluent text that is not on the page -- v2 completed lost line ends).
import json, os, pathlib, re, subprocess, sys, time

IN = pathlib.Path("/kaggle/input"); OUT = pathlib.Path("/kaggle/working/out"); OUT.mkdir(parents=True, exist_ok=True)
LOG = pathlib.Path("/kaggle/working/run.log")
MODEL = "__MODEL__" if not "__MODEL__".startswith("__") else "Qwen/Qwen3-VL-8B-Instruct"
DEADLINE = time.time() + float("__HOURS__" if not "__HOURS__".startswith("__") else "11") * 3600
DPI = 200
MAXPIX = 2_000_000          # pixels per crop handed to the model
FIRST = [9722, 8935, 9533, 9168, 9540, 8962, 9164, 9181, 9524, 9572]   # page-verified benchmark documents


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


log("gpu probe: " + subprocess.run("nvidia-smi -L 2>&1", shell=True, capture_output=True, text=True).stdout.replace("\n", " | "))
r = subprocess.run([sys.executable, "-m", "pip", "-q", "install", "transformers>=4.57.0", "accelerate", "pypdfium2"],
                   capture_output=True, text=True)
if r.returncode:
    log("pip failed: " + r.stderr[-1500:]); raise SystemExit(1)

import numpy as np
import torch
import transformers
import pypdfium2 as pdfium
from transformers import AutoProcessor, AutoModelForImageTextToText

t0 = time.time()
# T4 (sm_75) has no bfloat16: float16, the model split over both GPUs
model = AutoModelForImageTextToText.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="auto",
                                                    attn_implementation="sdpa")
proc = AutoProcessor.from_pretrained(MODEL)
log(f"model {MODEL} loaded in {time.time() - t0:.0f}s (transformers {transformers.__version__})")

PROMPT = (
    "This is part of one page of an official printed legal text (a Gazette or code of statutes). Transcribe it "
    "EXACTLY as printed. Do not correct, modernise, complete or summarise anything; never add words that are not on "
    "the page. A word cut off or hidden at the edge or in the binding is written [illegible] -- never guess it. Copy "
    "every number and figure digit by digit. Keep every section, sub-section and clause number exactly as printed "
    "(e.g. '12.', '(2)', '(a)'). Keep each printed paragraph as one paragraph; separate paragraphs with one blank line. "
    "Tables: one row per line, cells separated by ' | ', every cell kept, figures included.\n"
    "Return four parts, each starting with its marker on its own line:\n"
    "### BODY\nthe main text column(s) in reading order (left column before right column), WITHOUT the marginal notes\n"
    "### SIDE NOTES\nthe short marginal notes printed beside the text, one per line, top to bottom\n"
    "### HEADS\nrunning heads, page numbers, sheet marks, imprints and signatures-blocks' outside furniture, one per line\n"
    "### FOOTNOTES\nfootnotes at the foot of the page, one per line\n")


def split(raw):
    parts = {"body": "", "side_notes": "", "heads": "", "footnotes": ""}
    key = None
    for line in raw.splitlines():
        m = re.match(r"\s*#+\s*(BODY|SIDE NOTES|HEADS|FOOTNOTES)\s*$", line, re.I)
        if m:
            key = m.group(1).lower().replace(" ", "_"); continue
        if key:
            parts[key] += line + "\n"
    return {k: v.strip() for k, v in parts.items()}


def crops(img):
    """Two crops: at a central gutter that is blank the whole height of the text (two columns), else at the blank
    row nearest the middle."""
    g = np.asarray(img.convert("L"))
    ink = g < 128
    h, w = ink.shape
    y0, y1 = int(h * 0.12), int(h * 0.92)          # skip the running head and the foot
    cols = ink[y0:y1].mean(axis=0)
    band = range(int(w * 0.38), int(w * 0.62))
    gut = [x for x in band if cols[x] < 0.002]
    if len(gut) >= max(6, w // 150):
        x = gut[len(gut) // 2]
        return "columns", [img.crop((0, 0, x, h)), img.crop((x, 0, w, h))]
    rows = ink.mean(axis=1)
    cand = [y for y in range(int(h * 0.40), int(h * 0.60)) if rows[y] < 0.001]
    y = min(cand, key=lambda v: abs(v - h // 2)) if cand else h // 2
    return "rows", [img.crop((0, 0, w, y)), img.crop((0, y, w, h))]


def fit(im):
    n = im.width * im.height
    if n <= MAXPIX:
        return im
    k = (MAXPIX / n) ** 0.5
    return im.resize((int(im.width * k), int(im.height * k)))


def read(im):
    msgs = [{"role": "user", "content": [{"type": "image", "image": im}, {"type": "text", "text": PROMPT}]}]
    inputs = proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True,
                                      return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=2500, do_sample=False, repetition_penalty=1.05)
    return proc.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]


def read_safe(im):
    im = fit(im)
    try:
        return read(im)
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache(); log("OOM; retrying smaller")
        return read(im.resize((im.width * 3 // 4, im.height * 3 // 4)))


pdfs = sorted({p.stem: p for p in IN.glob("**/*.pdf")}.values(),
              key=lambda p: (int(p.stem) not in FIRST, FIRST.index(int(p.stem)) if int(p.stem) in FIRST else 0,
                             p.stat().st_size))
done = {p.parent.name for p in IN.glob("**/out/*/vlm.json")}
log(f"{len(pdfs)} pdfs, {len(done)} already read in attached outputs")
pages_done = 0
for pdf in pdfs:
    if pdf.stem in done:
        continue
    dst = OUT / pdf.stem / "vlm.json"; dst.parent.mkdir(parents=True, exist_ok=True)
    res = {"model": MODEL, "dpi": DPI, "pages": {}}
    doc = pdfium.PdfDocument(str(pdf))
    for i in range(len(doc)):
        if time.time() > DEADLINE:
            log("=== deadline reached; stopping cleanly"); raise SystemExit(0)
        t1 = time.time()
        img = doc[i].render(scale=DPI / 72).to_pil().convert("RGB")
        how, parts = crops(img)
        raws = [read_safe(c) for c in parts]
        sp = [split(x) for x in raws]
        page = {k: "\n".join(s[k] for s in sp if s[k]) for k in ("body", "side_notes", "heads", "footnotes")}
        res["pages"][str(i + 1)] = dict(page, raw="\n\n=== CROP ===\n\n".join(raws), crops=sp, cut=how,
                                        secs=round(time.time() - t1, 1))
        dst.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        pages_done += 1
        log(f"{pdf.stem} p{i + 1}/{len(doc)} {how} {time.time() - t1:.0f}s ({pages_done} pages)")
log(f"=== finished: {pages_done} pages")
