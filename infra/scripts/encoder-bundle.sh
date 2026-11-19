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
  echo "$id"
}

# check_encoder DIR : verify DIR/encoder and DIR/encoder-gpu against their SHA256SUMS (absent folders: nothing to check)
check_encoder() {
  local sub src
  for sub in encoder encoder-gpu; do
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
}
