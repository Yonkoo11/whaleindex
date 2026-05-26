#!/usr/bin/env bash
# Concatenate the per-segment VO clips with 0.4s gaps into one track.
set -euo pipefail
cd "$(dirname "$0")/out"

# 0.4s of silence to breathe between segments
ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 0.4 _gap.mp3 -loglevel error

# build concat list: seg-1, gap, seg-2, gap, ...
: > _concat.txt
n=$(ls seg-*.mp3 | wc -l | tr -d ' ')
for i in $(seq 1 "$n"); do
  echo "file 'seg-$i.mp3'" >> _concat.txt
  if [ "$i" -lt "$n" ]; then echo "file '_gap.mp3'" >> _concat.txt; fi
done

# re-encode (segments + silence may differ in params) so concat is clean
ffmpeg -y -f concat -safe 0 -i _concat.txt -ar 44100 -ac 2 -b:a 192k vo.mp3 -loglevel error
echo "wrote out/vo.mp3"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 vo.mp3
