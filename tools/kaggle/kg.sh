#!/bin/bash
# kg.sh whoami
# kg.sh dataset SUFFIX ZIP...    : create (or version) private dataset <user>/nizam-ocr-SUFFIX holding those input zips
#                                  (zips from E:/nizam-data/ocr/colab, moved into E:/nizam-data/ocr/kaggle/ds-SUFFIX)
# kg.sh push NAME GROUPS DS...   : push GPU script kernel <user>/nizam-ocr-NAME reading GROUPS (e.g. 1-pages,2-small)
#                                  from datasets DS (suffixes)
# kg.sh status NAME              : kernel status
# kg.sh fetch NAME               : download the kernel's output, copy new results into E:/nizam-data/ocr/colab/output
# Credentials: C:\Users\bilaa\.kaggle\access_token (owner's Kaggle API token). Kernel code: tools/kaggle/ocr_kernel.py.
set -euo pipefail
# kg.sh embeddata|embedpush|embedstatus|embedlogs|embedfetch : the embedding run (D-098, tools/kaggle/embed_kernel.py)
# kg.sh exportpush|exportstatus|exportfetch : the int8 ONNX query encoder (D-098, tools/kaggle/export_kernel.py)
# kg.sh rrpush|rrstatus|rrfetch : the reranker bake-off (D-101, tools/kaggle/rerank_kernel.py)
# KG_ACCOUNT=2 : the second account (darashikohbodla, token in C:/Users/bilaa/.kaggle2) -- its own weekly GPU quota
export KAGGLE_CONFIG_DIR=/mnt/c/Users/bilaa/.kaggle${KG_ACCOUNT:-}
[ "${KG_ACCOUNT:-}" = 2 ] && export KAGGLE_USERNAME=darashikohbodla
export KAGGLE_API_TOKEN=$(cat $KAGGLE_CONFIG_DIR/access_token)
KG=/mnt/e/nizam-data/kaggle-venv/bin/kaggle
ROOT=/mnt/e/nizam-data/ocr/kaggle; mkdir -p $ROOT
USER=${KAGGLE_USERNAME:-$($KG config view 2>/dev/null | awk -F': ' '/username/{print $2}' | tr -d ' ')}
case "$1" in
whoami)
  $KG config view; echo "user=$USER" ;;
dataset)
  S=$2; shift 2; DS=$ROOT/ds-$S; mkdir -p $DS
  for z in "$@"; do [ -f /mnt/e/nizam-data/ocr/colab/$z ] && mv /mnt/e/nizam-data/ocr/colab/$z $DS/; [ -f $DS/$z ] || { echo "missing $z"; exit 1; }; done
  cat > $DS/dataset-metadata.json <<EOF
{"title": "nizam-ocr-$S", "id": "$USER/nizam-ocr-$S", "licenses": [{"name": "other"}]}
EOF
  ls -la $DS
  if $KG datasets status $USER/nizam-ocr-$S >/dev/null 2>&1; then
    $KG datasets version -p $DS -m "inputs $(date -u +%F)" -r skip
  else
    $KG datasets create -p $DS -r skip
  fi ;;
