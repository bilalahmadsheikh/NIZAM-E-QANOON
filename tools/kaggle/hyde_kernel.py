# Kaggle GPU kernel: HyDE for the GPU statute path (D-175). For each question, Qwen3-8B (Apache-2.0; non-thinking,
# the model card's sampling: temperature 0.7, top-p 0.8, top-k 20) drafts the statutory provision that would answer
# it, in the corpus's own passage shape ("Act | Part | s. N heading" then the text). The draft is embedded with
# Qwen3-Embedding-8B at the corpus run's revision exactly as corpus passages were (document side: no instruction,
# last-token pooling, normalised, 512 tokens; tools/kaggle/embed8b_kernel.py). Pushed by `kg.sh hydepush NAME DATASET`;
# the dataset holds questions.json (texts only, no gold). Output: out/hyde.json (the drafts, questions.json order),
# out/hyde_q.npy (float32 [n, 4096]), out/run.json. The drafts are search vectors only: never shown, never cited.
import glob
import json
import os
import subprocess
import sys
import time

REV_EMB = "__REV__"
LLM = "Qwen/Qwen3-8B"
EMB = "Qwen/Qwen3-Embedding-8B"
OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "accelerate==1.6.0"], check=False)
import numpy as np  # noqa: E402
import torch  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402
from safetensors import safe_open  # noqa: E402
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer  # noqa: E402

if not REV_EMB:
    raise SystemExit("KG_REV is required: the embedding corpus run's commit")
src = os.path.dirname(sorted(glob.glob("/kaggle/input/**/questions.json", recursive=True))[0])
questions = json.load(open(f"{src}/questions.json", encoding="utf-8"))
print(f"{len(questions)} questions; GPUs: {torch.cuda.device_count()}", flush=True)

SYSTEM = ("You are drafting the text of a Pakistani statute. You never answer questions and never give advice. "
          "You write only statutory text.")
USER = ("A person asks: \"{q}\"\n\n"
        "Write the one statutory provision of Pakistani law (federal or provincial) most likely to govern this, "
        "as it would appear in the statute book. Use exactly this shape:\n"
        "<Act name and year> | <Part or Chapter, if any> | s. <number> <section heading>\n"
        "<the section's text: 2 to 4 sentences of formal statutory English>\n"
        "Write the provision only, in English, even if the question is in Urdu or Roman Urdu.")

t0 = time.time()
ltok = AutoTokenizer.from_pretrained(LLM, padding_side="left")
llm = AutoModelForCausalLM.from_pretrained(LLM, torch_dtype=torch.float16, device_map="auto").eval()
torch.manual_seed(20261127)
drafts = []
for i in range(0, len(questions), 8):
    batch = questions[i:i + 8]
    prompts = [ltok.apply_chat_template([{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": USER.format(q=" ".join(q.split()))}],
                                        tokenize=False, add_generation_prompt=True, enable_thinking=False)
               for q in batch]
    enc = ltok(prompts, return_tensors="pt", padding=True).to(llm.device)
    with torch.inference_mode():
        out = llm.generate(**enc, max_new_tokens=180, do_sample=True, temperature=0.7, top_p=0.8, top_k=20,
                           pad_token_id=ltok.pad_token_id or ltok.eos_token_id)
    for row in out[:, enc.input_ids.shape[1]:]:
        drafts.append(ltok.decode(row, skip_special_tokens=True).strip())
    print(f"  drafted {len(drafts)}/{len(questions)} ({time.time() - t0:.0f}s)", flush=True)
json.dump(drafts, open(f"{OUT}/hyde.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
del llm
torch.cuda.empty_cache()

tok = AutoTokenizer.from_pretrained(EMB, revision=REV_EMB, padding_side="left")
idx = json.load(open(hf_hub_download(EMB, "model.safetensors.index.json", revision=REV_EMB), encoding="utf-8"))
key = next(k for k in idx["weight_map"] if k.endswith("embed_tokens.weight"))
with safe_open(hf_hub_download(EMB, idx["weight_map"][key], revision=REV_EMB), "pt") as f:
    embed = torch.nn.Embedding.from_pretrained(f.get_tensor(key).to(torch.float16), freeze=True)
model = AutoModel.from_pretrained(EMB, revision=REV_EMB, torch_dtype=torch.float16,
                                  device_map={"embed_tokens": "cpu", "layers": 0, "norm": 0, "rotary_emb": 0},
                                  attn_implementation="sdpa").eval()


@torch.inference_mode()
def encode(texts):
    ids = tok(texts, truncation=True, max_length=512, padding=True, return_tensors="pt")      # document side
    x = embed(ids.input_ids).to("cuda:0")
    h = model(inputs_embeds=x, attention_mask=ids.attention_mask.to("cuda:0")).last_hidden_state
    return torch.nn.functional.normalize(h[:, -1, :].float(), dim=-1).cpu().numpy()


vec = np.concatenate([encode(drafts[i:i + 8]) for i in range(0, len(drafts), 8)])
np.save(f"{OUT}/hyde_q.npy", vec.astype(np.float32))
json.dump({"llm": LLM, "embedding": EMB, "embedding_revision": REV_EMB, "questions": len(questions),
           "sampling": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "seed": 20261127, "max_new_tokens": 180},
           "seconds": round(time.time() - t0), "gpus": torch.cuda.device_count()},
          open(f"{OUT}/run.json", "w"), indent=1)
print("done", flush=True)
