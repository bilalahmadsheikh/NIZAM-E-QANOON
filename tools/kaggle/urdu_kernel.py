# Nizam-e-Qanoon: Urdu and Sindhi page readings on a Kaggle GPU (script kernel, pushed by tools/kaggle/kg.sh urdupush).
#
# WHY: the Sindh Code Urdu and Sindhi PDFs (data/sindh_language_scraper.py, 12 Nov 2026) carry a text layer that cannot
# be used: Jameel Noori Nastaleeq glyph clusters map to letters in scrambled order ('سندھ' -> 'دنسھ', 2018 -> '8102'),
# MB Bhitai Sattar to wrong letters. So the text must be read from the page image.
#
# Two readers, both kept (neither is trusted alone; tools/urdu/textlayer_check.py scores each page against the
# letters of the text layer, which are scrambled in ORDER but complete in CONTENT):
#   qaari  -- oddadmix/Qaari-0.1-Urdu-OCR-VL-2B-Instruct (Qwen2-VL-2B fine-tuned on synthetic Nastaleeq pages, fonts
#             incl. Jameel Noori Nastaleeq; Urdu files only), the card's own prompt;
#   qwen3  -- Qwen/Qwen3-VL-8B-Instruct (Urdu and Sindhi files), an exact-transcription prompt.
# Each page is rendered at 200 DPI and read in two crops cut at the blank row nearest the middle (as vlm3_kernel.py).
# Output: /kaggle/working/out/<file stem>/read.json {"pages": {"<n>": {"qaari": [crop texts], "qwen3": [...],
# "secs": {...}}}}, written after every page; phase 1 (qaari) runs over every Urdu file before phase 2 (qwen3).
#
# The readings are EVIDENCE, never law: nothing reaches the corpus until it has passed the text-layer check and a
# reader has checked it against the page image.
import gc, json, os, pathlib, re, subprocess, sys, time

IN = pathlib.Path("/kaggle/input"); OUT = pathlib.Path("/kaggle/working/out"); OUT.mkdir(parents=True, exist_ok=True)
LOG = pathlib.Path("/kaggle/working/run.log")
DEADLINE = time.time() + float("__HOURS__" if not "__HOURS__".startswith("__") else "11") * 3600
DPI = 200
MAXPIX = 2_000_000
QAARI = "oddadmix/Qaari-0.1-Urdu-OCR-VL-2B-Instruct"
QWEN3 = "Qwen/Qwen3-VL-8B-Instruct"


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


log("gpu probe: " + subprocess.run("nvidia-smi -L 2>&1", shell=True, capture_output=True, text=True).stdout.replace("\n", " | "))
r = subprocess.run([sys.executable, "-m", "pip", "-q", "install", "transformers>=4.57.0", "accelerate", "peft",
                    "pypdfium2", "qwen-vl-utils"], capture_output=True, text=True)
if r.returncode:
    log("pip failed: " + r.stderr[-1500:]); raise SystemExit(1)

import numpy as np
import torch
import transformers
import pypdfium2 as pdfium

QAARI_PROMPT = ("Below is the image of one page of a document, as well as some raw textual content that was previously "
                "extracted for it. Just return the plain text representation of this document as if you were reading "
                "it naturally. Do not hallucinate.")
QWEN3_PROMPT = {
    "UR": ("This is part of one page of an official printed legal text in Urdu (a Sindh Government Gazette). Transcribe "
           "it EXACTLY as printed, in Urdu script, right to left, one printed line per line. Do not translate, correct, "
           "complete or summarise anything; never add words that are not on the page. Copy every number digit by digit "
           "as printed. English words printed on the page are copied as printed. A word that cannot be read is written "
           "[illegible]."),
    "SD": ("This is part of one page of an official printed legal text in Sindhi (a Sindh Government Gazette). "
           "Transcribe it EXACTLY as printed, in Sindhi (Arabic) script with every Sindhi letter as printed (e.g. ڄ ٻ ڀ ٽ "
           "ٿ ڦ ڙ ڳ ڱ ڻ ڪ ڃ ڇ ڍ ڊ ڏ ڌ), right to left, one printed line per line. Do not translate, correct, complete or "
           "summarise anything; never add words that are not on the page. Copy every number digit by digit as printed. "
           "English words printed on the page are copied as printed. A word that cannot be read is written [illegible]."),
}