push)
  K=$ROOT/kernel-$2; mkdir -p $K; G=$3; shift 3
  SRC=$(printf '"%s/nizam-ocr-%s",' $(for s in "$@"; do echo $USER $s; done) | sed 's/,$//')
  # KG_HOURS: stop cleanly after this many hours so results come back in batches (output is only fetchable once a run
  # ends); KG_KSRC: earlier runs (names) whose outputs are attached, so their stems are skipped
  KG_KSRC=${KG_KSRC:-}
  KSRC=$(for k in ${KG_KSRC//,/ }; do printf '"%s/nizam-ocr-run-%s",' $USER $k; done | sed 's/,$//')
  sed "s/__GROUPS__/$G/; s/__HOURS__/${KG_HOURS:-11}/" /mnt/e/Nizam_e_Qanoon/tools/kaggle/ocr_kernel.py > $K/ocr_kernel.py
  cat > $K/kernel-metadata.json <<EOF
{"id": "$USER/nizam-ocr-run-$(basename $K | sed 's/kernel-//')", "title": "nizam-ocr-run-$(basename $K | sed 's/kernel-//')",
 "code_file": "ocr_kernel.py", "language": "python", "kernel_type": "script", "is_private": true,
 "enable_gpu": true, "enable_internet": true, "dataset_sources": [$SRC], "kernel_sources": [$KSRC], "competition_sources": []}
EOF
  # enable_gpu alone no longer attaches a GPU (run a died at nvidia-smi); --accelerator does. T4 = sm_75, in the build.
  cat $K/kernel-metadata.json
  if $KG kernels push -p $K --accelerator ${KG_ACCEL:-NvidiaTeslaT4} | tee /dev/stderr | grep -q "successfully pushed"; then
    # run ledger for tools/kaggle/progress.py: name, groups, datasets, pushed (UTC), hour bound
    printf '%s\t%s\t%s\t%s\t%s\n' "$(basename $K | sed 's/kernel-//')" "$G" "$*" "$(date -u +%FT%TZ)" "${KG_HOURS:-11}" >> $ROOT/runs.tsv
  fi ;;
vlmdata)
  # kg.sh vlmdata SUFFIX : upload E:/nizam-data/ocr/kaggle/vlm-SUFFIX (tools/kaggle/vlm_inputs.py) as dataset nizam-vlm-SUFFIX
  DS=$ROOT/vlm-$2
  cat > $DS/dataset-metadata.json <<EOF2
{"title": "nizam-vlm-$2", "id": "$USER/nizam-vlm-$2", "licenses": [{"name": "other"}]}
EOF2
  if $KG datasets status $USER/nizam-vlm-$2 >/dev/null 2>&1; then $KG datasets version -p $DS -m "inputs $(date -u +%F)" -r skip
  else $KG datasets create -p $DS -r skip; fi ;;
vlmpush)
  # kg.sh vlmpush NAME SUFFIX : push the vision-model pre-read kernel over dataset nizam-vlm-SUFFIX (wait for it to be ready)
  K=$ROOT/kernel-$2; mkdir -p $K
  # KG_VLMK: the kernel file (default vlm_kernel.py, Qwen2.5-VL-7B; vlm3_kernel.py, Qwen3-VL-8B read in two crops)
  sed "s/__HOURS__/${KG_HOURS:-11}/" /mnt/e/Nizam_e_Qanoon/tools/kaggle/${KG_VLMK:-vlm_kernel.py} > $K/vlm_kernel.py
  cat > $K/kernel-metadata.json <<EOF2
{"id": "$USER/nizam-ocr-run-$2", "title": "nizam-ocr-run-$2", "code_file": "vlm_kernel.py", "language": "python",
 "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_internet": true,
 "dataset_sources": ["$USER/nizam-vlm-$3"], "kernel_sources": [], "competition_sources": []}
EOF2
  $KG kernels push -p $K --accelerator ${KG_ACCEL:-NvidiaTeslaT4} | tee /dev/stderr | grep -q "successfully pushed" && \
    printf '%s\t%s\t%s\t%s\t%s\n' "$2" "vlm" "$3" "$(date -u +%FT%TZ)" "${KG_HOURS:-11}" >> $ROOT/runs.tsv ;;
progress)
  # per run and per group: documents/pages read by Kaggle, fetched, imported, released (tools/kaggle/progress.py)
  cd /mnt/e/Nizam_e_Qanoon && PYTHONPATH=. .venv/bin/python tools/kaggle/progress.py ;;
status)
  $KG kernels status $USER/nizam-ocr-run-$2 ;;
logs)
  # the running kernel's stdout so far (run.log lines), without waiting for it to finish
  $KG kernels logs $USER/nizam-ocr-run-$2 2>&1 | grep -oE '"data":"[^"]*' | sed 's/"data":"//; s/\\n$//' | grep -E '^[0-9]{2}:[0-9]{2}:[0-9]{2} ' | tail -${3:-15} ;;
embeddata)
  # kg.sh embeddata VERSION : upload E:/nizam-data/embed/ds-VERSION (tools/kaggle/embed_inputs.py) as private dataset
  # nizam-embed-VERSION (D-098)
  DS=/mnt/e/nizam-data/embed/ds-$2
  cat > $DS/dataset-metadata.json <<EOF3
{"title": "nizam-embed-$2", "id": "$USER/nizam-embed-$2", "licenses": [{"name": "other"}]}
EOF3
  if $KG datasets status $USER/nizam-embed-$2 >/dev/null 2>&1; then $KG datasets version -p $DS -m "inputs $(date -u +%F)" -r skip
  else $KG datasets create -p $DS -r skip; fi ;;
