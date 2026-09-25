#!/usr/bin/env bash
# 제작 세션용: 오늘 대본의 실제 영상 클립을 준비한다.
# 1) 직접 받기 시도 → 2) 안 되면 script.json을 push해 GitHub(broll 워크플로)가 받게 하고 최대 10분 기다린 뒤 가져온다.
# 끝까지 안 되면 클립 없이 진행(제작기가 그림 배경으로 대신 만든다). 사용법: bash tools/get_broll.sh shorts/<id>/script.json
set -uo pipefail
S="$1"; D="$(dirname "$S")"
python3 tools/fetch_broll.py "$S" && { echo "broll: 직접 받기 성공"; exit 0; }
echo "broll: 직접 받기 실패 → GitHub에서 받기"
git add "$S" && git commit -q -m "대본: $D (broll 요청)" || true
git push -q || { echo "broll: push 실패 → 클립 없이 진행"; exit 0; }
for i in $(seq 1 40); do
  sleep 15
  if git fetch -q origin broll-cache 2>/dev/null && git ls-tree -r --name-only origin/broll-cache | grep -q "^$D/broll/s"; then
    git archive origin/broll-cache "$D/broll" | tar x
    echo "broll: GitHub에서 가져옴 ($(ls "$D"/broll/*.mp4 | wc -l)개)"; exit 0
  fi
done
echo "broll: 10분 안에 못 받음 → 클립 없이 진행"; exit 0
