# 알고보면 매일 운영 절차

Ark Cornerstone 매일 예약 작업이 따르는 절차. 의장(강솔찬)에게는 출금·긴급 안건만 알린다.

## 도구

```bash
bash tools/setup.sh                       # 음성(sherpa-onnx KSS)·ffmpeg·Pillow 준비 (약 1분)
python3 tools/make_short.py <폴더>/script.json   # video.mp4 + thumb.jpg 생성
```

- 숏폼: `shorts/YYYY-MM-DD-<slug>/script.json` (`"format": "short"`, 25~50초, 장면 6~12개)
- 롱폼: `longs/YYYY-MM-DD-<slug>/script.json` (`"format": "long"`, 18~22분, 장면 150~250개, 장이 바뀔 때 요약 장면)
- `script.json` 형식은 `tools/make_short.py` 맨 위 설명, 예시는 `shorts/2026-09-23-octopus/script.json`
- 자막(`text`)은 짧게, 읽을 문장(`say`)은 숫자를 한글로 풀어 쓴다(예: "3개" → "세 개").
- 화면·목소리·글꼴은 모두 직접 만든 것(글꼴 Nanum Gothic, OFL)만 쓴다. 남의 영상·이미지·음악을 넣지 않는다.

## 요일별 제작량 (한국 시간 기준)

| 요일 | 바이럴 참고 숏폼 | 창작 숏폼(자막형) | 20분 롱폼 |
|---|---|---|---|
| 매일 | 1 | | |
| 화·금 | | 1 | |
| 수·토 | | | 1 |

하루 최대 2편 업로드. 쉬는 요일 없음.

## 순서

1. **조사(트렌드리서치팀)** — `topics`에 오늘 주제를 쌓는다.
   - 바이럴 참고: vidIQ(`vidiq_outliers`, `vidiq_trending_videos`)로 잘 된 영상의 *공식*(첫 3초 질문, 숫자 목록, 반전, 시리즈)만 뽑는다. 내용·대본·장면은 베끼지 않는다. vidIQ 크레딧은 하루 10 이하, 부족하면 웹 검색.
   - 주제는 제한 없음. 단 불법·저작권 침해·혐오·확인 안 된 사실·실존 인물 비방·의료/투자 조언은 뺀다.
   - 모든 사실은 서로 다른 출처 2곳 이상에서 확인한다(백과사전, 공공기관, 학술·언론). 출처 URL을 `sources`와 영상 설명에 넣는다.
   - `videos` 컬렉션을 보고 이미 다룬 주제는 피한다.
2. **기획·제작(기획·작가팀 → 숏폼/롱폼제작팀)** — 대본을 `script.json`으로 쓰고 제작기를 돌린다. 결과 화면 1~2장을 뽑아 눈으로 확인한다.
3. **심의(CLO 심의팀)** — 아래를 모두 통과해야 올린다. 하나라도 실패하면 고치거나 그날은 건너뛴다.
   - 사실마다 출처 2개 이상 / 남의 저작물 없음 / 혐오·선정·폭력·위험 행동 없음 / 광고 친화 / 제목이 내용과 맞음(낚시 금지) / 아동용 아님
   - **스타일 중복 금지**: 화면 구성·전개 방식(질문/반전/순위/비교/이야기)·말투를 `videos`의 최근 7편과 겹치지 않게 바꾸고, 업로드 후 `videos/<youtubeId>`에 `style: {layout, structure, tone}`으로 기록한다.
   - **내용 깊이**: 편마다 '왜 그런지' 설명·수치 비교·생활 예시 중 2개 이상을 넣는다.
   - **그림 자료**: 도표·지도는 직접 만든 것만 쓴다.
   - **새로 쓰기**: 제목·설명·해시태그는 편마다 새로 쓴다(참고 영상이나 이전 편의 문구 재사용 금지).
   - **롱폼 화면 변화**: 같은 화면을 30초 넘게 이어서 보여주지 않는다.
   - 위 항목 중 하나라도 지키지 못한 편은 올리지 않는다.
4. **업로드(배포운영팀)** — 영상 폴더를 커밋·푸시한 뒤, 커밋 SHA로 공개 주소를 만든다:
   `https://raw.githubusercontent.com/solchan0520-cpu/ai-office-media/<SHA>/<폴더>/video.mp4`
   (curl로 200 확인 후) Zapier YouTube `upload_video`, 연결 `02d1c0dc-489c-85a7-9bff-88a7c9c75495`, `privacy_status: public`, `made_for_kids: false`, `language_code/default_language/default_audio_language: ko`.
   - 한도: `setup/zapier` 문서로 센다. 24시간 업로드 5편, 월 100 task. 월 90 task를 넘으면 그달 업로드를 멈추고 로그만 남긴다. 월이 바뀌면 `month`·`tasks`를 새로 시작한다.
   - 영상 커밋은 `claude/epic-volta-6tcf65` 브랜치에 푸시한다(영상 보관용, 새 PR은 만들지 않는다).
5. **기록** — `videos/<youtubeId>`, `logs/<오늘>`(시각은 한국 시간, 부서명), `setup/zapier`, `kpi/current`(`videosPublished`, `channels.adult.shorts`, `channels.adult.long`). 회의는 규정상 필요할 때만 `meetings`에 남긴다. 모든 쓰기는 읽은 `version`으로 `if_version`을 건다.

## 하지 않는 것

- 결제, 계정 생성, 삭제, 비공개 시험 영상 공개 전환
- 채널 통계 조회(월간 의장 보고가 월 2회 이내로 한다)
- 돈이 드는 일·긴급 사항은 직접 하지 않고 `approvals`에 다음 H-번호로 올린 뒤 의장에게 알린다.
