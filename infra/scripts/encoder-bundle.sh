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
  row=$(psql_ "SELECT id || ' ' || model || ' ' || revision FROM embedding_generation WHERE active" | tr -d '\r')
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

# check_encoder DIR : verify DIR/encoder against its SHA256SUMS (absent folder: nothing to check)
check_encoder() {
  local src="$1/encoder"
  [ -f "$src/SHA256SUMS" ] || return 0
  ( cd "$src" && sha256sum -c --quiet SHA256SUMS ) || { echo "encoder: ${src} fails its SHA256SUMS" >&2; return 1; }
}

# install_encoder DIR : verify DIR/encoder and copy it to the encoder directory this machine reads
install_encoder() {
  local src="$1/encoder" dst
  [ -f "$src/SHA256SUMS" ] || return 0
  check_encoder "$1" || return 1
  dst="${NIZAM_ENCODER_DIR:-${CORPUS_ROOT}/models/encoder}"
  mkdir -p "$dst"
  cp "$src"/* "$dst/"
  echo "query encoder installed at ${dst} ($(sed -n 's/^ *"model": *"\(.*\)",$/\1/p' "$dst/encoder.json"))"
}
