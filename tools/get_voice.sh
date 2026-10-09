#!/usr/bin/env bash
# 제작 세션용: GitHub(tts 워크플로)가 만든 MeloTTS 목소리를 받아 <폴더>/voice/에 둔다.
# 대본이 아직 안 올라갔으면 커밋·푸시해서 워크플로를 깨운다. 지금 대본과 해시가 맞는 목소리가
# 올라올 때까지 최대 VOICE_WAIT_STEPS×15초(기본 30분) 기다리고, 끝내 없으면 그냥 넘어간다(제작기는 KSS로 만든다).
# 사용법: bash tools/get_voice.sh shorts/<id>/script.json
set -uo pipefail
S="$1"; D="$(dirname "$S")"
git add "$S" && git commit -q -m "대본: $D (목소리 요청)" && { git push -q || echo "voice: push 실패"; } || true
match() { python3 - "$S" <<'PY'
import json, sys, pathlib, hashlib
s = pathlib.Path(sys.argv[1]); m = s.parent / "voice" / "manifest.json"
if not m.exists(): sys.exit(1)
spec = json.loads(s.read_text(encoding="utf-8")); man = json.loads(m.read_text())["scenes"]
sp = float(spec.get("voiceSpeed", 1.25 if spec.get("format", "short") == "short" else 1.1))
for i, sc in enumerate(spec["scenes"]):
    t = sc.get("say", sc["text"]).replace("\n", " ").replace("*", "")
    if man.get(str(i)) != hashlib.sha256(f"{sp}|{t}".encode("utf-8")).hexdigest()[:16]: sys.exit(1)
PY
}
match && { echo "voice: 이미 맞는 목소리 있음"; exit 0; }
for i in $(seq 1 ${VOICE_WAIT_STEPS:-120}); do
  if git fetch -q origin tts-cache 2>/dev/null && git ls-tree -r --name-only origin/tts-cache | grep -q "^$D/voice/manifest.json"; then
    rm -rf "$D/voice" && git archive origin/tts-cache "$D/voice" | tar x
    if match; then echo "voice: MeloTTS 목소리 받음 ($(ls "$D"/voice/*.wav | wc -l)개)"; exit 0; fi
  fi
  sleep 15
done
echo "voice: 기다려도 맞는 목소리 없음 → KSS로 진행"; exit 0
