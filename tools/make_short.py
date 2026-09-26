#!/usr/bin/env python3
"""알고보면 영상 제작기 v2 — 세로 숏폼(1080x1920) / 가로 롱폼(1920x1080), 움직이는 화면.

사용법: python3 tools/make_short.py shorts/<id>/script.json
script.json:
  {
    "id": "2026-09-23-octopus",
    "format": "short" | "long"   (기본 short),
    "title": "...", "description": "...", "tags": [...],
    "sources": ["https://...", "https://..."],
    "music": true | false        (기본 true, 잔잔한 배경음),
    "scenes": [{"text": "화면 자막", "say": "읽을 문장(없으면 text)"}]
  }
자막 규칙:
  - 숫자(45%, 6,000원, 4.7~8.2배)는 자동으로 노란색 + 0에서 올라가는 카운트업.
  - *강조할 말* 처럼 별표로 감싸면 그 말도 노란색으로 강조된다(별표는 화면에 안 나옴).
움직임: 배경이 천천히 확대·이동, 줄마다 톡 튀어나오는 등장, 장면 사이 밀어내기 전환 + 휙 소리,
        음량은 유튜브 기준(-14 LUFS)으로 맞춘다.
결과: 같은 폴더에 video.mp4, thumb.jpg
"""
import json
import math
import os
import random
import re
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import visuals as V  # noqa: E402

SIZES = {"short": (1080, 1920), "long": (1920, 1080)}
W, H = SIZES["short"]
FPS = 30
ROOT = Path(__file__).resolve().parent
FONT = str(ROOT / "fonts" / "NanumGothic-ExtraBold.ttf")
CACHE = Path(os.environ.get("ALGO_CACHE", Path.home() / ".cache" / "algobomyeon"))
SHERPA = CACHE / "sherpa-onnx-v1.12.14-linux-x64-shared"
MODEL = CACHE / "vits-mimic3-ko_KO-kss_low"
MELO_PY = CACHE / "melo-venv" / "bin" / "python"
MELO_OK = CACHE / "melo.ok"  # tools/setup.sh가 MeloTTS 설치·시험에 성공했을 때만 생긴다
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
BAND_H = 190  # 롱폼은 make()에서 줄인다
BAR_H = 18
TAIL = 0.45      # 장면 끝 여유(초)
TRANS = 0.28     # 장면 전환(밀어내기) 길이(초)
LINE_GAP = 0.16  # 줄마다 등장 간격(초)
POP = 0.32       # 줄 등장 애니메이션 길이(초)
COUNT = 0.8      # 숫자 카운트업 길이(초)
# 장면마다 돌아가며 쓰는 배경 (위→아래 그라데이션)
PALETTES = [
    ((20, 24, 48), (6, 8, 18)),
    ((44, 16, 52), (10, 4, 16)),
    ((10, 44, 58), (2, 10, 16)),
    ((52, 22, 14), (14, 6, 4)),
]
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


# ───────────────────────── 음성 ─────────────────────────
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
    return wav_seconds(out_wav)


def wav_seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def read_wav(path):
    """모노 float32 배열과 샘플레이트를 돌려준다."""
    with wave.open(str(path)) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    dtype = {2: np.int16, 4: np.int32}[width]
    a = np.frombuffer(raw, dtype=dtype).astype(np.float32) / float(np.iinfo(dtype).max)
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, rate


