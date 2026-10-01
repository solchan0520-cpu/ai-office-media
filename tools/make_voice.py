#!/usr/bin/env python3
"""GitHub Actions(tts 워크플로)에서 돈다: 대본의 장면별 say를 MeloTTS-Korean으로 읽어
<폴더>/voice/sNNN.wav 와 manifest.json({장면번호: say 해시})을 만든다.
제작기(make_short.py)는 해시가 지금 대본과 모두 맞을 때만 이 목소리를 쓴다."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def say_of(sc):
    return sc.get("say", sc["text"]).replace("\n", " ").replace("*", "")


def say_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def main(script_path):
    script_path = Path(script_path)
    spec = json.loads(script_path.read_text(encoding="utf-8"))
    out = script_path.parent / "voice"
    out.mkdir(exist_ok=True)
    says = [say_of(sc) for sc in spec["scenes"]]
    jobs = [{"text": t, "out": str(out / f"s{i:03d}.wav")} for i, t in enumerate(says)]
    jp = out / "jobs.json"
    jp.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, str(Path(__file__).parent / "melo_tts.py"), str(jp)], check=True)
    jp.unlink()
    manifest = {str(i): say_hash(t) for i, t in enumerate(says) if (out / f"s{i:03d}.wav").exists()}
    (out / "manifest.json").write_text(json.dumps({"engine": "melo", "scenes": manifest}, indent=1), encoding="utf-8")
    print(json.dumps({"id": spec.get("id"), "voiced": len(manifest), "scenes": len(says)}))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
