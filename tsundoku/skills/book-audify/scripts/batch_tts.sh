#!/bin/bash
# Batch-synthesize TTS-ready chapter .txt files into per-chapter mp3s.
#
# Usage: batch_tts.sh <src_txt_dir> <dst_mp3_dir> [voice] [rate]
#   voice  edge-tts voice name        (default: zh-TW-HsiaoChenNeural)
#          list options: edge-tts --list-voices | grep <lang>
#   rate   base speaking rate offset  (default: +0%)
#          tip: if you listen at 1.5x, generate at -25% so pauses and
#          prosody survive the speed-up
#
# Idempotent: existing non-empty mp3s are skipped, so a killed run can be
# resumed by re-running the same command. Runs validate_tts.py first — a
# dirty source folder refuses to synthesize.
set -uo pipefail
SRC="${1:?usage: batch_tts.sh <src_txt_dir> <dst_mp3_dir> [voice] [rate]}"
DST="${2:?usage: batch_tts.sh <src_txt_dir> <dst_mp3_dir> [voice] [rate]}"
VOICE="${3:-zh-TW-HsiaoChenNeural}"
RATE="${4:-+0%}"

command -v edge-tts >/dev/null || { echo "edge-tts not found: pip install edge-tts"; exit 1; }
[ -d "$SRC" ] || { echo "source folder not found: $SRC"; exit 1; }
python3 "$(dirname "$0")/validate_tts.py" "$SRC" || { echo "not TTS-ready — fix violations first"; exit 1; }
mkdir -p "$DST"

fail=0
for f in "$SRC"/*.txt; do
  base="$(basename "$f" .txt)"
  out="$DST/$base.mp3"
  if [ -s "$out" ]; then
    echo "skip(exists) $base"
    continue
  fi
  echo "tts[$VOICE $RATE] $base ..."
  if ! edge-tts --voice "$VOICE" --rate="$RATE" --file "$f" --write-media "$out"; then
    echo "FAIL $base"
    fail=1
    rm -f "$out"
  fi
done

echo "=== summary ==="
ls -lh "$DST" | tail -n +2
[ "$fail" -eq 0 ] && echo "ALL OK" || { echo "SOME FAILED — re-run to retry"; exit 1; }