def write_wav(path, a, rate):
    a = np.clip(a, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def melo_batch(texts, wavs):
    """MeloTTS-Korean으로 한 번에 만든다. 실패하면 False를 돌려 KSS로 되돌린다."""
    if os.environ.get("ALGO_TTS") == "kss" or not MELO_OK.exists():
        return False
    jobs = wavs[0].parent / "melo_jobs.json"
    jobs.write_text(json.dumps([{"text": t, "out": str(w)} for t, w in zip(texts, wavs)],
                               ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([str(MELO_PY), str(ROOT / "melo_tts.py"), str(jobs)], capture_output=True, text=True)
    if r.returncode != 0 or not all(w.exists() for w in wavs):
        print("MeloTTS 실패, KSS 음성으로 대신함:", r.stderr[-500:], file=sys.stderr)
        return False
    return True


def whoosh(rate, length=0.35, seed=0):
    """장면 전환용 '휙' 소리: 잡음을 점점 높은 음역으로 훑는다."""
    rng = np.random.default_rng(seed)
    n = int(rate * length)
    noise = rng.standard_normal(n).astype(np.float32)
    t = np.linspace(0, 1, n, dtype=np.float32)
    # 간단한 1차 저역필터, 차단 주파수를 시간에 따라 올린다
    out = np.empty_like(noise)
    acc = 0.0
    alpha = 0.02 + 0.35 * t ** 1.5
    for i in range(n):
        acc += alpha[i] * (noise[i] - acc)
        out[i] = acc
    env = np.sin(np.pi * t) ** 2
    out *= env
    return out / (np.abs(out).max() + 1e-6)


def pad_music(rate, seconds):
    """저작권 걱정 없는 잔잔한 배경음: 부드러운 화음 4개를 천천히 돌린다(직접 합성)."""
    n = int(rate * seconds)
    t = np.arange(n, dtype=np.float32) / rate
    # C - Am - F - G (Hz)
    chords = [(261.63, 329.63, 392.00), (220.00, 261.63, 329.63),
              (174.61, 220.00, 261.63), (196.00, 246.94, 293.66)]
    bar = 4.0
    out = np.zeros(n, dtype=np.float32)
    for k in range(int(seconds // bar) + 1):
        s = int(k * bar * rate)
        e = min(n, int((k + 1) * bar * rate + 0.6 * rate))
        if s >= n:
            break
        tt = t[s:e] - k * bar
        env = np.minimum(1, tt / 0.8) * np.exp(-np.maximum(0, tt - bar) * 4)
        tone = np.zeros_like(tt)
        for f in chords[k % 4]:
            for h, amp in ((1, 1.0), (2, 0.25), (0.5, 0.35)):
                tone += amp * np.sin(2 * np.pi * f * h * tt)
        out[s:e] += tone * env
    # 느린 흔들림으로 기계음 느낌을 줄인다
    out *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.25 * t)
    fade = np.minimum(1, np.minimum(t / 1.5, (seconds - t) / 1.5)).clip(0, 1)
    out *= fade
    return out / (np.abs(out).max() + 1e-6)


# ───────────────────────── 글자 배치 ─────────────────────────
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


def parse_marks(text):
    """*강조* 표시를 떼어 내고, 글자마다 강조 여부와 숫자 정보를 만든다."""
    clean, hl = [], []
    on = False
    for ch in text:
        if ch == "*":
            on = not on
            continue
        clean.append(ch)
        hl.append(on)
    clean = "".join(clean)
    nums = []
    for m in NUM_RE.finditer(clean):
        s, e = m.span()
        tok = m.group().rstrip(",")
        e = s + len(tok)
        for i in range(s, e):
            hl[i] = True
        # 연도(2014년)는 강조만 하고 세지 않는다
        if re.fullmatch(r"(19|20)\d\d", tok) and clean[e:e + 1] == "년":
            continue
        dec = len(tok.split(".")[1]) if "." in tok else 0
        nums.append({"s": s, "e": e, "val": float(tok.replace(",", "")), "dec": dec, "comma": "," in tok})
    # 숫자 바로 뒤 단위(%, 원, 배, +, 편 …)도 같이 노랗게
    for m in NUM_RE.finditer(clean):
        i = m.end()
        while i < len(clean) and clean[i] in "%+배원개명만억조천분초년월일위편회번점kKmM":
            hl[i] = True
            i += 1
    return clean, hl, nums


def fmt_num(n, p):
    v = n["val"] * p
    if n["dec"]:
        s = f"{v:.{n['dec']}f}"
    else:
        s = f"{int(round(v)):,}" if n["comma"] else str(int(round(v)))
    return s


def ease_out_cubic(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def ease_out_back(p):
    p = min(1.0, max(0.0, p))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


class SceneText:
    """한 장면의 자막: 줄 배치를 한 번 계산하고, 시간(t)에 맞춰 줄 이미지를 그려 준다."""

    def __init__(self, text, hook, area=None):
        """area=(위, 아래): 자막이 들어갈 세로 범위. 없으면 화면 가운데."""
        self.hook = hook
        clean, self.hl, self.nums = parse_marks(text)
        probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        margin = 80 if W < H else 160
        max_h = int((H - BAND_H) * 0.65) if area is None else area[1] - area[0]
        start = (128 if hook else 112) if W < H else (120 if hook else 96)
        if area is not None:
            start = int(start * 0.9)
        self.font, lines, self.line_h = fit_text(probe, clean, W - margin * 2, max_h, start=start)
        self.stroke = max(4, self.font.size // 18)
        # 줄마다 원문 위치를 찾아 둔다
        self.lines = []
        cur = 0
        for ln in lines:
            pos = clean.find(ln, cur)
            if pos < 0:
                pos = cur
            self.lines.append((ln, pos))
            cur = pos + len(ln)
        block_h = self.line_h * len(self.lines)
        if area is None:
            self.top = BAND_H + (H - BAND_H - BAR_H - block_h) // 2
        else:
            self.top = area[0] + (area[1] - area[0] - block_h) // 2
        self._cache = {}

    def base_color(self):
        return YELLOW if self.hook else WHITE

    def hl_color(self):
        return WHITE if self.hook else YELLOW

    def line_start(self, i):
        return (0.05 if self.hook else 0.12) + LINE_GAP * i

    def render_line(self, i, t):
        """i번째 줄을 RGBA 이미지로. 숫자는 t에 맞춰 세어 올린다."""
        ln, pos = self.lines[i]
        p = ease_out_cubic((t - self.line_start(i)) / COUNT)
        counting = [n for n in self.nums if pos <= n["s"] < pos + len(ln)]
        key = (i, round(p, 3) if counting and p < 1 else 1)
        if key in self._cache:
            return self._cache[key]
        # 조각(글자, 강조 여부)으로 나눈다. 숫자 조각은 현재 값으로 바꾼다.
        segs = []
        j = 0
        while j < len(ln):
            gi = pos + j
            num = next((n for n in counting if n["s"] == gi), None)
            if num:
                txt = fmt_num(num, p) if p < 1 else ln[j:j + num["e"] - num["s"]]
                segs.append((txt, True))
                j += num["e"] - num["s"]
                continue
            segs.append((ln[j], self.hl[gi]))
            j += 1
        full_w = int(ImageDraw.Draw(Image.new("RGB", (8, 8))).textlength(ln, font=self.font))
        pad = self.stroke * 2 + 8
        img = Image.new("RGBA", (full_w + pad * 2 + 40, self.line_h + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # 숫자가 세어지는 동안 폭이 달라도 줄이 흔들리지 않게, 최종 폭 기준 가운데에서 시작
        cur_w = sum(d.textlength(s, font=self.font) for s, _ in segs)
        x = pad + (full_w - cur_w) / 2
        for s, h in segs:
            d.text((x, pad), s, font=self.font, fill=self.hl_color() if h else self.base_color(),
                   stroke_width=self.stroke, stroke_fill=(0, 0, 0))
            x += d.textlength(s, font=self.font)
        self._cache[key] = (img, full_w, pad)
        return self._cache[key]

    def draw(self, canvas, t):
        for i in range(len(self.lines)):
            st = self.line_start(i)
            if t < st:
                continue
            img, full_w, pad = self.render_line(i, t)
            a = (t - st) / POP
            scale = 0.55 + 0.45 * ease_out_back(a) if a < 1 else 1.0
            alpha = min(1.0, a * 2.5)
            # 첫 장면은 살짝 숨 쉬듯 커졌다 작아진다
            if self.hook and a >= 1:
                scale = 1 + 0.025 * math.sin(2 * math.pi * 0.6 * (t - st - POP))
            if scale != 1.0:
                img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                                 Image.BILINEAR)
            if alpha < 1:
                r, g, b, al = img.split()
                al = al.point(lambda v: int(v * alpha))
                img = Image.merge("RGBA", (r, g, b, al))
            cy = self.top + i * self.line_h + self.line_h // 2
            x = int(W / 2 - img.width / 2)
            y = int(cy - img.height / 2)
            canvas.alpha_composite(img, (max(0, x), max(0, y)) if x < 0 or y < 0 else (x, y))


# ───────────────────────── 배경 ─────────────────────────
def gradient(top, bottom, w, h):
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        col.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return col.resize((w, h))


def make_background(idx):
    """확대·이동에 쓸 수 있게 화면보다 크게 그린 배경(그라데이션 + 흐릿한 빛 방울)."""
    pal = PALETTES[idx % len(PALETTES)]
    bw, bh = int(W * 1.18), int(H * 1.18)
    img = gradient(*pal, bw, bh).convert("RGBA")
    rng = random.Random(idx * 7 + 3)
    glow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    light = tuple(min(255, c * 3 + 40) for c in pal[0])
    for _ in range(7):
        r = rng.randint(int(min(bw, bh) * 0.08), int(min(bw, bh) * 0.22))
        cx, cy = rng.randint(0, bw), rng.randint(0, bh)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=light + (rng.randint(40, 80),))
    # 노란 포인트 방울 하나
    r = int(min(bw, bh) * 0.12)
    cx, cy = rng.randint(r, bw - r), rng.randint(r, bh - r)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=YELLOW + (38,))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img.alpha_composite(glow)
    # 얇은 대각선 무늬(움직일 때 속도감이 보이게)
    lines = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for x in range(-bh, bw, 90):
        ld.line([(x, bh), (x + bh, 0)], fill=(255, 255, 255, 10), width=3)
    img.alpha_composite(lines)
    return img.convert("RGB")


def background_frame(bg, p, idx):
    """p(0→1)에 따라 천천히 확대(1.0→1.08)하면서 한쪽으로 흐른다."""
    zoom = 1.0 + 0.08 * p
    cw, ch = int(bg.width / 1.18 / zoom * 1.0), int(bg.height / 1.18 / zoom)
    dx = (1 if idx % 2 == 0 else -1)
    cx = bg.width / 2 + dx * (bg.width - cw) * 0.4 * (p - 0.5)
    cy = bg.height / 2 + (bg.height - ch) * 0.3 * (0.5 - p)
    box = (int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))
    return bg.crop(box).resize((W, H), Image.BILINEAR)


# ───────────────────────── 고정 장식(띠·번호·진행 막대) ─────────────────────────
def overlay(canvas, idx, total_scenes, hook, progress):
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, BAND_H], fill=YELLOW)
    bf = ImageFont.truetype(FONT, int(BAND_H * 0.5))
    label = "알고보면"
    d.text(((W - d.textlength(label, font=bf)) / 2, BAND_H * 0.2), label, font=bf, fill=(0, 0, 0))
    nf = ImageFont.truetype(FONT, 40)
    tag = "지금 알려줌" if hook else f"{idx}/{total_scenes - 1}"
    d.text((60, BAND_H + 40), tag, font=nf, fill=YELLOW)
    d.rectangle([0, H - BAR_H, W, H], fill=(60, 60, 60))
    if progress > 0:
        d.rectangle([0, H - BAR_H, max(1, int(W * progress)), H], fill=YELLOW)


def layout():
    """화면 비율별 배치: 자막 칸, 그림 칸, 진행자 크기."""
    if W < H:  # 세로 숏폼
        return {"text": (BAND_H + 100, 800), "vis_c": (W // 2, 1090), "icon": 440,
                "chart": (900, 520), "host": 1.0, "src_y": H - BAR_H - 78}
    return {"text": (BAND_H + 40, 470), "vis_c": (W // 2 + 120, 740), "icon": 330,
            "chart": (900, 420), "host": 0.6, "src_y": H - BAR_H - 70}


class Scene:
    """한 장면: 배경 + 자막 + (그래프 또는 소재 그림) + 출처 꼬리표."""

    def __init__(self, sc, idx, n, visual=True, base=None):
        self.idx, self.n = idx, n
        self.bg = make_background(idx)
        # 실제 촬영 영상(B-roll): shorts/<id>/broll/sNN.mp4 가 있으면 배경으로 쓴다
        self.broll = None
        if base is not None:
            cand = base / "broll" / f"s{idx:02d}.mp4"
            if cand.exists() and cand.stat().st_size > 1000:
                self.broll = cand
        self.reader = None
        self.case = sc.get("case")
        L = layout()
        self.L = L
        self.visual = visual and sc.get("visual", True)
        self.chart = sc.get("chart") if self.visual else None
        self.icon = None
        if self.visual and not self.chart:
            self.icon = sc.get("icon") or V.pick_icon(sc["text"], sc.get("say", ""))
        self.text = SceneText(sc["text"].replace("\u2212", "-").replace("\u00d7", "x"), hook=(idx == 0), area=L["text"] if self.visual else None)
        self.source = sc.get("source")
        self.has_nums = bool(self.text.nums) or bool(self.chart)
        # 실제 영상이 깔린 장면은 사람이 이미 움직이므로 소재 그림·진행자를 뺀다
        if self.broll is not None:
            self.icon = None
        self.host = self.broll is None and not self.case  # 사례 카드와 겹치지 않게
        # 그림은 자막이 다 나온 직후 등장
        self.vis_start = self.text.line_start(len(self.text.lines) - 1) + 0.2

    def pose(self, t):
        if self.idx == self.n - 1:
            return "wave"
        if self.idx == 0:
            return "think" if t < 1.4 else "talk"
        if self.has_nums and self.vis_start - 0.1 < t < self.vis_start + 1.8:
            return "point"
        return "talk"

    def broll_frame(self, dur):
        """실제 영상에서 다음 프레임을 읽어 글자가 잘 보이게 어둡게 깐다."""
        if self.reader is None:
            self.reader = subprocess.Popen(
                [FFMPEG, "-loglevel", "error", "-stream_loop", "-1", "-i", str(self.broll),
                 "-t", f"{dur + 1:.3f}",
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1",
                 "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                stdout=subprocess.PIPE)
            self._last = None
            self._shade = shade_mask()
        raw = self.reader.stdout.read(W * H * 3)
        if len(raw) == W * H * 3:
            a = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 3).astype(np.float32)
            self._last = Image.fromarray((a * self._shade).astype(np.uint8))
        if self._last is None:
            return background_frame(self.bg, 0, self.idx)
        return self._last

    def close(self):
        if self.reader is not None:
            self.reader.stdout.close()
            self.reader.kill()
            self.reader = None

    def frame(self, t, dur):
        if self.broll is not None:
            frame = self.broll_frame(dur).convert("RGBA")
        else:
            frame = background_frame(self.bg, t / max(dur, 0.01), self.idx).convert("RGBA")
        self.text.draw(frame, t)
        cx, cy = self.L["vis_c"]
        land = W > H
        both = bool(self.chart and self.case)
        if land and both:
            # 가로 화면: 그래프는 왼쪽, 사례 카드는 오른쪽에 나란히
            cx = int(W * 0.30)
        if self.chart:
            cw, ch = self.L["chart"]
            if land and both:
                cw = int(W * 0.46)
            img = V.bar_chart(self.chart.get("items", []), t, self.vis_start, cw, ch)
            frame.alpha_composite(img, (cx - cw // 2, cy - ch // 2))
        elif self.icon:
            r = V.icon_frame(self.icon, t, self.vis_start, self.L["icon"])
            if r:
                img, dy = r
                frame.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2 + dy)))
        if self.case:
            if land:
                cw = int(W * 0.42) if both else 1000
            else:
                cw = W - 120
            card, dy = V.case_card(self.case, t, self.vis_start + (0.6 if self.chart else 0), cw)
            if card is not None:
                if land and both:
                    x, y = int(W * 0.54), cy - card.height // 2
                elif self.chart:
                    x, y = (W - card.width) // 2, cy + self.L["chart"][1] // 2 + 30
                else:
                    x, y = (W - card.width) // 2, cy - card.height // 2
                frame.alpha_composite(card, (x, int(y + dy)))
        tag = V.source_tag(self.source, t, self.vis_start + 0.3, W - 480 if W < H else W - 700)
        if tag:
            frame.alpha_composite(tag, (W - tag.width - 36, self.L["src_y"] - tag.height // 2))
        return frame


_SHADE = {}


def shade_mask():
    """실제 영상 위 글자가 잘 보이도록: 전체 55% 밝기 + 위·아래는 더 어둡게."""
    if (W, H) not in _SHADE:
        y = np.linspace(0, 1, H, dtype=np.float32)
        v = 0.62 - 0.30 * np.exp(-((y - 0.0) / 0.28) ** 2) - 0.25 * np.exp(-((y - 1.0) / 0.22) ** 2)
        _SHADE[(W, H)] = np.clip(v, 0.25, 1)[:, None, None]
    return _SHADE[(W, H)]


def scene_frame(bg, text, idx, t, dur):
    """썸네일용: 배경 + 자막만."""
    frame = background_frame(bg, t / max(dur, 0.01), idx).convert("RGBA")
    text.draw(frame, t)
    return frame


def run(args):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True)


def ad_notice(frame, text):
    """쿠팡 파트너스 등 대가성 표시(의장 지시 17번): 화면 아래 작은 자막."""
    d = ImageDraw.Draw(frame)
    size = 30 if W < H else 28
    font = ImageFont.truetype(FONT, size)
    tw = d.textlength(text, font=font)
    x = int(W - tw - 40)  # 오른쪽 위(띠 바로 아래) — 출처 표시·진행자와 겹치지 않게
    y = BAND_H + 16
    d.rounded_rectangle((x - 18, y - 10, x + tw + 18, y + size + 12), radius=12, fill=(0, 0, 0, 175))
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255))


def make(script_path):
    global W, H, BAND_H
    script_path = Path(script_path)
    spec = json.loads(script_path.read_text(encoding="utf-8"))
    W, H = SIZES[spec.get("format", "short")]
    BAND_H = 190 if W < H else 130
    out_dir = script_path.parent
    work = out_dir / ".work"
    work.mkdir(exist_ok=True)
    scenes = spec["scenes"]
    n = len(scenes)

    # 1) 음성
    says = [sc.get("say", sc["text"]).replace("\n", " ").replace("*", "") for sc in scenes]
    wavs = [work / f"s{i:03d}.wav" for i in range(n)]
    voice = "melo" if melo_batch(says, wavs) else "kss"
    durs = []
    for i in range(n):
        d = wav_seconds(wavs[i]) if voice == "melo" else tts(says[i], wavs[i])
        durs.append(d + TAIL)
    starts = np.cumsum([0] + durs[:-1]).tolist()
    total = sum(durs)

    # 2) 소리 합치기: 목소리 + 전환 '휙' + 배경음
    parts, rate = [], None
    for i in range(n):
        a, rate = read_wav(wavs[i])
        need = int(round(durs[i] * rate))
        parts.append(np.pad(a, (0, max(0, need - len(a))))[:need])
    voice_track = np.concatenate(parts)
    fx = np.zeros_like(voice_track)
    wh = whoosh(rate)
    for i in range(1, n):
        s = int(starts[i] * rate) - len(wh) // 2
        s = max(0, s)
        e = min(len(fx), s + len(wh))
        fx[s:e] += 0.22 * wh[:e - s]
    if spec.get("music", True):
        bgm = pad_music(rate, len(fx) / rate)[:len(fx)]
        fx += 0.06 * np.pad(bgm, (0, len(fx) - len(bgm)))  # 길이 반올림 오차 보정
    # 말하는 동안 배경음이 조금 더 작아지게(간단한 덕킹)
    mix = voice_track + fx * (1 - 0.35 * (np.abs(voice_track) > 0.02))
    mixed_wav = work / "mix.wav"
    write_wav(mixed_wav, mix / (np.abs(mix).max() + 1e-6) * 0.9, rate)

    # 3) 화면: 프레임을 직접 그려 ffmpeg에 넘긴다
    V.set_font(FONT)
    visual = spec.get("visuals", True)
    objs = [Scene(sc, i, n, visual=visual, base=out_dir) for i, sc in enumerate(scenes)]
    broll_used = sum(1 for o in objs if o.broll is not None)
    bgs = [o.bg for o in objs]
    host_on = visual and spec.get("presenter", True)
    # 진행자 입 모양용: 프레임마다 목소리 크기(0~1)
    spf = rate / FPS
    frames = int(math.ceil(total * FPS))
    amps = np.zeros(frames, dtype=np.float32)
    for f in range(frames):
        seg = voice_track[int(f * spf):int((f + 1) * spf)]
        amps[f] = float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0
    ref = np.percentile(amps[amps > 0], 90) if np.any(amps > 0) else 1.0
    amps = np.clip(amps / (ref + 1e-6), 0, 1)
    amps = np.maximum(amps, np.concatenate([[0], amps[:-1]]) * 0.6)  # 입이 너무 빨리 닫히지 않게
    video = out_dir / "video.mp4"
    enc = subprocess.Popen(
        [FFMPEG, "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(mixed_wav),
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-maxrate", "8M", "-bufsize", "16M", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k",
         "-shortest", "-movflags", "+faststart", str(video)],
        stdin=subprocess.PIPE,
    )
    prev_i = None
    for f in range(frames):
        t_global = f / FPS
        i = max(k for k in range(n) if starts[k] <= t_global + 1e-9)
        if prev_i is not None and i != prev_i:
            objs[prev_i].close()  # 지난 장면의 실제 영상 리더를 바로 닫는다(롱폼 메모리 부족 방지)
        prev_i = i
        t = t_global - starts[i]
        frame = objs[i].frame(t, durs[i])
        if i > 0 and t < TRANS:
            # 밀어내기 전환: 이전 장면 마지막 모습이 왼쪽으로 빠지고 새 장면이 오른쪽에서 들어온다
            prev = last_frame
            q = ease_out_cubic(t / TRANS)
            off = int(W * (1 - q))
            comp = Image.new("RGBA", (W, H))
            comp.paste(prev, (off - W, 0))
            comp.paste(frame, (off, 0))
            frame = comp
        if i > 0 and t < TRANS:
            pass
        else:
            last_frame = frame.copy()
        if host_on and objs[i].host:
            # 진행자는 전환 때도 제자리에 서서 계속 말한다
            host = V.presenter(t_global, float(amps[f]), objs[i].pose(t), scale=objs[i].L["host"])
            frame.alpha_composite(host, (10, H - BAR_H - host.height + int(40 * objs[i].L["host"])))
        overlay(frame, i, n, i == 0, t_global / total)
        notice = spec.get("adNotice")
        if notice and (t_global < 3.0 or (W > H and t_global > total - 6.0)):
            ad_notice(frame, notice)
        enc.stdin.write(frame.convert("RGB").tobytes())
    for o in objs:
        o.close()
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("영상 인코딩 실패")

    # 4) 썸네일: 첫 장면 스타일, 모든 글자가 다 나온 상태
    thumb_text = SceneText(spec.get("thumbText", scenes[0]["text"]), hook=True)
    th = background_frame(bgs[0], 0.3, 0).convert("RGBA")
    thumb_text.draw(th, 99)
    overlay(th, 0, n, True, 0)
    th.convert("RGB").save(out_dir / "thumb.jpg", quality=90)

    for f in work.iterdir():
        f.unlink()
    work.rmdir()
    info = {"video": str(video), "seconds": round(total, 2), "bytes": video.stat().st_size,
            "voice": voice, "motion": "v2", "broll_scenes": broll_used}
    # 제작 중 자동 품질 검수(사람이 따로 확인하지 않는다): qc.json + qc_sheet.jpg
    import qc
    res = qc.run_qc(script_path, info)
    info["qc"] = "pass" if res["pass"] else "fail"
    info["qc_fail"], info["qc_warn"] = res["fail"], res["warn"]
    print(json.dumps(info, ensure_ascii=False))
    return 0 if res["pass"] else 2


if __name__ == "__main__":
    sys.exit(make(sys.argv[1]))
