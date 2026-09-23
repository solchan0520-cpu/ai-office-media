# 알고보면 매일 운영 절차

Ark Cornerstone 매일 예약 작업이 따르는 절차. 의장(강솔찬)에게는 출금·긴급 안건만 알린다.

## 도구

```bash
bash tools/setup.sh                       # 음성(현재 sherpa-onnx KSS, 아래 '음성' 참고)·ffmpeg·Pillow 준비 (약 1분)
python3 tools/make_short.py <폴더>/script.json   # video.mp4 + thumb.jpg 생성
```

- 숏폼: `shorts/YYYY-MM-DD-<slug>/script.json` (`"format": "short"`, 25~50초, 장면 6~12개)
- 롱폼: `longs/YYYY-MM-DD-<slug>/script.json` (`"format": "long"`, 18~22분, 장면 150~250개, 장이 바뀔 때 요약 장면)
- `script.json` 형식은 `tools/make_short.py` 맨 위 설명, 예시는 `shorts/2026-09-23-octopus/script.json`
- 자막(`text`)은 짧게, 읽을 문장(`say`)은 숫자를 한글로 풀어 쓴다(예: "3개" → "세 개").
- 화면·목소리·글꼴은 모두 직접 만든 것(글꼴 Nanum Gothic, OFL)만 쓴다. 남의 영상·이미지·음악을 넣지 않는다.

## 음성

- 기본 음성은 **MeloTTS-Korean**(MIT, CPU 실행)으로 한다(`insights/production-quality.voice`).
- 2026-09-23 설치 시도 결과: 모델이 HuggingFace(`myshell-ai/MeloTTS-Korean`)에만 있는데 이 작업 환경에서 HuggingFace 접속이 막혀 설치 실패 → **기존 음성(sherpa-onnx mimic3 KSS)을 유지**하고 `logs`에 남겼다.
- 매주 월요일에 한 번만 `curl -s -o /dev/null -w '%{http_code}' https://huggingface.co/myshell-ai/MeloTTS-Korean/resolve/main/config.json`로 다시 확인한다. 200이면 설치해 `tools/make_short.py`의 음성을 바꾸고, 아니면 KSS를 그대로 쓴다. 다른 우회 경로(미러 등)는 쓰지 않는다.

## 매일 제작 전에 읽을 것

제작을 시작하기 전에 DB `insights/production-quality`와 `insights/marketing-playbook`을 **매일** 읽고 그대로 따른다. 이 절차서와 부딪히면 더 엄격한 쪽을 따른다(예: 해시태그 3개 이하).

- `production-quality`: 말하듯 쓰는 대본(짧은 문장·구어체·끝맺음 다양화, 질문·맞장구), 숫자·영어는 읽는 대로 풀어 쓰기, 문장 사이 쉼·속도 변화, 화면 전환을 쉼에 맞추기, 강조 단어 색, 심의 전 끝까지 듣고 어색한 문장은 고쳐 다시 만들기.
- `marketing-playbook`: 제목 앞 20자에 핵심어, 설명 첫 2줄(요약 + 관련 롱폼 링크 + 구독 한 줄), 첫 3초 훅, 롱폼 초반 30초 예고·끝 20초 다음 영상 추천, 시리즈화, 롱폼 썸네일 규칙. `growthSprint`는 주간 평가·월간 보고에서 조건을 확인한다. `multiPlatform`은 결재 전까지 하지 않는다.
- 지금 도구로 못 하는 항목(효과음·배경음, 고정 댓글, 재생목록 등)은 무료로 가능한 범위에서만 하고, 못 한 것은 `logs`에 한 줄 남긴다. 효과음·배경음은 라이선스가 확인된 무료 자료만 쓴다.

## 요일별 제작량 (한국 시간 기준)

| 요일 | 바이럴 참고 숏폼 | 창작 숏폼(자막형) | 20분 롱폼 |
|---|---|---|---|
| 매일 | 1 | | |
| 화·금 | | 1 | |
| 수·토 | | | 1 |

하루 최대 2편 업로드. 쉬는 요일 없음. 아래 무료 예산이 모자라면 이 표보다 줄인다.

## 무료 원칙과 월 예산

- 돈이 드는 전환(Zapier·vidIQ 유료 요금제 등)은 하지 않는다.
- **Zapier 무료 월 100 task**를 넘지 않게 매월 1일 첫 실행에서 그달 예산을 짜 `setup/zapier`에 `budget: {month, uploads, weeklyChecks, monthlyReport, reserve}`로 기록한다.
  - 업로드 1편 = 1 task, 주간 평가 1회 = 1 task, 월간 의장 보고 확인 = 최대 2 task, 예비 5 task 이상.
