#!/usr/bin/env bash
# Mux screencast + voiceover + burned-in captions into the deliverable.
set -euo pipefail
cd "$(dirname "$0")/out"

# Captions are already baked into raw.mp4 (in-page overlay during capture),
# so this just marries the screencast to the voiceover.
ffmpeg -y -i raw.mp4 -i vo.mp3 \
  -map 0:v:0 -map 1:a:0 \
  -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 44100 \
  -movflags +faststart \
  whaleindex-demo.mp4 -loglevel error

echo "=== whaleindex-demo.mp4 ==="
ffprobe -v error -show_entries format=duration:stream=width,height,codec_name -of default=nw=1 whaleindex-demo.mp4
du -h whaleindex-demo.mp4
