"""알고보면 화면 요소: 진행자 캐릭터 '알보', 소재 그림(아이콘), 막대 그래프, 출처 표시.

모두 코드로 직접 그린 자체 창작물이라 저작권 걱정이 없다.
"""
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
INK = (24, 20, 28)
SKIN = (255, 208, 168)
HAIR = (46, 34, 34)
SHIRT = (255, 214, 0)
PANTS = (40, 60, 110)


def _ease_out_back(p):
    p = min(1.0, max(0.0, p))
    c1 = 1.70158
    return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2


def _ease_out_cubic(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


# ───────────────────────── 진행자 '알보' ─────────────────────────
def _arm(d, shoulder, angle_deg, length, width, color, hand=True, elbow=None):
    """어깨에서 각도(0=오른쪽, 90=아래)로 팔을 그린다. elbow가 있으면 두 마디."""
    x0, y0 = shoulder
    if elbow is None:
        a = math.radians(angle_deg)
        x1, y1 = x0 + length * math.cos(a), y0 + length * math.sin(a)
        d.line([(x0, y0), (x1, y1)], fill=color, width=width)
        d.ellipse([x0 - width / 2, y0 - width / 2, x0 + width / 2, y0 + width / 2], fill=color)
        end = (x1, y1)
    else:
        a1 = math.radians(angle_deg)
        mx, my = x0 + length * 0.55 * math.cos(a1), y0 + length * 0.55 * math.sin(a1)
        a2 = math.radians(elbow)
        x1, y1 = mx + length * 0.5 * math.cos(a2), my + length * 0.5 * math.sin(a2)
        d.line([(x0, y0), (mx, my)], fill=color, width=width)
        d.line([(mx, my), (x1, y1)], fill=color, width=width)
        for px, py in ((x0, y0), (mx, my)):
            d.ellipse([px - width / 2, py - width / 2, px + width / 2, py + width / 2], fill=color)
        end = (x1, y1)
    if hand:
        r = width * 0.62
        d.ellipse([end[0] - r, end[1] - r, end[0] + r, end[1] + r], fill=SKIN, outline=INK, width=4)
    return end


def presenter(t, amp, mode, scale=1.0, flip=False):
    """진행자 한 프레임(RGBA). amp=지금 말소리 크기(0~1), mode=talk|point|wave|think."""
    S = 2  # 두 배로 그려 줄이면 가장자리가 부드럽다
    w, h = 460 * S, 560 * S
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bob = math.sin(2 * math.pi * 1.1 * t) * 6 * S
    lean = math.sin(2 * math.pi * 0.35 * t) * 4 * S
    cx = w / 2 + lean
    by = 300 * S + bob  # 어깨 높이

    # 몸통(바지 → 셔츠)
    d.rounded_rectangle([cx - 90 * S, by + 150 * S, cx + 90 * S, h + 40], radius=40 * S, fill=PANTS)
    d.rounded_rectangle([cx - 105 * S, by - 20 * S, cx + 105 * S, by + 200 * S], radius=60 * S,
                        fill=SHIRT, outline=INK, width=5 * S)
    # 셔츠 가운데 '알' 마크
    f = ImageFont.truetype(_font_path(), 54 * S)
    d.text((cx, by + 95 * S), "알", font=f, fill=INK, anchor="mm")

    # 팔: 모드별 동작
    sl, sr = (cx - 98 * S, by + 18 * S), (cx + 98 * S, by + 18 * S)
    arm_w = 36 * S
    swing = math.sin(2 * math.pi * 1.6 * t)
    if mode == "point":
        # 오른팔을 위로 뻗어 자막·그래프를 가리킨다(살짝 톡톡)
        _arm(d, sl, 100 + 6 * swing, 150 * S, arm_w, SHIRT)
        _arm(d, sr, -62 + 5 * math.sin(2 * math.pi * 2.2 * t), 175 * S, arm_w, SHIRT)
    elif mode == "wave":
        _arm(d, sl, 100, 150 * S, arm_w, SHIRT)
        _arm(d, sr, -40, 170 * S, arm_w, SHIRT, elbow=-95 + 28 * math.sin(2 * math.pi * 2.4 * t))
    elif mode == "think":
        _arm(d, sl, 95, 150 * S, arm_w, SHIRT)
        _arm(d, sr, 140, 170 * S, arm_w, SHIRT, elbow=-120)  # 손을 턱으로
    else:  # talk: 말하면서 손을 조금씩 움직인다
        _arm(d, sl, 120 + 12 * swing, 160 * S, arm_w, SHIRT, elbow=60 + 18 * swing)
        _arm(d, sr, 60 - 12 * swing, 160 * S, arm_w, SHIRT, elbow=120 - 18 * swing)

    # 목·머리
    hy = by - 120 * S
    d.rectangle([cx - 24 * S, hy + 70 * S, cx + 24 * S, by], fill=SKIN)
    tilt = math.sin(2 * math.pi * 0.5 * t) * 5 * S
    hx = cx + tilt
    r = 108 * S
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=SKIN, outline=INK, width=5 * S)
    # 머리카락(위쪽 반원 + 앞머리)
    d.chord([hx - r - 6 * S, hy - r - 14 * S, hx + r + 6 * S, hy + r - 30 * S], 180, 360, fill=HAIR)
    d.pieslice([hx - 60 * S, hy - r + 10 * S, hx + 40 * S, hy - 20 * S], 180, 330, fill=HAIR)
    # 귀
    for sx in (-1, 1):
        ex = hx + sx * (r - 4 * S)
        d.ellipse([ex - 18 * S, hy - 10 * S, ex + 18 * S, hy + 30 * S], fill=SKIN, outline=INK, width=4 * S)
    # 눈(3초마다 깜빡)
    blink = (t % 3.1) < 0.12
    brow_up = (10 * S if mode in ("point", "wave") else 0) + 4 * S * amp
    for sx in (-1, 1):
        ex, ey = hx + sx * 40 * S, hy + 8 * S
        if blink:
            d.line([(ex - 13 * S, ey), (ex + 13 * S, ey)], fill=INK, width=5 * S)
        else:
            d.ellipse([ex - 12 * S, ey - 14 * S, ex + 12 * S, ey + 14 * S], fill=INK)
            d.ellipse([ex - 4 * S, ey - 9 * S, ex + 3 * S, ey - 2 * S], fill=WHITE)
        d.line([(ex - 20 * S, ey - 34 * S - brow_up), (ex + 18 * S, ey - 38 * S - brow_up)],
               fill=HAIR, width=6 * S)
    # 볼
    for sx in (-1, 1):
        px = hx + sx * 68 * S
        d.ellipse([px - 18 * S, hy + 38 * S, px + 18 * S, hy + 58 * S], fill=(255, 150, 150))
    # 입: 말소리 크기만큼 벌어진다
    my = hy + 62 * S
    open_h = 4 * S + 34 * S * min(1.0, amp)
    if open_h > 9 * S:
        d.ellipse([hx - 26 * S, my - open_h / 2, hx + 26 * S, my + open_h / 2], fill=(120, 30, 40),
                  outline=INK, width=4 * S)
    else:
        d.arc([hx - 30 * S, my - 26 * S, hx + 30 * S, my + 10 * S], 20, 160, fill=INK, width=6 * S)

    out = img.resize((int(w / S * scale), int(h / S * scale)), Image.LANCZOS)
    if flip:
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    return out


