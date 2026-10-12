"""업로드용 자막 트랙(ko.srt·en.srt) 만들기 — 기준서 9장 '자막 트랙'.
장면 시간은 제작기와 같게(음성 길이 + TAIL) 잡고, 장면 안에서는 문장 길이 비율로 나눈다.
en은 script.json 장면별 "say_en"(사람이 쓴 짧은 영어 문장)을 쓴다. 줄당 42자 이하로 줄바꿈.
사용법: python3 tools/make_srt.py <script.json>  → 같은 폴더에 ko.srt, en.srt"""
import json, re, sys, textwrap, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_short import TAIL  # noqa: E402


def wav_sec(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def sentences(text):
    parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", text) if p.strip()]
    return parts or [text]


def cues(scenes, durs, key, width):
    out, t = [], 0.0
    for sc, d in zip(scenes, durs):
        sents = sentences(sc.get(key) or "")
        total = sum(len(s) for s in sents) or 1
        st = t
        for s in sents:
            dd = (d - TAIL) * len(s) / total
            out.append((st, st + dd, "\n".join(textwrap.wrap(s, width)) or s))
            st += dd
        t += d
    return out


def write(path, items):
    path.write_text("".join(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(items, 1)),
                    encoding="utf-8")


def main(script):
    s = Path(script); spec = json.loads(s.read_text(encoding="utf-8"))
    vdir = s.parent / ".work" if (s.parent / ".work" / "s000.wav").exists() else s.parent / "voice"
    durs = [wav_sec(vdir / f"s{i:03d}.wav") + TAIL for i in range(len(spec["scenes"]))]
    write(s.parent / "ko.srt", cues(spec["scenes"], durs, "say", 24))
    if all(sc.get("say_en") for sc in spec["scenes"]):
        write(s.parent / "en.srt", cues(spec["scenes"], durs, "say_en", 42))
    print(f"srt: {len(durs)}장면 {sum(durs):.1f}초 → ko.srt" + (", en.srt" if (s.parent / 'en.srt').exists() else ""))


if __name__ == "__main__":
    main(sys.argv[1])
