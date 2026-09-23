#!/usr/bin/env bash
# 알고보면 제작 도구 준비: Pillow + ffmpeg(imageio-ffmpeg) + sherpa-onnx 한국어 음성(KSS).
# 결과 경로는 ~/.cache/algobomyeon 에 둔다. 여러 번 실행해도 안전하다.
set -euo pipefail

CACHE="${ALGO_CACHE:-$HOME/.cache/algobomyeon}"
mkdir -p "$CACHE"
cd "$CACHE"

python3 -c "import PIL, imageio_ffmpeg" 2>/dev/null || pip install --quiet pillow imageio-ffmpeg

SHERPA=sherpa-onnx-v1.12.14-linux-x64-shared
if [ ! -x "$CACHE/$SHERPA/bin/sherpa-onnx-offline-tts" ]; then
  curl -sSL -o "$SHERPA.tar.bz2" \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.14/$SHERPA.tar.bz2"
  tar xjf "$SHERPA.tar.bz2" && rm "$SHERPA.tar.bz2"
fi

MODEL=vits-mimic3-ko_KO-kss_low
if [ ! -f "$CACHE/$MODEL/ko_KO-kss_low.onnx" ]; then
  curl -sSL -o "$MODEL.tar.bz2" \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$MODEL.tar.bz2"
  tar xjf "$MODEL.tar.bz2" && rm "$MODEL.tar.bz2"
fi

echo "ready: $CACHE"