embedpush)
  # kg.sh embedpush NAME VERSION : push the embedding kernel (tools/kaggle/embed_kernel.py) over nizam-embed-VERSION;
  # KG_SMOKE=1 embeds the first 20,000 chunks only; KG_MODELS=slug,slug runs a subset (e.g. one model per account)
  K=/mnt/e/nizam-data/embed/kernel-$2; mkdir -p $K
  # KG_KEEPFLOAT=1 KG_REV=<hub commit>: keep the float vectors of that pinned commit (ADR-1d after reranking, D-110)
  sed "s/__HOURS__/${KG_HOURS:-11}/; s/__SMOKE__/${KG_SMOKE:-0}/; s/__ONLY__/${KG_MODELS:-}/; s/__KEEPFLOAT__/${KG_KEEPFLOAT:-0}/; s/__REV__/${KG_REV:-}/" /mnt/e/Nizam_e_Qanoon/tools/kaggle/embed_kernel.py > $K/embed_kernel.py
  cat > $K/kernel-metadata.json <<EOF3
{"id": "$USER/nizam-embed-run-$2", "title": "nizam-embed-run-$2", "code_file": "embed_kernel.py", "language": "python",
 "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_internet": true,
 "dataset_sources": ["$USER/nizam-embed-$3"], "kernel_sources": [], "competition_sources": []}
EOF3
  $KG kernels push -p $K --accelerator ${KG_ACCEL:-NvidiaTeslaT4} ;;
e8push)
  # kg.sh e8push NAME SHARDS : push the Qwen3-Embedding-8B shard kernel (tools/kaggle/embed8b_kernel.py, D-099) over
  # nizam-embed-v1; SHARDS like 0-11 or 3,7. KG_SMOKE=1 proves it (pipeline vs sentence-transformers, fp16 vs bf16,
  # throughput) instead; KG_REV=<commit> is required for a full run (the smoke run pins it); KG_TOKBUDGET optional.
  # Status, logs and output: embedstatus / embedlogs / embedfetch NAME (same kernel naming).
  # KG_DS=<dataset> (default nizam-embed-v1; a top-up: nizam-topup-<stamp>) and KG_NSHARD=1 for a top-up
  K=/mnt/e/nizam-data/embed/kernel-$2; mkdir -p $K
  sed "s/__HOURS__/${KG_HOURS:-11.5}/; s/__SMOKE__/${KG_SMOKE:-0}/; s/__SHARDS__/$3/; s/__REV__/${KG_REV:-}/; s/__TOKBUDGET__/${KG_TOKBUDGET:-}/; s/__NSHARD__/${KG_NSHARD:-}/" \
    /mnt/e/Nizam_e_Qanoon/tools/kaggle/embed8b_kernel.py > $K/embed8b_kernel.py
  cat > $K/kernel-metadata.json <<EOF3
{"id": "$USER/nizam-embed-run-$2", "title": "nizam-embed-run-$2", "code_file": "embed8b_kernel.py", "language": "python",
 "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_internet": true,
 "dataset_sources": ["$USER/${KG_DS:-nizam-embed-v1}"], "kernel_sources": [], "competition_sources": []}
EOF3
  grep -n '^HOURS\|^SMOKE\|^SHARDS\|^REV\|^TOKBUDGET' $K/embed8b_kernel.py
  $KG kernels push -p $K --accelerator ${KG_ACCEL:-NvidiaTeslaT4} ;;
q8push)
  # kg.sh q8push NAME DATASET : encode questions.json of private dataset nizam-DATASET with Qwen3-Embedding-8B
  # (tools/kaggle/query8b_kernel.py, D-099) at KG_REV, timing single-question encodes. Output: embedfetch NAME.
  K=/mnt/e/nizam-data/embed/kernel-$2; mkdir -p $K
  sed "s/__REV__/${KG_REV:-}/" /mnt/e/Nizam_e_Qanoon/tools/kaggle/query8b_kernel.py > $K/query8b_kernel.py
  cat > $K/kernel-metadata.json <<EOF3
{"id": "$USER/nizam-embed-run-$2", "title": "nizam-embed-run-$2", "code_file": "query8b_kernel.py", "language": "python",
 "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_internet": true,
 "dataset_sources": ["$USER/nizam-$3"], "kernel_sources": [], "competition_sources": []}
EOF3
  $KG kernels push -p $K --accelerator ${KG_ACCEL:-NvidiaTeslaT4} ;;
