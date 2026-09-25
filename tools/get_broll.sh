#!/usr/bin/env bash
# 제작 세션용: 오늘 대본의 실제 영상 클립을 준비한다.
# 1) 직접 받기 시도 → 2) 안 되면 script.json을 push해 GitHub(broll 워크플로)가 받게 하고 최대 10분 기다린 뒤 가져온다.
# 끝까지 안 되면 클립 없이 진행(제작기가 그림 배경으로 대신 만든다). 사용법: bash tools/get_broll.sh shorts/<id>/script.json
set -uo pipefail
S="$1"; D="$(dirname "$S")"
# 검색어(query)로 고른 영상을 script.json에 합친다(주소·촬영자·라이선스 기록 → 제작기·검수·설명란이 그대로 씀)
merge() { python3 - "$S" <<'PY'
import json, sys, pathlib
s = pathlib.Path(sys.argv[1]); r = s.parent / "broll" / "resolved.json"
spec = json.loads(s.read_text(encoding="utf-8"))
res = json.loads(r.read_text(encoding="utf-8")) if r.exists() else {}
for k, v in res.items():
    sc = spec["scenes"][int(k)]
    sc["broll"] = {**sc.get("broll", {}), **v}
# 검색어만 있고 영상을 못 고른 장면은 broll을 빼서 그림 배경으로(검수에서 '주소 없음'으로 실패하지 않게)
dropped = 0
for sc in spec["scenes"]:
    if sc.get("broll") and not sc["broll"].get("url"):
        sc.pop("broll"); dropped += 1
s.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"broll: 검색으로 고른 영상 {len(res)}개 대본에 합침 · 못 고른 장면 {dropped}개는 그림 배경")
PY
}
trap merge EXIT
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
