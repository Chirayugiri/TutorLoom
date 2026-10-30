#!/usr/bin/env bash
# Download a static FFmpeg build into tools/bin (used when ffmpeg is not installed system-wide).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bin dl
curl -fsSL -o dl/ff.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf dl/ff.tar.xz -C dl
mv dl/ffmpeg-*-static/ffmpeg dl/ffmpeg-*-static/ffprobe bin/
rm -rf dl
bin/ffmpeg -version | head -1
