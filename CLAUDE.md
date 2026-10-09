# KNU AUDIO 작업 안내

## 프로젝트 목적과 일정

경북대학교 2027학년도 신입생이 학교·학과 소식을 등굣길에 들을 수 있도록 매일 아침 짧은 오디오 브리핑을 제공한다. 생성형 AI 해커톤 프로젝트이며 최종 제출 시각은 2026-10-31 23:59 (Asia/Seoul)이다. 2026-10-27부터 새 기능을 추가하지 않고 안정화·발표 준비에 집중한다.

## 시작 순서

- 프로젝트 개요와 현재 사용자 흐름은 [README](README.md)를 읽는다.
- 데이터 입력·출력 필드 변경은 먼저 [데이터 계약](docs/contracts.md)과 관련 구현을 함께 확인한다.
- 수집 동작은 [수집 운영](docs/operations.md), 대본·음성은 [Kaggle 브리핑](docs/briefing-kaggle.md), 화면 재생 형식은 [플레이리스트 계약](docs/briefing-playlist-v2.md)을 기준으로 한다.
- 이 저장소는 공개 저장소다. 커밋·PR·Actions 로그·artifact는 누구나 볼 수 있으므로 새 자료를 올리기 전에 [공개 준비 점검](docs/public-readiness.md)의 개인정보·라이선스 기준을 확인한다.

## 현재 구성

- `collector/`: 경북대 공지 수집, JSON 저장소, 날씨·학사일정 수집, 앱용 데이터 생성.
- `data/db/notices.json`: 누적 공지와 확인 기록. `data/raw/<날짜>/items.json`은 브리핑 입력 스냅샷이다.
- `briefing/`: SLM 대본 생성, 규칙 기반 검수, Qwen3 TTS, 앱용 음성 결과 내보내기.
- `.github/workflows/collect.yml`: 수집과 선택적 Kaggle 브리핑 연결.
- `.github/workflows/briefing-kaggle.yml`: 지정된 입력 스냅샷을 Kaggle의 비공개 T4 커널에 보내 대본·음성을 생성하고 검증한다. 게시 입력(`publish`)은 기본적으로 켜져 있어 완료된 음성을 앱에 자동 게시한다.
- `tools/knua-app.html` 및 `web/player/`: 브라우저 화면과 플레이어.
- `output/app/`: GitHub Pages(`.github/workflows/deploy.yml`)가 제공하는 정적 앱 데이터. `output/app/data/briefing/segments.json`에는 생성된 대본·카드·음성 참조가 있다.

학교 수집은 GitHub Actions에서 실행한다. 식당 6곳 식단은 로컬에서 주간 갱신한다. Kaggle 브리핑은 수집 뒤 저장소 변수 `ENABLE_KAGGLE_BRIEFING=true`를 설정한 경우에만 자동 연결한다. 매일 한국시간 01:07에 cron-job.org가 `workflow_dispatch`로 수집을 요청한다. GitHub 자체 수집 예약과 `ENABLE_COLLECTION` 조건은 제거했으며 외부 예약 또는 실행 서버 대기는 발생할 수 있다. 현재 사이트 호스팅은 GitHub Pages(https://hoyeol903.github.io/KNU-AUDIO-public/)다.

## 데이터와 검수 원칙

- 날짜, 시간, 장소, 대상은 원문과 수집 입력에서 확인된 범위만 사용한다. 정상적인 자료 없음과 수집 실패를 구분한다.
- 공지 마감 날짜는 `collector.deadlines.extract_deadline` 결과가 원문에서 단일 날짜를 확인하고 저장된 deadline 필드와 일치할 때만 대본의 확인된 날짜로 취급한다. 이 검사는 정규식·필드 비교 기반이며 문장의 모든 의미를 검증하지 않는다. 참가 대상·장소·조건 등도 별도 완전 검증 대상이 아니다. 관련 한계는 `docs/briefing-integration.md`에 기록한다.
- `items.json`은 수집기와 브리핑 사이의 데이터 계약이다. DB나 전달 구조를 바꾸기 전 사용처·테스트·계약 문서를 확인한다.
- 저장용 JSON은 `collector/store.py`를 통한다. 파서 테스트는 저장된 fixture로 실행하고 수집을 테스트 목적으로 호출하지 않는다.

## 개발·검증

- Python 3.11 이상을 사용한다. 의존성은 `requirements.txt`와 `requirements-tts.txt`에 둔다. 새 의존성은 필요성과 근거를 설명하고 사용자 확인을 받은 뒤 추가한다.
- 학교 사이트를 요청하는 수집기는 요청 사이 1초 이상 간격, 명시적 User-Agent, 최대 2회 재시도를 지킨다. 사이트 선택자는 파일 상단의 상수로 모은다. 구조 변경을 점검하는 테스트는 저장 HTML fixture로 작성하고 실제 사이트에 요청하지 않는다.
- 일부 출처가 실패해도 성공 자료를 보존하고 실패를 `errors`/실행 보고서에 남긴다. 파일은 임시 파일에 쓴 뒤 원자 교체하며 JSON은 `ensure_ascii=False`, 들여쓰기 2칸, 키 정렬을 유지한다.
- 한 달 프로젝트에서는 동작하는 완성·배포와 정확성이 우선이다. 요청되지 않은 추상화·기능을 추가하지 않는다.
- 수집/브리핑 오프라인 검사:

```bash
python -m pytest -q -p no:cacheprovider collector/tests briefing/tests
node collector/tests/test_daily_bgm_player.mjs
```

- `python -m collector.run`과 `python -m tools.update_meals`는 실제 외부 사이트에 요청하고 자료를 갱신할 수 있다. 브리핑 생성은 SLM/TTS 모델 실행과 파일 생성을 일으킨다. 사용자 요청에 포함되지 않으면 실행하지 않는다.
- API 토큰은 GitHub Secrets 또는 로컬 `.env`로 전달하며 코드·로그·문서에 값을 쓰지 않는다. `.env`와 모델 가중치를 커밋하지 않는다.
- 기능 작업은 별도 `feat/...` 브랜치에서 수행하고 PR로 `main`에 반영한다. 운영 워크플로의 데이터 자동 커밋은 예외다.
- 커밋 메시지는 한국어로 쓴다. 작업이 끝나면 변경 내용, 실행 방법과 테스트 결과를 짧게 알린다.
- 기존 비공개 저장소 `KNU-AUDIO`의 Git 이력·PR·Actions 기록·artifact를 이 저장소로 옮기지 않는다. 과거 이력에는 권리가 확인되지 않은 음악 파일과 가리기 전 자료가 있다.

## 공개 자료와 원문 대조

운영 저장소는 `hoyeol903/KNU-AUDIO-public`이며, 기존 저장소는 비공개 기록 보관용입니다. `collector/privacy.py`가 저장 전에 명시적 학번·주민등록번호·010 휴대전화와 학번에 연결된 성명을 `[개인정보 가림]`으로 대체합니다. 날짜·마감·장소·조건과 공식 부서 연락처는 유지합니다. 검수 기준은 개인정보를 가린 원문입니다. items.json과 DB 필드는 변경하지 않으며, 저장된 내용 해시는 가린 내용으로 계산합니다. 가림 표시는 사실 정보로 읽거나 대본에 넣지 않습니다. 새 개인정보 형태는 사람이 검토하며, 자동 가림만으로 공개 적합성을 보증하지 않습니다.
