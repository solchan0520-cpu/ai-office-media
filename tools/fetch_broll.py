#!/usr/bin/env python3
"""실제 촬영 영상(B-roll) 받아서 장면별 클립으로 다듬기.

사용법: python3 tools/fetch_broll.py shorts/<id>/script.json
script.json 장면에 "broll": {"url": "https://videos.pexels.com/...mp4", "start": 0,
                              "credit": "촬영자 / Pexels", "page": "https://www.pexels.com/video/..."}
  또는 "broll": {"query": "korean market crowd"} — url 없이 검색어만 적으면, 환경변수 PEXELS_API_KEY가 있을 때
  Pexels 공식 API로 검색해 첫 번째 쓸 수 있는 영상을 고른다(무료, vidIQ 크레딧 불필요).
  고른 결과는 broll/resolved.json에 {장면번호: {url, page, credit, license}}로 남는다(get_broll.sh가 script.json에 합침).
결과: shorts/<id>/broll/sNN.mp4 (1080x1920·30fps·소리 없음, 최대 15초) + broll/credits.txt
이미 있는 클립은 다시 받지 않는다. 실패한 장면은 건너뛴다(제작기는 그 장면을 그림 배경으로 만든다).
"""
import json
import os
import urllib.parse
import subprocess
import sys
import urllib.request
from pathlib import Path

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SIZES = {"short": (1080, 1920), "long": (1920, 1080)}


def pexels_search(query, orientation, used):
    """Pexels 공식 API(무료 키)로 영상 검색 → 쓸 수 있는 첫 영상 {url, page, credit, license}."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    q = urllib.parse.urlencode({"query": query, "orientation": orientation, "per_page": 15, "size": "medium"})
    req = urllib.request.Request(f"https://api.pexels.com/videos/search?{q}",
                                 headers={"Authorization": key, "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    for v in data.get("videos", []):
        page = v.get("url", "")
        if not page or page in used or v.get("duration", 0) < 4:
            continue
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("link")]
        # 너무 크지 않은 HD 파일(긴 변 1920 이하) 중 가장 큰 것
        files = [f for f in files if max(f.get("width") or 0, f.get("height") or 0) <= 1920] or files
        if not files:
            continue
        best = max(files, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0))
        link = best["link"]
        if not link.startswith("https://videos.pexels.com/"):  # qc.py 라이선스 검사와 같은 기준
            continue
        user = (v.get("user") or {}).get("name", "Pexels")
        return {"url": link, "page": page, "credit": f"{user} / Pexels", "license": "Pexels License(상업 무료)"}
    return None


def main(script_path):
    script_path = Path(script_path)
    spec = json.loads(script_path.read_text(encoding="utf-8"))
    W, H = SIZES[spec.get("format", "short")]
    out = script_path.parent / "broll"
    out.mkdir(exist_ok=True)
    credits, ok, fail = [], 0, 0
    resolved_path = out / "resolved.json"
    resolved = json.loads(resolved_path.read_text(encoding="utf-8")) if resolved_path.exists() else {}
    used = {sc.get("broll", {}).get("page") for sc in spec["scenes"] if sc.get("broll")} | set(spec.get("brollUsed", []))
    used |= {r.get("page") for r in resolved.values()}
    orientation = "portrait" if spec.get("format", "short") == "short" else "landscape"
    for i, sc in enumerate(spec["scenes"]):
        b = sc.get("broll")
        if b and not b.get("url") and b.get("query"):
            if str(i) in resolved:
                b = {**b, **resolved[str(i)]}
            else:
                try:
                    hit = pexels_search(b["query"], orientation, used)
                except Exception as e:  # 검색 실패는 그 장면만 그림 배경으로
                    hit = None
                    print(f"장면 {i} 검색 실패: {e}", file=sys.stderr)
                if hit:
                    used.add(hit["page"])
                    resolved[str(i)] = hit
                    b = {**b, **hit}
                else:
                    fail += 1  # 검색어를 못 풀면 실패로 세서 get_broll.sh가 GitHub(키 있음)로 넘기게 한다
        if not b or not b.get("url"):
            continue
        dst = out / f"s{i:02d}.mp4"
        if b.get("credit"):
            credits.append(f"{b['credit']} {b.get('page', '')}".strip())
        if dst.exists() and dst.stat().st_size > 1000:
            ok += 1
            continue
        tmp = out / f".raw{i:02d}.mp4"
        try:
            req = urllib.request.Request(b["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                f.write(r.read())
            subprocess.run([FF, "-y", "-loglevel", "error", "-ss", str(b.get("start", 0)), "-i", str(tmp),
                            "-t", "15", "-an",
                            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
                            str(dst)], check=True)
            ok += 1
        except Exception as e:  # 한 장면 실패는 전체를 막지 않는다
            fail += 1
            print(f"장면 {i} 실패: {e}", file=sys.stderr)
        finally:
            tmp.unlink(missing_ok=True)
    if resolved:
        resolved_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "credits.txt").write_text("\n".join(dict.fromkeys(credits)) + "\n", encoding="utf-8")
    print(json.dumps({"id": spec.get("id"), "ok": ok, "fail": fail}, ensure_ascii=False))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    rc = 0
    for p in sys.argv[1:]:
        rc |= main(p)
    sys.exit(rc)