# ───────────────────────── 소재 그림(아이콘) ─────────────────────────
_FONT = {"path": None}


def set_font(path):
    _FONT["path"] = path


def _font_path():
    return _FONT["path"]


def _font(size):
    return ImageFont.truetype(_font_path(), size)


@lru_cache(maxsize=64)
def icon(name, size=420):
    S = 2
    s = size * S
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = 7 * S
    if name == "popcorn":
        # 알갱이
        import random
        rng = random.Random(4)
        for _ in range(26):
            x = rng.uniform(0.24, 0.76) * s
            y = rng.uniform(0.10, 0.36) * s
            r = rng.uniform(0.06, 0.085) * s
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 246, 214), outline=(230, 190, 90), width=3 * S)
        # 통(빨강·흰 줄무늬 사다리꼴)
        top, bot = 0.30 * s, 0.95 * s
        stripes = 6
        for k in range(stripes):
            x0t = 0.18 * s + (0.64 * s) * k / stripes
            x1t = 0.18 * s + (0.64 * s) * (k + 1) / stripes
            x0b = 0.28 * s + (0.44 * s) * k / stripes
            x1b = 0.28 * s + (0.44 * s) * (k + 1) / stripes
            d.polygon([(x0t, top), (x1t, top), (x1b, bot), (x0b, bot)],
                      fill=(226, 44, 52) if k % 2 == 0 else (250, 250, 250))
        d.polygon([(0.18 * s, top), (0.82 * s, top), (0.72 * s, bot), (0.28 * s, bot)], outline=INK, width=lw)
    elif name == "ticket":
        d.rounded_rectangle([0.08 * s, 0.28 * s, 0.92 * s, 0.72 * s], radius=0.05 * s, fill=YELLOW,
                            outline=INK, width=lw)
        for x in (0.08 * s, 0.92 * s):
            d.ellipse([x - 0.07 * s, 0.43 * s, x + 0.07 * s, 0.57 * s], fill=(0, 0, 0, 0), outline=INK, width=lw)
        for yy in range(int(0.32 * s), int(0.68 * s), int(0.05 * s)):
            d.line([(0.68 * s, yy), (0.68 * s, yy + 0.025 * s)], fill=INK, width=4 * S)
        d.text((0.38 * s, 0.5 * s), "입장권", font=_font(int(0.12 * s)), fill=INK, anchor="mm")
        d.text((0.8 * s, 0.5 * s), "1", font=_font(int(0.14 * s)), fill=INK, anchor="mm")
    elif name == "coin":
        for k, (ox, oy) in enumerate(((0.12, 0.10), (0.0, 0.0))):
            x0, y0 = (0.16 + ox) * s, (0.16 + oy) * s
            d.ellipse([x0, y0, x0 + 0.62 * s, y0 + 0.62 * s], fill=(250, 196, 0) if k else (230, 170, 0),
                      outline=INK, width=lw)
        d.ellipse([0.24 * s, 0.24 * s, 0.70 * s, 0.70 * s], outline=(255, 235, 150), width=5 * S)
        d.text((0.47 * s, 0.47 * s), "₩", font=_font(int(0.3 * s)), fill=INK, anchor="mm")
    elif name == "chart":
        base = 0.85 * s
        for k, hh in enumerate((0.25, 0.42, 0.62)):
            x0 = (0.16 + 0.24 * k) * s
            d.rectangle([x0, base - hh * s, x0 + 0.17 * s, base], fill=YELLOW if k == 2 else WHITE,
                        outline=INK, width=lw)
        d.line([(0.1 * s, base), (0.9 * s, base)], fill=WHITE, width=lw)
        d.line([(0.18 * s, 0.5 * s), (0.44 * s, 0.36 * s), (0.62 * s, 0.4 * s), (0.86 * s, 0.14 * s)],
               fill=(255, 90, 90), width=lw * 2 // 2)
    elif name == "comment":
        d.rounded_rectangle([0.08 * s, 0.14 * s, 0.92 * s, 0.70 * s], radius=0.1 * s, fill=WHITE,
                            outline=INK, width=lw)
        d.polygon([(0.26 * s, 0.68 * s), (0.22 * s, 0.9 * s), (0.44 * s, 0.68 * s)], fill=WHITE)
        d.line([(0.26 * s, 0.70 * s), (0.22 * s, 0.9 * s), (0.44 * s, 0.70 * s)], fill=INK, width=lw)
        for k in range(3):
            x = (0.32 + 0.18 * k) * s
            d.ellipse([x - 0.05 * s, 0.37 * s, x + 0.05 * s, 0.47 * s], fill=INK)
    elif name == "store":
        d.rectangle([0.14 * s, 0.40 * s, 0.86 * s, 0.9 * s], fill=(245, 240, 230), outline=INK, width=lw)
        for k in range(6):
            x0 = (0.1 + 0.8 * k / 6) * s
            d.pieslice([x0, 0.26 * s, x0 + 0.8 * s / 6, 0.5 * s], 0, 180,
                       fill=(226, 44, 52) if k % 2 == 0 else WHITE, outline=INK, width=4 * S)
        d.rectangle([0.1 * s, 0.18 * s, 0.9 * s, 0.38 * s], fill=(226, 44, 52), outline=INK, width=lw)
        d.rectangle([0.4 * s, 0.6 * s, 0.6 * s, 0.9 * s], fill=(120, 80, 50), outline=INK, width=lw)
    elif name == "percent":
        d.ellipse([0.1 * s, 0.1 * s, 0.9 * s, 0.9 * s], fill=YELLOW, outline=INK, width=lw)
        d.text((0.5 * s, 0.5 * s), "%", font=_font(int(0.45 * s)), fill=INK, anchor="mm")
    else:  # question
        d.ellipse([0.1 * s, 0.1 * s, 0.9 * s, 0.9 * s], fill=YELLOW, outline=INK, width=lw)
        d.text((0.5 * s, 0.52 * s), "?", font=_font(int(0.55 * s)), fill=INK, anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


ICON_WORDS = [
    ("comment", ["댓글", "알려주세요", "파?", "어때", "여러분"]),
    ("popcorn", ["팝콘", "간식", "매점"]),
    ("ticket", ["티켓", "영화표", "입장권", "영화", "입장"]),
    ("store", ["가게", "매장", "편의점", "식당", "마트"]),
    ("percent", ["%", "퍼센트", "이익률", "금리"]),
    ("coin", ["원", "돈", "값", "가격", "비용", "요금"]),
    ("chart", ["배", "증가", "늘", "올라"]),
]


def pick_icon(text, say=""):
    blob = f"{text} {say}"
    for name, words in ICON_WORDS:
        if any(w in blob for w in words):
            return name
    return "question"


def icon_frame(name, t, start, size):
    """아이콘이 톡 튀어나온 뒤 둥실둥실 떠 있고 살짝 흔들린다."""
    if t < start:
        return None
    p = (t - start) / 0.4
    scale = 0.3 + 0.7 * _ease_out_back(p) if p < 1 else 1.0
    img = icon(name, size)
    ang = math.sin(2 * math.pi * 0.5 * (t - start)) * 6
    if scale != 1.0:
        img = img.resize((max(1, int(size * scale)), max(1, int(size * scale))), Image.BILINEAR)
    img = img.rotate(ang, resample=Image.BICUBIC, expand=True)
    dy = math.sin(2 * math.pi * 0.7 * (t - start)) * 14
    return img, dy


# ───────────────────────── 막대 그래프 ─────────────────────────
def _fmt(v, like):
    dec = len(str(like).split(".")[1]) if "." in str(like) else 0
    if dec:
        return f"{v:.{dec}f}"
    return f"{int(round(v)):,}"


def bar_chart(items, t, start, w, h):
    """items=[[이름, 값, 단위], ...]. 막대가 차례로 자라며 숫자가 세어 올라간다."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t < start:
        return img
    d = ImageDraw.Draw(img)
    # 반투명 판
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=36, fill=(255, 255, 255, 26),
                        outline=(255, 255, 255, 70), width=3)
    n = len(items)
    vmax = max(float(it[1]) for it in items) or 1
    label_f, val_f = _font(40), _font(46)
    top, bottom = 90, h - 90
    slot = (w - 80) / n
    bw = min(170, slot * 0.55)
    for k, it in enumerate(items):
        name, val, unit = it[0], float(it[1]), (it[2] if len(it) > 2 else "")
        p = _ease_out_cubic((t - start - 0.25 * k) / 0.9)
        if p <= 0:
            continue
        bh = (bottom - top) * (val / vmax) * p
        x = 40 + slot * k + (slot - bw) / 2
        color = YELLOW if k == n - 1 else (235, 235, 245)
        d.rounded_rectangle([x, bottom - bh, x + bw, bottom], radius=14, fill=color + (255,))
        d.text((x + bw / 2, bottom - bh - 12), _fmt(val * p, it[1]) + unit, font=val_f,
               fill=WHITE, anchor="mb", stroke_width=4, stroke_fill=(0, 0, 0))
        d.text((x + bw / 2, bottom + 18), name, font=label_f, fill=WHITE, anchor="ma",
               stroke_width=3, stroke_fill=(0, 0, 0))
    d.line([(30, bottom), (w - 30, bottom)], fill=(255, 255, 255, 160), width=4)
    return img


# ───────────────────────── 출처 표시 ─────────────────────────
def source_tag(text, t, start, max_w):
    """'자료: ○○' 꼬리표. 서서히 나타난다."""
    if not text or t < start:
        return None
    a = min(1.0, (t - start) / 0.4)
    f = _font(34)
    label = f"자료: {text}"
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    while probe.textlength(label, font=f) > max_w - 40 and f.size > 24:
        f = _font(f.size - 2)
    tw = int(probe.textlength(label, font=f))
    img = Image.new("RGBA", (tw + 40, f.size + 26), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=img.height // 2,
                        fill=(0, 0, 0, int(150 * a)))
    d.text((20, 12), label, font=f, fill=(255, 255, 255, int(235 * a)))
    return img


# ───────────────────────── 실제 사례 카드 ─────────────────────────
def case_card(case, t, start, w):
    """실제 사례를 기사 요약 카드처럼 보여준다(매체 로고·지면 디자인은 흉내 내지 않는다).
    case = {"headline": "...", "outlet": "한국일보", "date": "2014.06"}"""
    if not case or t < start:
        return None, 0
    p = _ease_out_cubic((t - start) / 0.45)
    hf, sf, lf = _font(54), _font(34), _font(32)
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    inner = w - 80
    words, lines, cur = case["headline"].split(" "), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if probe.textlength(trial, font=hf) <= inner:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    lines = lines[:3]
    h = 40 + 56 + 20 + len(lines) * 70 + 24 + 50 + 30
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=28, fill=(250, 250, 248, 240))
    d.rounded_rectangle([40, 40, 40 + probe.textlength("실제 사례", font=lf) + 36, 96], radius=12,
                        fill=(226, 44, 52))
    d.text((58, 68), "실제 사례", font=lf, fill=WHITE, anchor="lm")
    y = 116
    for ln in lines:
        d.text((40, y), ln, font=hf, fill=INK)
        y += 70
    y += 24
    d.line([(40, y - 12), (w - 40, y - 12)], fill=(210, 210, 210), width=3)
    meta = " · ".join(x for x in (case.get("outlet"), case.get("date")) if x)
    d.text((40, y), meta, font=sf, fill=(110, 110, 120))
    if p < 1:
        r, g, b, a = img.split()
        a = a.point(lambda v: int(v * p))
        img = Image.merge("RGBA", (r, g, b, a))
    return img, int((1 - p) * 80)