- 예산이 모자라면 편수를 줄이고 남은 편의 품질을 올린다. 줄이는 순서: ① 바이럴 참고 숏폼 → ② 창작 숏폼. **롱폼은 수익 창출(시청시간) 핵심이라 마지막까지 유지한다.**
- **vidIQ 무료 크레딧은 잔액 20 아래로 쓰지 않는다.** 쓰기 전 `vidiq_balance`로 확인하고, 20 이하이면 웹 검색으로 대신한다.

## 전 세계 대상 (DB `plan/2027`의 `globalStrategy`를 따른다)

- 매주 월요일 `plan/2027.globalStrategy`를 읽고, 지금은 `phase1Free`(0원 단계)만 적용한다. `phase2Paid`는 결재 전까지 하지 않는다.
- 주제의 **절반 이상**은 세계 공통 관심사(자연·우주·몸·동물·역사·과학 등)로 고른다. `topics`와 `videos`에 `global: true/false`를 적고 주 단위로 비율을 맞춘다.
- 제목·설명은 **한국어 | English** 병기로 새로 쓴다(예: `문어는 심장이 3개? | Octopuses have 3 hearts?`). 해시태그도 한·영을 섞는다.
- 화면 글자는 짧게(한 장면 한 줄~두 줄), 숫자·도표·그림 위주로 만들어 말을 몰라도 이해되게 한다.
- 업로드 시간은 한국 저녁~밤(20~24시, 미국 아침)을 우선한다. 매일 예약이 한국 09:00에 돌기 때문에 지금은 제작 직후 올리고, 채널이 YouTube 파트너가 되어 `publish_at`(파트너 전용)을 쓸 수 있으면 `privacy_status: private` + `publish_at`으로 한국 20~24시 공개를 예약한다.

## 주간 평가 (매주 월요일, 그날 제작 전)

1. `videos`에서 지난 4주 영상 ID를 최대 50개 모은다.
2. Zapier YouTube **Make API GET Request 1회**로 `videos?part=statistics,contentDetails&id=<ID들 쉼표로>`를 가져온다(1 task, `setup/zapier`에 기록).
3. 조회수 기준 잘된 3편·안된 3편을 고르고, 공통점을 뽑는다: 주제 분야, 첫 3초 훅, 전개 방식, 스타일(`videos.style`), 길이, 올린 시간.
4. `insights/YYYY-Www`(ISO 주차, 예: `2026-W40`)에 `{week, createdAt, sampleSize, top:[{id, views, ...}], bottom:[...], patterns:{more:[..], less:[..]}, note}`로 기록한다.
5. 숫자는 API가 준 값만 쓴다. 지난 4주 영상이 5편 미만이면 `note: "표본 부족"`으로 기록만 하고 공식은 바꾸지 않는다.
6. 그 주의 주제·스타일은 **최신 `insights`를 먼저 읽고** 잘된 공식은 늘리고 안된 공식은 줄인다(스타일 중복 금지 규칙은 그대로 지킨다).

## 순서

1. **조사(트렌드리서치팀)** — `topics`에 오늘 주제를 쌓는다.
   - 바이럴 참고: vidIQ(`vidiq_outliers`, `vidiq_trending_videos`)로 잘 된 영상의 *공식*(첫 3초 질문, 숫자 목록, 반전, 시리즈)만 뽑는다. 내용·대본·장면은 베끼지 않는다. vidIQ 크레딧은 하루 10 이하, 잔액 20 아래로는 쓰지 않고 웹 검색.
   - 주제는 제한 없음. 단 불법·저작권 침해·혐오·확인 안 된 사실·실존 인물 비방·의료/투자 조언은 뺀다.
   - 모든 사실은 서로 다른 출처 2곳 이상에서 확인한다(백과사전, 공공기관, 학술·언론). 출처 URL을 `sources`와 영상 설명에 넣는다.
   - `videos` 컬렉션을 보고 이미 다룬 주제는 피한다.
   - **바이럴 → 롱폼 연결**: 바이럴에서는 주제와 첫 3초 공식만 가져오고 내용·화면·음악은 쓰지 않는다. 바이럴 주제 중 20분 롱폼으로 깊게 풀 수 있는 것을 우선 고르고, `topics`에 `longCandidate`(연결될 롱폼 후보 주제)를 같이 적는다. 채널 성격("알고 보면 재밌는 사실")에 안 맞는 유행은 고르지 않는다.
   - 숏폼을 올릴 때 관련 롱폼이 이미 있으면 설명란에 그 롱폼 링크를 넣는다. 롱폼이 나중에 올라가면 이미 올린 숏폼은 고치지 않고(기존 영상 수정 금지) 롱폼 설명란에 관련 숏폼 링크를 넣는다. `videos`에 `relatedLong`/`relatedShorts`로 기록한다.
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
- 채널 통계 조회(월간 의장 보고가 월 2회 이내로 한다). 단, 월요일 주간 평가의 Make API GET 1회는 예외.
- 유료 요금제 전환·결제
- 돈이 드는 일·긴급 사항은 직접 하지 않고 `approvals`에 다음 H-번호로 올린 뒤 의장에게 알린다.