rrpush)
  # kg.sh rrpush NAME DATASET MODELS : score pairs.jsonl of private dataset nizam-DATASET (evals/rerank_slates.py, then
  # kg.sh dsup) with the rerankers MODELS (comma-separated slugs of tools/kaggle/rerank_kernel.py). KG_SMOKE=1: 64 pairs.
  K=/mnt/e/nizam-data/rerank/kernel-$2; mkdir -p $K
  sed "s/__MODELS__/$4/; s/__SMOKE__/${KG_SMOKE:-0}/" /mnt/e/Nizam_e_Qanoon/tools/kaggle/rerank_kernel.py > $K/rerank_kernel.py
  cat > $K/kernel-metadata.json <<EOF3
{"id": "$USER/nizam-rerank-run-$2", "title": "nizam-rerank-run-$2", "code_file": "rerank_kernel.py", "language": "python",
 "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_internet": true,
 "dataset_sources": ["$USER/nizam-$3"], "kernel_sources": [], "competition_sources": []}
EOF3
  $KG kernels push -p $K --accelerator ${KG_ACCEL:-NvidiaTeslaT4} ;;
rrexportpush)
  # kg.sh rrexportpush NAME DATASET SLUG : export reranker SLUG to int8 ONNX and score every pair of nizam-DATASET on
  # the Kaggle CPU (tools/kaggle/rerank_export_kernel.py, D-101). Status/fetch: rrstatus/rrfetch NAME.
  K=/mnt/e/nizam-data/rerank/kernel-$2; mkdir -p $K
  sed "s/__SLUG__/$4/" /mnt/e/Nizam_e_Qanoon/tools/kaggle/rerank_export_kernel.py > $K/rerank_export_kernel.py
  cat > $K/kernel-metadata.json <<EOF3
{"id": "$USER/nizam-rerank-run-$2", "title": "nizam-rerank-run-$2", "code_file": "rerank_export_kernel.py",
 "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": false, "enable_internet": true,
 "dataset_sources": ["$USER/nizam-$3"], "kernel_sources": [], "competition_sources": []}
EOF3
  $KG kernels push -p $K ;;
rrstatus)
  $KG kernels status $USER/nizam-rerank-run-$2 ;;
rrfetch)
  # no --force: files already here are skipped and a partial one resumes (an 8B fetch restarted from zero, D-099)
  O=/mnt/e/nizam-data/rerank/out-$2; mkdir -p $O
  $KG kernels output $USER/nizam-rerank-run-$2 -p $O >/dev/null || true
  ls -la $O/out 2>/dev/null; cat $O/out/run.json 2>/dev/null | head -60 || true ;;
dsup)
  # kg.sh dsup NAME DIR : upload DIR (tools/embed_topup.py output) as private dataset nizam-NAME, or a new version
  cat > $3/dataset-metadata.json <<EOF3
{"title": "nizam-$2", "id": "$USER/nizam-$2", "licenses": [{"name": "other"}]}
EOF3
  if $KG datasets status $USER/nizam-$2 >/dev/null 2>&1; then $KG datasets version -p $3 -m "inputs $(date -u +%F)" -r skip
  else $KG datasets create -p $3 -r skip; fi ;;
embedstatus)
  $KG kernels status $USER/nizam-embed-run-$2 ;;
exportpush)
  # kg.sh exportpush NAME VERSION SLUG RUN : export model SLUG (as embedded by bake-off run nizam-embed-run-RUN) to an
  # int8 ONNX query encoder and validate it on the dev questions (tools/kaggle/export_kernel.py, D-098). The hub id,
  # pooling and query template are read from the run's own metrics.json, so the encoder cannot drift from the vectors.
  M=/mnt/e/nizam-data/embed/out-$5/out/$4/metrics.json
  [ -f $M ] || { echo "no $M: run embedfetch $5 first"; exit 1; }
  HUB=$(python3 -c "import json;print(json.load(open('$M'))['model'])")
  POOL=$(python3 -c "import json;print(json.load(open('$M'))['pooling'])")
  REV=$(python3 -c "import json;print(json.load(open('$M'))['revision'])")
  QT=$(python3 -c "import json;print(json.dumps(json.dumps(json.load(open('$M'))['query_template']))[1:-1])")
  K=/mnt/e/nizam-data/embed/kexport-$2; mkdir -p $K
  python3 - "$4" "$HUB" "$POOL" "$QT" $K/export_kernel.py "$REV" <<'EOF4'
