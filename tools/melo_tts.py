#!/usr/bin/env python3
"""MeloTTS-Korean(MIT) 음성 생성기. melo-venv의 python으로 실행한다.

사용법: <melo-venv>/bin/python tools/melo_tts.py jobs.json
jobs.json: [{"text": "읽을 문장", "out": "/path/s000.wav"}, ...]
문장 단위로 만들어 속도를 0.95~1.05로 조금씩 바꾸고, 문장 사이에 쉼을 넣어 이어 붙인다.
모델은 처음 한 번만 올린다.
"""
import json
import random
import re
import sys

import numpy as np
import soundfile as sf
from melo.api import TTS


def sentences(text):
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p for p in parts if p]


def pause_after(sentence):
    # 질문·반전 앞은 길게, 나머지는 0.25~0.45초
    if sentence.endswith("?") or sentence.endswith("…"):
        return 0.6
    return random.uniform(0.25, 0.45)


def main(jobs_path):
    jobs = json.load(open(jobs_path, encoding="utf-8"))
    model = TTS(language="KR", device="cpu")
    spk = model.hps.data.spk2id["KR"]
    sr = model.hps.data.sampling_rate
    random.seed(0)
    for job in jobs:
        chunks = []
        for s in sentences(job["text"]):
            audio = model.tts_to_file(s, spk, None, speed=random.uniform(0.95, 1.05), quiet=True)
            chunks.append(audio)
            chunks.append(np.zeros(int(sr * pause_after(s)), dtype=audio.dtype))
        if chunks:
            chunks.pop()  # 마지막 쉼은 make_short.py가 넣는다
        sf.write(job["out"], np.concatenate(chunks) if chunks else np.zeros(sr // 2), sr, subtype="PCM_16")


if __name__ == "__main__":
    main(sys.argv[1])
