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
dsstatus)
  $KG datasets status $USER/nizam-ocr-$2 ;;
fetch)
  O=$ROOT/out-$2; mkdir -p $O
  $KG kernels output $USER/nizam-ocr-run-$2 -p $O --force >/dev/null || true
  n=0; for r in $O/out/*/results.json; do [ -f "$r" ] || continue; s=$(basename $(dirname $r))
    d=/mnt/e/nizam-data/ocr/colab/output/$s; [ -f $d/results.json ] && continue; mkdir -p $d; cp $r $d/; n=$((n+1)); done
  echo "fetched $n new result(s)"; tail -3 $O/run.log 2>/dev/null || true ;;
esac