import sys
slug, hub, pool, qt, out, rev = sys.argv[1:7]
s = open("/mnt/e/Nizam_e_Qanoon/tools/kaggle/export_kernel.py", encoding="utf-8").read()
s = s.replace("__SLUG__", slug).replace("__HUB__", hub).replace("__POOLING__", pool).replace("__QTEMPLATE__", qt).replace("__REVISION__", rev)
open(out, "w", encoding="utf-8").write(s)
EOF4
  cat > $K/kernel-metadata.json <<EOF3
{"id": "$USER/nizam-embed-export-$2", "title": "nizam-embed-export-$2", "code_file": "export_kernel.py",
 "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": false, "enable_internet": true,
 "dataset_sources": ["$USER/nizam-embed-$3"], "kernel_sources": ["$USER/nizam-embed-run-$5"], "competition_sources": []}
EOF3
  $KG kernels push -p $K ;;
querypush)
  # kg.sh querypush NAME VERSION RUN/SLUG... : encode the dev questions at full precision with each model, at the revision
  # and template its bake-off run recorded (tools/kaggle/query_kernel.py, D-098; the asymmetric-rescoring arm of ADR-1d)
  K=/mnt/e/nizam-data/embed/kquery-$2; mkdir -p $K; V=$3; shift 3
  python3 - $K/query_kernel.py "$@" <<'EOF5'
import json, sys
out, pairs = sys.argv[1], sys.argv[2:]
specs = []
for p in pairs:
    run, slug = p.split("/")
    m = json.load(open(f"/mnt/e/nizam-data/embed/out-{run}/out/{slug}/metrics.json", encoding="utf-8"))
    specs.append({"slug": slug, "model": m["model"], "revision": m["revision"], "query_template": m["query_template"]})
s = open("/mnt/e/Nizam_e_Qanoon/tools/kaggle/query_kernel.py", encoding="utf-8").read()
lit = json.dumps(specs).replace("\\", "\\\\").replace("'", "\\'")
open(out, "w", encoding="utf-8").write(s.replace("__SPECS__", lit))
print(json.dumps(specs, indent=1))
EOF5
  cat > $K/kernel-metadata.json <<EOF3
{"id": "$USER/nizam-embed-query-$(basename $K | sed 's/kquery-//')", "title": "nizam-embed-query-$(basename $K | sed 's/kquery-//')",
 "code_file": "query_kernel.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": false,
 "enable_internet": true, "dataset_sources": ["$USER/nizam-embed-$V"], "kernel_sources": [], "competition_sources": []}
EOF3
  $KG kernels push -p $K ;;
querystatus)
  $KG kernels status $USER/nizam-embed-query-$2 ;;
queryfetch)
  O=/mnt/e/nizam-data/embed/query-$2; mkdir -p $O
  $KG kernels output $USER/nizam-embed-query-$2 -p $O --force >/dev/null || true
  ls -la $O ;;
exportstatus)
  $KG kernels status $USER/nizam-embed-export-$2 ;;
exportfetch)
  O=/mnt/e/nizam-data/embed/export-$2; mkdir -p $O
  $KG kernels output $USER/nizam-embed-export-$2 -p $O --force >/dev/null || true
  ls -la $O $O/encoder 2>/dev/null; cat $O/encoder/validation.json 2>/dev/null; tail -8 $O/run.log 2>/dev/null || true ;;
embedlogs)
  $KG kernels logs $USER/nizam-embed-run-$2 2>&1 | grep -oE '"data":"[^"]*' | sed 's/"data":"//; s/\n$//' | grep -E '^[0-9]{2}:[0-9]{2}:[0-9]{2} ' | tail -${3:-15} ;;
embedfetch)
  O=/mnt/e/nizam-data/embed/out-$2; mkdir -p $O
  $KG kernels output $USER/nizam-embed-run-$2 -p $O --force >/dev/null || true
  ls -la $O $O/out 2>/dev/null | head -20; tail -5 $O/run.log 2>/dev/null || true ;;
dsstatus)
  $KG datasets status $USER/nizam-ocr-$2 ;;
fetch)
  O=$ROOT/out-$2; mkdir -p $O
  $KG kernels output $USER/nizam-ocr-run-$2 -p $O --force >/dev/null || true
  n=0; for r in $O/out/*/results.json; do [ -f "$r" ] || continue; s=$(basename $(dirname $r))
    d=/mnt/e/nizam-data/ocr/colab/output/$s; [ -f $d/results.json ] && continue; mkdir -p $d; cp $r $d/; n=$((n+1)); done
  echo "fetched $n new result(s)"; tail -3 $O/run.log 2>/dev/null || true ;;
esac
