#!/usr/bin/env python3
"""제작 중 자동 품질 검수 — make_short.py가 영상을 만든 직후 스스로 돌린다(사람이 따로 확인할 일 없음).

사용법(단독): python3 tools/qc.py shorts/<id>/script.json
결과: 같은 폴더에 qc.json(항목별 통과/경고/실패)과 qc_sheet.jpg(영상 전체를 12장으로 한눈에 보는 판).
- 실패(fail)가 하나라도 있으면 종료 코드 2 → 그 영상은 올리지 않고 고쳐서 다시 만든다.
- 경고(warn)는 올려도 되지만 logs에 한 줄 남기고 다음 기획에서 고친다.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
NUM = re.compile(r"\d")


def ff(args):
    r = subprocess.run([FF, "-hide_banner", "-nostats", *args], capture_output=True, text=True)
    return r.stderr


def run_qc(script_path, render_info=None):
    script_path = Path(script_path)
    spec = json.loads(script_path.read_text(encoding="utf-8"))
    d = script_path.parent
    video = d / "video.mp4"
    info = render_info or {}
    checks = []

    def add(name, level, value, rule):
        checks.append({"item": name, "result": level, "value": value, "rule": rule})

    if not video.exists():
        add("파일", "fail", "없음", "video.mp4가 있어야 함")
        return finish(d, checks)

    # 1) 길이·용량
    probe = ff(["-i", str(video)])
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe)
    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    short = spec.get("format", "short") == "short"
    lo, hi = (25, 60) if short else (60, 1500)
    add("길이", "pass" if lo <= secs <= hi else "fail", f"{secs:.1f}초", f"{lo}~{hi}초")
    mb = video.stat().st_size / 1e6
    add("용량", "pass" if mb < 80 else "fail", f"{mb:.1f}MB", "80MB 미만(GitHub 100MB 한도·업로드 안정)")

    # 2) 소리 크기
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", ff(["-i", str(video), "-af", "ebur128", "-f", "null", "-"]))
    val = float(lufs[-1]) if lufs else None
    if val is None:
        add("음량", "fail", "측정 불가", "-16~-12 LUFS")
    else:
        add("음량", "pass" if -16 <= val <= -12 else "fail", f"{val} LUFS", "-16~-12 LUFS")

    # 3) 검은 화면·멈춘 화면
    blk = re.findall(r"black_duration:([\d.]+)", ff(["-i", str(video), "-vf", "blackdetect=d=0.4:pix_th=0.06",
                                                     "-an", "-f", "null", "-"]))
    add("검은 화면", "pass" if not blk else "fail", f"{len(blk)}곳", "0.4초 이상 검은 화면 없음")
    frz = re.findall(r"freeze_duration: ([\d.]+)", ff(["-i", str(video), "-vf", "freezedetect=n=0.002:d=2.5",
                                                      "-an", "-f", "null", "-"]))
    add("멈춘 화면", "pass" if not frz else "fail", f"{len(frz)}곳", "2.5초 넘게 멈춘 화면 없음(움직임 규칙)")

    # 4) 대본 규칙(의장 지시 3·8·9·10번)
    scenes = spec["scenes"]
    first = scenes[0].get("say", scenes[0]["text"]).strip()
    add("첫 문장 숫자", "pass" if first[:1].isdigit() or NUM.search(first[:8] or "") else "warn",
        first[:20], "첫 문장은 숫자로 시작(지시 8번②)")
    no_src = [i for i, s in enumerate(scenes) if NUM.search(s["text"]) and not s.get("source") and i > 0]
    add("출처 표시", "pass" if not no_src else "warn", f"출처 없는 숫자 장면 {no_src}",
        "숫자 장면마다 source(지시 9번⑤)")
    cases = sum(1 for s in scenes if s.get("case"))
    add("실제 사례", "pass" if cases >= 1 else "warn", f"{cases}개", "1개 이상(지시 10번②)")
    n_b = info.get("broll_scenes")
    if n_b is None:
        n_b = sum(1 for i in range(len(scenes)) if (d / "broll" / f"s{i:02d}.mp4").exists())
    share = n_b / max(1, len(scenes))
    add("실제 영상 비율", "pass" if share >= 0.5 else "warn", f"{n_b}/{len(scenes)}장면",
        "절반 이상(지시 10번①). 못 받은 날은 경고만")
    bad = [s.get("broll", {}).get("url", "") for s in scenes
           if s.get("broll") and not re.match(r"https://(videos\.pexels\.com|cdn\.pixabay\.com)/", s["broll"].get("url", ""))]
    add("영상 라이선스", "pass" if not bad else "fail", f"허용 밖 주소 {len(bad)}개",
        "Pexels·Pixabay 무료 영상만(지시 10번⑤)")
    if any(s.get("broll") for s in scenes):
        cred = (d / "broll" / "credits.txt")
        add("촬영자 표기", "pass" if cred.exists() and cred.read_text().strip() else "warn",
            "credits.txt", "설명란 마지막 줄에 '영상 자료: Pexels — 촬영자'")
    add("제작기", "pass" if info.get("motion", "v2") == "v2" else "fail", info.get("motion", "v2"), "제작기 v2")

    # 5) 한눈에 보는 판(12장) — 품질관리팀·심의팀이 이 한 장으로 채점
    sheet = d / "qc_sheet.jpg"
    step = max(secs / 12, 0.5)
    ff(["-y", "-i", str(video), "-vf", f"fps=1/{step:.3f},scale=270:480,tile=6x2", "-frames:v", "1",
        "-q:v", "4", str(sheet)])
    return finish(d, checks)


def finish(d, checks):
    fails = [c for c in checks if c["result"] == "fail"]
    warns = [c for c in checks if c["result"] == "warn"]
    out = {"pass": not fails, "fail": len(fails), "warn": len(warns), "checks": checks,
           "sheet": "qc_sheet.jpg"}
    (d / "qc.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    line = "QC " + ("통과" if not fails else "실패") + f" (실패 {len(fails)}·경고 {len(warns)})"
    if fails or warns:
        line += ": " + "; ".join(f"{c['item']} {c['value']}" for c in fails + warns)
    print(line)
    return out


if __name__ == "__main__":
    res = run_qc(sys.argv[1])
    sys.exit(0 if res["pass"] else 2)
