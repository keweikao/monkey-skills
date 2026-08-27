#!/bin/bash
# Merge per-chapter mp3s into a single .m4b audiobook with chapter bookmarks.
#
# Usage: build_m4b.sh <mp3_dir> <out.m4b> [title] [author]
#
# Chapter titles come from the filenames: "06-04-The Deal.mp3" → "04 The Deal"
# (leading play-order prefix stripped). Requires ffmpeg + ffprobe.
set -euo pipefail
SRC="${1:?usage: build_m4b.sh <mp3_dir> <out.m4b> [title] [author]}"
OUT="${2:?usage: build_m4b.sh <mp3_dir> <out.m4b> [title] [author]}"
TITLE="${3:-$(basename "$OUT" .m4b)}"
AUTHOR="${4:-}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

command -v ffmpeg >/dev/null || { echo "ffmpeg not found"; exit 1; }
[ -d "$SRC" ] || { echo "mp3 folder not found: $SRC"; exit 1; }

: > "$TMP/list.txt"
for f in "$SRC"/*.mp3; do
  echo "file '$f'" >> "$TMP/list.txt"
done

python3 - "$SRC" "$TMP/chapters.txt" "$TITLE" "$AUTHOR" <<'EOF'
import os, re, subprocess, sys
src, out, title, author = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
files = sorted(f for f in os.listdir(src) if f.endswith('.mp3'))
lines = [";FFMETADATA1", f"title={title}", f"album={title}"]
if author:
    lines.append(f"artist={author}")
t = 0
for f in files:
    dur = float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", os.path.join(src, f)],
        capture_output=True, text=True).stdout.strip())
    ms = int(dur * 1000)
    chap = re.sub(r'^\d+-', '', f[:-4])   # strip play-order prefix
    lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={t}", f"END={t+ms}",
              f"title={chap}"]
    t += ms
open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"chapters: {len(files)}, total {t/1000/3600:.2f} hr")
EOF

ffmpeg -y -f concat -safe 0 -i "$TMP/list.txt" -i "$TMP/chapters.txt" \
  -map_metadata 1 -map_chapters 1 \
  -c:a aac -b:a 64k -movflags +faststart \
  "$OUT"

echo "=== done ==="
ls -lh "$OUT"