def crops(img):
    g = np.asarray(img.convert("L")); ink = g < 128; h, w = ink.shape
    rows = ink.mean(axis=1)
    cand = [y for y in range(int(h * 0.40), int(h * 0.60)) if rows[y] < 0.001]
    y = min(cand, key=lambda v: abs(v - h // 2)) if cand else h // 2
    return [img.crop((0, 0, w, y)), img.crop((0, y, w, h))]


def fit(im):
    n = im.width * im.height
    if n <= MAXPIX:
        return im
    k = (MAXPIX / n) ** 0.5
    return im.resize((int(im.width * k), int(im.height * k)))


files = sorted(IN.glob("**/*.pdf"), key=lambda p: p.stat().st_size)
lang = lambda p: "UR" if p.stem.endswith("-UR") else "SD" if p.stem.endswith("-SD") else None
files = [p for p in files if lang(p)]
log(f"{len(files)} files: {sum(lang(p) == 'UR' for p in files)} Urdu, {sum(lang(p) == 'SD' for p in files)} Sindhi")
state = {}


def page_images(p):
    doc = pdfium.PdfDocument(str(p))
    for i in range(len(doc)):
        yield i + 1, doc[i].render(scale=DPI / 72).to_pil().convert("RGB")


def save(p, n, key, texts, secs):
    dst = OUT / p.stem / "read.json"; dst.parent.mkdir(parents=True, exist_ok=True)
    res = state.setdefault(p.stem, {"dpi": DPI, "models": {"qaari": QAARI, "qwen3": QWEN3}, "pages": {}})
    pg = res["pages"].setdefault(str(n), {"secs": {}})
    pg[key] = texts; pg["secs"][key] = round(secs, 1)
    dst.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


def run(key, model, proc, reader, which):
    pages = 0
    for p in files:
        if lang(p) not in which:
            continue
        for n, img in page_images(p):
            if time.time() > DEADLINE:
                log("=== deadline reached; stopping cleanly"); return
            t1 = time.time()
            texts = []
            for c in crops(img):
                c = fit(c)
                try:
                    texts.append(reader(model, proc, c, lang(p)))
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache(); log("OOM; retrying smaller")
                    texts.append(reader(model, proc, c.resize((c.width * 3 // 4, c.height * 3 // 4)), lang(p)))
            save(p, n, key, texts, time.time() - t1); pages += 1
            log(f"{key} {p.stem} p{n} {time.time() - t1:.0f}s ({pages} pages)")
    log(f"=== {key} finished: {pages} pages")


def gen(model, proc, msgs, image, max_new=2500):
    text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = proc(text=[text], images=[image], return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False, repetition_penalty=1.05)
    return proc.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True,
                             clean_up_tokenization_spaces=False)[0]


def read_qaari(model, proc, im, lg):
    msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": QAARI_PROMPT}]}]
    return gen(model, proc, msgs, im, 2000)


def read_qwen3(model, proc, im, lg):
    msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": QWEN3_PROMPT[lg]}]}]
    return gen(model, proc, msgs, im, 2500)


# --- phase 1: Qaari on the Urdu files (T4 has no bfloat16: float16) ---
t0 = time.time()
try:
    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
    m = Qwen2VLForConditionalGeneration.from_pretrained(QAARI, torch_dtype=torch.float16, device_map="auto")
    pr = AutoProcessor.from_pretrained(QAARI)
    log(f"qaari loaded in {time.time() - t0:.0f}s (transformers {transformers.__version__})")
    run("qaari", m, pr, read_qaari, {"UR"})
    del m, pr; gc.collect(); torch.cuda.empty_cache()
except Exception as e:  # a failed reader must not cost the other one its run
    log(f"qaari phase failed: {type(e).__name__}: {str(e)[:800]}")

# --- phase 2: Qwen3-VL-8B on every file ---
t0 = time.time()
from transformers import AutoModelForImageTextToText, AutoProcessor
m = AutoModelForImageTextToText.from_pretrained(QWEN3, torch_dtype=torch.float16, device_map="auto", attn_implementation="sdpa")
pr = AutoProcessor.from_pretrained(QWEN3)
log(f"qwen3 loaded in {time.time() - t0:.0f}s")
run("qwen3", m, pr, read_qwen3, {"UR", "SD"})
log("=== all done")
