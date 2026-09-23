#!/usr/bin/env bash
# 알고보면 제작 도구 준비: Pillow + ffmpeg(imageio-ffmpeg) + sherpa-onnx 한국어 음성(KSS).
# 결과 경로는 ~/.cache/algobomyeon 에 둔다. 여러 번 실행해도 안전하다.
set -euo pipefail

TOOLS="$(cd "$(dirname "$0")" && pwd)"
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

# MeloTTS-Korean(MIT): huggingface.co에 닿을 때만 설치·시험하고, 성공하면 melo.ok를 만든다.
# 실패하면 melo.ok를 지워 make_short.py가 KSS 음성을 쓰게 한다.
MELO_COMMIT=209145371cff8fc3bd60d7be902ea69cbdb7965a
setup_melo() {
  local hf
  hf=$(curl -s -o /dev/null -w '%{http_code}' -L -m 30 \
    https://huggingface.co/myshell-ai/MeloTTS-Korean/resolve/main/config.json || true)
  if [ "$hf" != "200" ]; then
    echo "melo: huggingface.co 접속 불가($hf) → KSS 음성 사용"
    return 1
  fi
  if [ ! -x "$CACHE/melo-venv/bin/python" ] || ! "$CACHE/melo-venv/bin/python" -c "import melo" 2>/dev/null; then
    python3 -m venv "$CACHE/melo-venv"
    "$CACHE/melo-venv/bin/pip" install --quiet "git+https://github.com/myshell-ai/MeloTTS.git@$MELO_COMMIT" || return 1
  fi
  # 한국어에는 필요 없는 일본어 사전(770MB) 대신 함께 설치된 unidic-lite를 쓴다
  local sp
  sp=$("$CACHE/melo-venv/bin/python" -c "import site; print(site.getsitepackages()[0])")
  if [ ! -e "$sp/unidic/dicdir/mecabrc" ]; then
    rm -rf "$sp/unidic/dicdir" && ln -s "$sp/unidic_lite/dicdir" "$sp/unidic/dicdir"
  fi
  local tmp
  tmp=$(mktemp -d)
  echo '[{"text": "문어는 심장이 세 개예요. 진짜요?", "out": "'"$tmp"'/t.wav"}]' > "$tmp/jobs.json"
  "$CACHE/melo-venv/bin/python" "$TOOLS/melo_tts.py" "$tmp/jobs.json" >/dev/null 2>&1 \
    && [ -s "$tmp/t.wav" ] || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
}
if setup_melo; then touch "$CACHE/melo.ok"; echo "melo: 사용"; else rm -f "$CACHE/melo.ok"; echo "melo: 실패 → KSS"; fi
