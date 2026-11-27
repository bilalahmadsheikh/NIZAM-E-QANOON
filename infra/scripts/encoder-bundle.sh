# Sourced by export.sh, export-physical.sh, restore.sh and restore-physical.sh (D-098).
#
# The vectors travel inside the database; the query encoder that makes a question comparable with them does not
# (a 570 MB ONNX file under ${NIZAM_ENCODER_DIR:-${CORPUS_ROOT}/models/encoder}). A copy of the corpus without it can
# only serve lexical_only, so an export carries it and a restore verifies and installs it.
#
# Needs: CORPUS_ROOT, and a psql_ function that runs one SQL statement against the corpus database.

# bundle_encoder OUT_DIR : print the active embedding generation's id ("none" when no generation is active) and, when
# one is active, copy its query encoder into OUT_DIR/encoder with SHA256SUMS. Refuses (non-zero) when a generation is
# active and the installed encoder is missing or is not that generation's model and commit.
bundle_encoder() {
  local out="$1" row id model rev src f
  row=$(psql_ "SELECT id || ' ' || model || ' ' || revision FROM embedding_generation
                WHERE active AND storage = 'chunk.embedding'" | tr -d '\r')
  if [ -z "$row" ]; then echo none; return 0; fi
  read -r id model rev <<< "$row"
  src="${NIZAM_ENCODER_DIR:-${CORPUS_ROOT}/models/encoder}"
  [ -f "$src/model.onnx" ] && [ -f "$src/encoder.json" ] \
    || { echo "encoder: generation ${id} (${model}) is active but no encoder is installed at ${src}" >&2; return 1; }
  python3 - "$src/encoder.json" "$model" "$rev" <<'PY' \
    || { echo "encoder: ${src} is not generation ${id}'s encoder (${model}@${rev:0:12})" >&2; return 1; }
import json, sys
e = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(0 if (e.get("model"), e.get("revision")) == (sys.argv[2], sys.argv[3]) else 1)
PY
  mkdir -p "$out/encoder"
  for f in model.onnx tokenizer.json encoder.json validation.json dev_query_int8.npy dev_questions.json; do
    [ -f "$src/$f" ] && cp "$src/$f" "$out/encoder/"
  done
  ( cd "$out/encoder" && sha256sum model.onnx tokenizer.json encoder.json \
      $(ls validation.json dev_query_int8.npy dev_questions.json 2>/dev/null) > SHA256SUMS )
  echo "$id"
}

# bundle_encoder_gpu OUT_DIR : the GPU generation's (D-099) id, or "none". Its encoder is a service on the GPU host
# (nizam.inference.remote), so what travels is the bundle that service is validated against: encoder.json and the
# corpus run's own question vectors (reference_q.npy, reference_questions.json), into OUT_DIR/encoder-gpu with
# SHA256SUMS. Refuses when the generation is active and its bundle is missing or names another model or commit.
bundle_encoder_gpu() {
  local out="$1" row id model rev src
  row=$(psql_ "SELECT id || ' ' || model || ' ' || revision FROM embedding_generation
                WHERE active AND storage = 'chunk_embedding_gpu'" | tr -d '\r')
  if [ -z "$row" ]; then echo none; return 0; fi
  read -r id model rev <<< "$row"
  src="${NIZAM_GPU_ENCODER_DIR:-${CORPUS_ROOT}/models/encoder-gpu}"
  [ -f "$src/encoder.json" ] && [ -f "$src/reference_q.npy" ] && [ -f "$src/reference_questions.json" ] \
    || { echo "encoder: GPU generation ${id} (${model}) is active but its bundle is not at ${src}" >&2; return 1; }
  python3 - "$src/encoder.json" "$model" "$rev" <<'PY' \
    || { echo "encoder: ${src} is not GPU generation ${id}'s bundle (${model}@${rev:0:12})" >&2; return 1; }
import json, sys
e = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(0 if (e.get("model"), e.get("revision")) == (sys.argv[2], sys.argv[3]) else 1)
PY
  mkdir -p "$out/encoder-gpu"
  cp "$src/encoder.json" "$src/reference_q.npy" "$src/reference_questions.json" "$out/encoder-gpu/"
  ( cd "$out/encoder-gpu" && sha256sum encoder.json reference_q.npy reference_questions.json > SHA256SUMS )
  # the 4-bit host (D-169) is checked against nf4-made reference vectors (D-178: nf4 vs fp16 cosine .977 fails the
  # fp16 bundle's 0.99 check), so its bundle travels too when installed: same model and commit, or refused
  local nf4="${NIZAM_GPU_ENCODER_NF4_DIR:-${CORPUS_ROOT}/models/encoder-gpu-nf4}"
  if [ -f "$nf4/encoder.json" ] && [ -f "$nf4/reference_q.npy" ] && [ -f "$nf4/reference_questions.json" ]; then
    python3 -c "import json,sys; e=json.load(open(sys.argv[1],encoding='utf-8')); sys.exit(0 if (e.get('model'),e.get('revision'),e.get('precision'))==(sys.argv[2],sys.argv[3],'nf4') else 1)" \
      "$nf4/encoder.json" "$model" "$rev" || { echo "encoder: ${nf4} is not generation ${id}'s nf4 bundle" >&2; return 1; }
    mkdir -p "$out/encoder-gpu-nf4"
    cp "$nf4/encoder.json" "$nf4/reference_q.npy" "$nf4/reference_questions.json" "$out/encoder-gpu-nf4/"
    ( cd "$out/encoder-gpu-nf4" && sha256sum encoder.json reference_q.npy reference_questions.json > SHA256SUMS )
  fi
  echo "$id"
}

# bundle_rerankers OUT_DIR : the cross-encoders (D-101) are not database state, so they travel beside it when installed:
# the CPU reranker (int8 ONNX, ${NIZAM_RERANKER_DIR:-${CORPUS_ROOT}/models/reranker}) into OUT_DIR/reranker, and the
# GPU reranker's validation bundle (${NIZAM_GPU_RERANKER_DIR:-${CORPUS_ROOT}/models/reranker-gpu}) into
# OUT_DIR/reranker-gpu, each with SHA256SUMS. Prints what it bundled ("cpu gpu", either, or "none"). A copy without a
# reranker serves the fused order marked "unreranked" (docs/04 §9.2), so a missing one is reported, not refused.
bundle_rerankers() {
  local out="$1" src got="" f
  src="${NIZAM_RERANKER_DIR:-${CORPUS_ROOT}/models/reranker}"
  if [ -f "$src/model.onnx" ] && [ -f "$src/reranker.json" ] && [ -f "$src/tokenizer.json" ]; then
    mkdir -p "$out/reranker"
    for f in model.onnx tokenizer.json reranker.json validation.json reference_pairs.jsonl scores-fp32-first256.npy; do
      [ -f "$src/$f" ] && cp "$src/$f" "$out/reranker/"
    done
    ( cd "$out/reranker" && sha256sum model.onnx tokenizer.json reranker.json \
        $(ls validation.json reference_pairs.jsonl scores-fp32-first256.npy 2>/dev/null) > SHA256SUMS )
    got="cpu"
  fi
  src="${NIZAM_GPU_RERANKER_DIR:-${CORPUS_ROOT}/models/reranker-gpu}"
  if [ -f "$src/reranker.json" ] && [ -f "$src/reference.json" ]; then
    mkdir -p "$out/reranker-gpu"
    cp "$src/reranker.json" "$src/reference.json" "$out/reranker-gpu/"
    ( cd "$out/reranker-gpu" && sha256sum reranker.json reference.json > SHA256SUMS )
    got="${got:+$got }gpu"
  fi
  # the 4-bit GPU reranker's bundle (D-182): precision nf4 and nf4-made reference scores (fp16 and nf4 rank alike, so
  # the host's /health precision is what tells them apart; the gate keys its calibration by precision)
  src="${NIZAM_GPU_RERANKER_NF4_DIR:-${CORPUS_ROOT}/models/reranker-gpu-nf4}"
  if [ -f "$src/reranker.json" ] && [ -f "$src/reference.json" ]; then
    python3 -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1],encoding='utf-8')).get('precision')=='nf4' else 1)"       "$src/reranker.json" || { echo "reranker: ${src} is not an nf4 bundle" >&2; return 1; }
    mkdir -p "$out/reranker-gpu-nf4"
    cp "$src/reranker.json" "$src/reference.json" "$out/reranker-gpu-nf4/"
    ( cd "$out/reranker-gpu-nf4" && sha256sum reranker.json reference.json > SHA256SUMS )
    got="${got:+$got }gpu-nf4"
  fi
  echo "${got:-none}"
}

