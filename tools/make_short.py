#!/usr/bin/env python3
"""알고보면 영상 제작기 — 세로 숏폼(1080x1920) / 가로 롱폼(1920x1080).

사용법: python3 tools/make_short.py shorts/<id>/script.json
script.json:
  {
    "id": "2026-09-23-octopus",
    "format": "short" | "long"   (기본 short),
    "title": "...", "description": "...", "tags": [...],
    "sources": ["https://...", "https://..."],
    "scenes": [{"text": "화면 자막", "say": "읽을 문장(없으면 text)"}]
  }
결과: 같은 폴더에 video.mp4, thumb.jpg
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

SIZES = {"short": (1080, 1920), "long": (1920, 1080)}
W, H = SIZES["short"]
FPS = 30
ROOT = Path(__file__).resolve().parent
FONT = str(ROOT / "fonts" / "NanumGothic-ExtraBold.ttf")
CACHE = Path(os.environ.get("ALGO_CACHE", Path.home() / ".cache" / "algobomyeon"))
SHERPA = CACHE / "sherpa-onnx-v1.12.14-linux-x64-shared"
MODEL = CACHE / "vits-mimic3-ko_KO-kss_low"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

YELLOW = (255, 214, 0)
BAND_H = 190  # 롱폼은 make()에서 줄인다
BAR_H = 18
# 장면마다 돌아가며 쓰는 배경 (위→아래 그라데이션)
PALETTES = [
    ((20, 24, 48), (6, 8, 18)),
    ((44, 16, 52), (10, 4, 16)),
    ((10, 44, 58), (2, 10, 16)),
    ((52, 22, 14), (14, 6, 4)),
]


def tts(text, out_wav):
    env = dict(os.environ, LD_LIBRARY_PATH=str(SHERPA / "lib"))
    subprocess.run(
        [
            str(SHERPA / "bin" / "sherpa-onnx-offline-tts"),
            f"--vits-model={MODEL / 'ko_KO-kss_low.onnx'}",
            f"--vits-tokens={MODEL / 'tokens.txt'}",
            f"--vits-data-dir={MODEL / 'espeak-ng-data'}",
            "--vits-length-scale=0.95",
            f"--output-filename={out_wav}",
            text,
        ],
        check=True, env=env, capture_output=True,
    )
    with wave.open(str(out_wav)) as w:
        return w.getnframes() / w.getframerate()


def wrap(draw, text, font, max_w):
    """어절 단위로 줄바꿈하고, 한 어절이 너무 길면 글자 단위로 자른다."""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = f"{cur} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            cur = ""
            for ch in word:
                if draw.textlength(cur + ch, font=font) > max_w and cur:
                    lines.append(cur)
                    cur = ""
                cur += ch
        lines.append(cur)
    return lines


def fit_text(draw, text, max_w, max_h, start=120, low=56):
    size = start
    while size >= low:
        font = ImageFont.truetype(FONT, size)
        lines = wrap(draw, text, font, max_w)
        line_h = int(size * 1.3)
        if line_h * len(lines) <= max_h:
            return font, lines, line_h
        size -= 6
    font = ImageFont.truetype(FONT, low)
    return font, wrap(draw, text, font, max_w), int(low * 1.3)


def gradient(top, bottom):
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        col.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return col.resize((W, H))


_GRADIENTS = {}


def scene_image(text, idx, total, hook=False):
    pal = PALETTES[idx % len(PALETTES)]
    if pal not in _GRADIENTS:
        _GRADIENTS[pal] = gradient(*pal)
    img = _GRADIENTS[pal].copy()
    d = ImageDraw.Draw(img)

    # 노란 「알고보면」 띠
    d.rectangle([0, 0, W, BAND_H], fill=YELLOW)
    bf = ImageFont.truetype(FONT, int(BAND_H * 0.5))
    label = "알고보면"
    d.text(((W - d.textlength(label, font=bf)) / 2, BAND_H * 0.2), label, font=bf, fill=(0, 0, 0))

    # 장면 번호
    nf = ImageFont.truetype(FONT, 40)
    tag = "지금 알려줌" if hook else f"{idx}/{total - 1}"
    d.text((60, BAND_H + 40), tag, font=nf, fill=YELLOW)

    # 본문 자막
    margin = 80 if W < H else 160
    max_h = int((H - BAND_H) * 0.65)
    start = (128 if hook else 112) if W < H else (120 if hook else 96)
    font, lines, line_h = fit_text(d, text, W - margin * 2, max_h, start=start)
    block_h = line_h * len(lines)
    y = BAND_H + (H - BAND_H - BAR_H - block_h) // 2
    for line in lines:
        x = (W - d.textlength(line, font=font)) / 2
        d.text((x, y), line, font=font, fill=YELLOW if hook else (255, 255, 255),
               stroke_width=6, stroke_fill=(0, 0, 0))
        y += line_h

    # 진행 막대 바탕(채움은 ffmpeg drawbox가 시간에 따라 그린다)
    d.rectangle([0, H - BAR_H, W, H], fill=(60, 60, 60))
    return img


def run(args):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True)


def make(script_path):
    global W, H, BAND_H
    script_path = Path(script_path)
    spec = json.loads(script_path.read_text(encoding="utf-8"))
    W, H = SIZES[spec.get("format", "short")]
    BAND_H = 190 if W < H else 130
    _GRADIENTS.clear()
    out_dir = script_path.parent
    work = out_dir / ".work"
    work.mkdir(exist_ok=True)
    scenes = spec["scenes"]
    n = len(scenes)

    segs = []
    total = 0.0
    for i, sc in enumerate(scenes):
        wav = work / f"s{i:03d}.wav"
        dur = tts(sc.get("say", sc["text"]).replace("\n", " "), wav) + 0.45
        png = work / f"s{i:03d}.png"
        scene_image(sc["text"], i, n, hook=(i == 0)).save(png)
        seg = work / f"s{i:03d}.mp4"
        run([
            "-loop", "1", "-i", str(png), "-i", str(wav),
            "-af", "apad", "-t", f"{dur:.3f}",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
            str(seg),
        ])
        segs.append(seg)
        total += dur

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segs))
    joined = work / "joined.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])

    video = out_dir / "video.mp4"
    run([
        "-i", str(joined),
        "-vf", f"drawbox=x=0:y={H - BAR_H}:w='max(1,iw*t/{total:.3f})':h={BAR_H}:color=0xFFD600:t=fill",
        "-c:v", "libx264", "-preset", "medium", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(video),
    ])
    scene_image(spec.get("thumbText", scenes[0]["text"]), 0, n, hook=True).convert("RGB").save(
        out_dir / "thumb.jpg", quality=90)

    for f in work.iterdir():
        f.unlink()
    work.rmdir()
    print(json.dumps({"video": str(video), "seconds": round(total, 2), "bytes": video.stat().st_size},
                     ensure_ascii=False))


if __name__ == "__main__":
    make(sys.argv[1])
