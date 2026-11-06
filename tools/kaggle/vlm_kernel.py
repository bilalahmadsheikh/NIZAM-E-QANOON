# Nizam-e-Qanoon: page pre-read with a vision-language model on a Kaggle GPU (script kernel, pushed by
# tools/kaggle/kg.sh vlmpush). For each input PDF <doc>.pdf (dataset <user>/nizam-vlm-<suffix>), every page is rendered
# and transcribed by Qwen2.5-VL-7B-Instruct into four parts: the main text in reading order, the side (marginal) notes,
# the running heads / page numbers / sheet marks, and the footnotes. Output: /kaggle/working/out/<doc>/vlm.json
# {"model", "pages": {"<n>": {"body", "side_notes", "heads", "footnotes", "raw", "secs"}}}, written after every page so
# a run stopped by its deadline keeps what it read.
#
# The reading is EVIDENCE FOR A REVIEWER, never a source of law: tools/recrawl/vlmdraft.py turns it into a pagewrite
# transcription and marks every paragraph the page's OCR does not support, and nothing is recorded until a reader
# has checked the flagged spans against the page image (a VLM can write fluent text that is not on the page).
import json, os, pathlib, re, subprocess, sys, time

IN = pathlib.Path("/kaggle/input"); OUT = pathlib.Path("/kaggle/working/out"); OUT.mkdir(parents=True, exist_ok=True)
LOG = pathlib.Path("/kaggle/working/run.log")
MODEL = os.environ.get("NZ_VLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
DEADLINE = time.time() + float(os.environ.get("NZ_HOURS", "__HOURS__")) * 3600
DPI = int(os.environ.get("NZ_DPI", "150"))


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


log("gpu probe: " + subprocess.run("nvidia-smi -L 2>&1", shell=True, capture_output=True, text=True).stdout.replace("\n", " | "))
r = subprocess.run([sys.executable, "-m", "pip", "-q", "install", "transformers==4.51.3", "accelerate", "qwen-vl-utils",
                    "pypdfium2"], capture_output=True, text=True)
if r.returncode:
    log("pip failed: " + r.stderr[-1500:]); raise SystemExit(1)

import torch
import pypdfium2 as pdfium
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

t0 = time.time()
# T4 (sm_75) has no bfloat16: float16, the 7B model split over both GPUs (~16.6 GB of weights)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="auto",
                                                           attn_implementation="sdpa")
proc = AutoProcessor.from_pretrained(MODEL, min_pixels=256 * 28 * 28, max_pixels=int(os.environ.get("NZ_MAXPIX", str(1600 * 28 * 28))))
log(f"model {MODEL} loaded in {time.time() - t0:.0f}s")

PROMPT = (
    "This is one page of an official printed legal text (a Gazette or code of statutes). Transcribe it EXACTLY as "
    "printed. Do not correct, modernise, complete or summarise anything; never add words that are not on the page. "
    "If a word cannot be read, write [illegible]. Keep every section, sub-section and clause number exactly as printed "
    "(e.g. '12.', '(2)', '(a)'). Keep each printed paragraph as one paragraph; separate paragraphs with one blank line. "
    "Tables: one row per line, cells separated by ' | '.\n"
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


def read_page(img):
    msgs = [{"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": PROMPT}]}]
    text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = proc(text=[text], images=[img], return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=int(os.environ.get("NZ_MAXTOK", "3000")), do_sample=False,
                             repetition_penalty=1.05)
    return proc.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]


pdfs = sorted({p.stem: p for p in IN.glob("**/*.pdf")}.values(), key=lambda p: p.stat().st_size)
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
        try:
            raw = read_page(img)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache(); log(f"OOM {pdf.stem} p{i + 1}; retrying smaller")
            img = img.resize((img.width * 3 // 4, img.height * 3 // 4)); raw = read_page(img)
        res["pages"][str(i + 1)] = dict(split(raw), raw=raw, secs=round(time.time() - t1, 1))
        dst.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        pages_done += 1
        log(f"{pdf.stem} p{i + 1}/{len(doc)} {time.time() - t1:.0f}s ({pages_done} pages)")
log(f"=== finished: {pages_done} pages")