# check_encoder DIR : verify DIR/encoder, DIR/encoder-gpu, DIR/reranker and DIR/reranker-gpu against their SHA256SUMS
# (absent folders: nothing to check)
check_encoder() {
  local sub src
  for sub in encoder encoder-gpu encoder-gpu-nf4 reranker reranker-gpu reranker-gpu-nf4; do
    src="$1/$sub"
    [ -f "$src/SHA256SUMS" ] || continue
    ( cd "$src" && sha256sum -c --quiet SHA256SUMS ) || { echo "encoder: ${src} fails its SHA256SUMS" >&2; return 1; }
  done
}

# install_encoder DIR : verify DIR/encoder (and DIR/encoder-gpu) and copy each to the directory this machine reads
install_encoder() {
  local dst
  check_encoder "$1" || return 1
  if [ -f "$1/encoder/SHA256SUMS" ]; then
    dst="${NIZAM_ENCODER_DIR:-${CORPUS_ROOT}/models/encoder}"
    mkdir -p "$dst"
    cp "$1/encoder"/* "$dst/"
    echo "query encoder installed at ${dst} ($(sed -n 's/^ *"model": *"\(.*\)",$/\1/p' "$dst/encoder.json"))"
  fi
  if [ -f "$1/encoder-gpu/SHA256SUMS" ]; then
    dst="${NIZAM_GPU_ENCODER_DIR:-${CORPUS_ROOT}/models/encoder-gpu}"
    mkdir -p "$dst"
    cp "$1/encoder-gpu"/* "$dst/"
    echo "GPU encoder bundle installed at ${dst} (served by the GPU host: set NIZAM_GPU_ENCODER_URL)"
  fi
  if [ -f "$1/encoder-gpu-nf4/SHA256SUMS" ]; then
    dst="${NIZAM_GPU_ENCODER_NF4_DIR:-${CORPUS_ROOT}/models/encoder-gpu-nf4}"
    mkdir -p "$dst"
    cp "$1/encoder-gpu-nf4"/* "$dst/"
    echo "4-bit GPU encoder bundle installed at ${dst} (a 4-bit host: set NIZAM_GPU_ENCODER_DIR=${dst})"
  fi
  if [ -f "$1/reranker/SHA256SUMS" ]; then
    dst="${NIZAM_RERANKER_DIR:-${CORPUS_ROOT}/models/reranker}"
    mkdir -p "$dst"
    cp "$1/reranker"/* "$dst/"
    echo "reranker installed at ${dst} ($(sed -n 's/^ *"model": *"\(.*\)",$/\1/p' "$dst/reranker.json"))"
  fi
  if [ -f "$1/reranker-gpu/SHA256SUMS" ]; then
    dst="${NIZAM_GPU_RERANKER_DIR:-${CORPUS_ROOT}/models/reranker-gpu}"
    mkdir -p "$dst"
    cp "$1/reranker-gpu"/* "$dst/"
    echo "GPU reranker bundle installed at ${dst} (served by the GPU host: set NIZAM_GPU_RERANKER_URL)"
  fi
  if [ -f "$1/reranker-gpu-nf4/SHA256SUMS" ]; then
    dst="${NIZAM_GPU_RERANKER_NF4_DIR:-${CORPUS_ROOT}/models/reranker-gpu-nf4}"
    mkdir -p "$dst"
    cp "$1/reranker-gpu-nf4"/* "$dst/"
    echo "4-bit GPU reranker bundle installed at ${dst} (a 4-bit host: set NIZAM_GPU_RERANKER_DIR=${dst})"
  fi
}
