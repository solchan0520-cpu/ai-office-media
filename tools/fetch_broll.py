#!/usr/bin/env python3
"""실제 촬영 영상(B-roll) 받아서 장면별 클립으로 다듬기.

사용법: python3 tools/fetch_broll.py shorts/<id>/script.json
script.json 장면에 "broll": {"url": "https://videos.pexels.com/...mp4", "start": 0,
                              "credit": "촬영자 / Pexels", "page": "https://www.pexels.com/video/..."}
결과: shorts/<id>/broll/sNN.mp4 (1080x1920·30fps·소리 없음, 최대 15초) + broll/credits.txt
이미 있는 클립은 다시 받지 않는다. 실패한 장면은 건너뛴다(제작기는 그 장면을 그림 배경으로 만든다).
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SIZES = {"short": (1080, 1920), "long": (1920, 1080)}


def main(script_path):
    script_path = Path(script_path)
    spec = json.loads(script_path.read_text(encoding="utf-8"))
    W, H = SIZES[spec.get("format", "short")]
    out = script_path.parent / "broll"
    out.mkdir(exist_ok=True)
    credits, ok, fail = [], 0, 0
    for i, sc in enumerate(spec["scenes"]):
        b = sc.get("broll")
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
    (out / "credits.txt").write_text("\n".join(dict.fromkeys(credits)) + "\n", encoding="utf-8")
    print(json.dumps({"id": spec.get("id"), "ok": ok, "fail": fail}, ensure_ascii=False))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    rc = 0
    for p in sys.argv[1:]:
        rc |= main(p)
    sys.exit(rc)
