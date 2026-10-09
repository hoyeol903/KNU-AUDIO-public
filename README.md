# 크누아 KNU AUDIO

**경북대 새내기에게 매일 필요한 소식을 짧은 음성 브리핑으로 전합니다.** 개인별 브리핑은 1~2분을 목표로 하며, 선택한 게시판과 공지 수에 따라 실제 길이는 달라집니다.

경북대학교 공지·날씨·학사일정과 학식 정보를 모아, 학생이 고른 학과와 식당에 맞는 브리핑을 보여주는 프로젝트입니다. 공지 수집은 GitHub Actions에서 매일 실행하고, 여섯 식당의 식단은 로컬에서 주간 자료를 갱신합니다. 음성 브리핑과 웹 앱은 GitHub Pages에서 확인할 수 있습니다.

## 현재 상태

| 기능 | 상태 | 설명 |
|---|---|---|
| 공지 수집 | 운영 중 | 고유 게시판 136개를 139개 논리 채널로 매일 확인합니다. |
| 날씨·학사일정 | 운영 중 | 공지 수집과 함께 자동으로 갱신합니다. |
| 식당 6곳 | 로컬 주간 갱신 | 생협 사이트를 자동 수집하지 않습니다. 로컬 명령이 자료를 갱신하고 PR을 만듭니다. |
| 대본·음성 | 구현 및 GPU 실행 | Kaggle T4에서 Qwen3-TTS 1.7B CustomVoice로 음성을 만듭니다. 여성 Sohee에는 안정된 아침 라디오 지시를 적용합니다. 실제 전체 실행 시간은 입력과 처리량에 따라 달라집니다. |
| 웹 앱 | 배포 중 | [hoyeol903.github.io/KNU-AUDIO-public](https://hoyeol903.github.io/KNU-AUDIO-public/)에서 수집 현황, 학과 선택, 다른 학과 게시판 선택, 식당 선택, 음성 브리핑을 제공합니다. |

## 데이터 흐름

```text
경북대 게시판 ─┐
날씨·일정 ─────┼─▶ collector ─▶ data/db/ 및 data/raw/<날짜>/
               │                       │
여섯 식당 ─────┘ 로컬 주간 수집          ├─▶ items.json ─▶ Kaggle 대본·음성
                                       └─▶ collector.export_app
                                             output/app/
                                                  │
                                                  └─▶ GitHub Pages
```

- `data/db/notices.json`: 누적 공지와 확인 기록
- `data/raw/<날짜>/items.json`: 해당 날짜 브리핑 입력
- `data/raw/<날짜>/context.json`: 날씨·식단·학사일정 등 출처별 자료
- `output/app/`: 웹 앱과 화면에 필요한 데이터. 음성·대본은 `output/app/data/briefing/`에 저장됩니다.
- `data/runs/`: 실행별 수집·음성 처리 보고서

## 시작과 검사

Python 3.11 이상이 필요합니다.

```bash
git clone https://github.com/hoyeol903/KNU-AUDIO-public.git
cd KNU-AUDIO-public
python -m pip install -r requirements.txt
python -m pytest -q collector/tests briefing/tests
```

아래 전체 수집 명령은 인터넷에 실제 요청을 보냅니다. 학교 필수 게시판 전체와 날씨·학사일정을 가져와 오늘 입력을 저장합니다. 여섯 식당은 요청하지 않습니다.

```bash
python -m collector.run --all-required --write-items --collect-extras --skip-meals
```

저장된 자료로 웹 앱 파일을 다시 만들고 로컬에서 보려면:

```bash
python -m collector.export_app
python -m http.server 8000 --directory output/app
```

브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000)을 엽니다. 첫 명령은 저장된 자료만 사용하며 학교 사이트에 요청하지 않습니다.

## 공지 수집과 실패 재수집

매일 한국시간 01:07에 cron-job.org가 GitHub Actions의 `매일 경북대 자료 수집` 워크플로를 실행하도록 요청합니다. 수집은 기존 GitHub 실행 서버에서 진행하며 GitHub 자체 예약은 제거했습니다. 외부 예약이나 실행 서버 대기는 발생할 수 있어 정각 시작을 보장하지는 않습니다. 토큰 갱신과 예약 중지 방법은 [수집 운영](docs/operations.md)을 참고하세요.

공지 목록은 최근 30일을 확인합니다. 최근 7일 글의 본문은 매 실행 확인하고, 그보다 오래된 일반 글은 마지막 본문 확인 후 7일이 지나면 다시 확인합니다. 새 글·상단 고정 글·제목이나 날짜가 바뀐 글·마감이 남은 글·본문 확인이 필요한 글은 별도로 다시 확인합니다. 오늘 본문을 확인하지 못한 선정 후보와 이미 마감한 글은 브리핑에서 제외합니다. 오늘 새로 확인한 최근 공지와 마감 3일 전·1일 전·당일 알림을 입력에 담습니다.

실패한 게시판은 GitHub Actions에서 같은 워크플로를 수동 실행하고 `collection_mode`를 `retry_failed`로 선택해 다시 수집할 수 있습니다. 필요하면 이전 실행 보고서 경로도 지정합니다. 로컬에서는 다음 명령을 사용할 수 있습니다.

```bash
python -m collector.run --retry-failed --write-items
python -m collector.run --retry-failed --write-items --retry-report data/runs/<이전-보고서>.json
```

수집 결과와 실패 게시판 정보는 실행 보고서, Actions 결과 파일, `output/app/data/collection-failures.csv`에 남습니다. GitHub 이슈 댓글로 결과를 알리며, 이메일 수신은 각 사용자의 GitHub 알림 설정에 따릅니다.

## 주간 학식 갱신

매주 월요일 오전 9시(한국시간)에 GitHub 이슈 알림이 옵니다. 여섯 식당의 식단 수집은 로컬에서만 합니다. 다음 명령은 식단 수집, 앱 파일 내보내기, 새 브랜치 push, PR 생성을 진행합니다. PR 병합은 직접 해야 합니다.

```bash
python -m tools.update_meals
```

실행 전 작업 폴더가 깨끗한지, `gh`에 로그인했는지, `origin`이 이 저장소를 가리키는지 확인하세요. 생협 사이트에 실제 요청을 보냅니다. 이 명령은 식단 화면을 갱신하며, `items.json` 재생성이나 음성 생성은 하지 않습니다.

## Kaggle 음성 브리핑

`Kaggle GPU 브리핑 생성` 워크플로는 커밋된 날짜별 수집 자료를 사용해 Kaggle T4에서 대본과 음성을 생성하고 결과를 검증합니다. 수동 실행에서도 `publish`는 기본적으로 켜져 있습니다. 생성이 완료되면 최신 음성을 자동 게시하며, GitHub 대기가 중단돼도 별도 작업이 완료 결과를 가져옵니다. 수집 완료 후 자동 생성·게시를 연결하려면 저장소 변수 `ENABLE_KAGGLE_BRIEFING=true`를 설정합니다. Kaggle 인증은 저장소 Secret `KAGGLE_API_TOKEN`을 사용하며 토큰 값은 코드나 로그에 넣지 마세요.

음성 파일은 `output/app/data/briefing/`에 들어갑니다. 최근 관측된 실행은 약 17~18분 걸렸습니다. 이 시간은 참고 기록이며 다음 실행의 소요 시간을 보장하지 않습니다.

## 웹 미리보기와 배포

실서비스는 [https://hoyeol903.github.io/KNU-AUDIO-public/](https://hoyeol903.github.io/KNU-AUDIO-public/)입니다. 화면은 학과와 게시판을 고르고 다른 학과 공지와 여섯 식당 중 원하는 식당을 함께 볼 수 있으며, 생성된 음성 브리핑을 재생합니다.

`.github/workflows/deploy.yml`은 `output/app/index.html`과 `output/app/data/`를 GitHub Pages에 올립니다. 앱 자료를 바꾼 기본 브랜치 push, 공지 수집 워크플로 완료, 또는 Actions의 `GitHub Pages 배포` 수동 실행으로 배포합니다. 저장소 Settings → Pages의 Source를 GitHub Actions로 설정합니다. 홈페이지 배포에 별도 API 키는 필요하지 않습니다. 교류의 상세 소개·참가 링크·예시 양식을 추가했으며, 실제 모집글 공유·신청은 별도 API와 DB를 연결해야 합니다. [교류 연결 안내](docs/community.md)를 참고하세요.

하루 배경음악은 Kevin MacLeod의 Incompetech 공식 원본 MP3 30곡(CC BY 4.0) 중 하루 한 곡을 앱에 포함합니다. 출처 카탈로그와 원본 보관 안내는 [하루 배경음악](docs/daily-bgm.md)을 참고하세요.

## 협업 문서

| 담당 | 작업 |
|---|---|
| 이호열 | 공지 수집기와 데이터 저장 |
| 김경민 | 브리핑 대본·음성 |
| 박정원 | 웹 서비스 |

개발은 `feat/<카드번호>-<이름>` 브랜치에서 진행하고 PR로 `main`에 반영합니다. 개발 코드를 `main`에 직접 push하지 않으며 커밋 메시지는 한국어로 작성합니다. 운영 결과 파일의 자동 커밋은 별도입니다. 데이터 형식 변경은 팀과 합의한 뒤 `docs/contracts.md`부터 수정합니다.

- [공지 수집·채널 선택·재수집](docs/collection.md)
- [운영과 실패 확인](docs/operations.md)
- [날씨·학식·학사일정 및 학식 갱신](docs/daily-sources.md)
- [대본·음성 생성과 Kaggle 실행](docs/briefing-kaggle.md)
- [화면과 데이터 계약](docs/contracts.md)
- [정적 앱 로컬 미리보기](docs/app-test.md)

`.env`와 API 토큰 등 비밀 값은 저장소에 올리지 마세요.

## 라이선스

이 저장소의 코드는 [MIT 라이선스](LICENSE)를 따릅니다. 다음 자료에는 MIT 라이선스가 적용되지 않습니다.

- 배경음악(`assets/bgm/`): Kevin MacLeod, CC BY 4.0. 곡별 출처는 `assets/bgm/catalog.json`에 있습니다.
- 수집한 공지·학식·학사일정 자료와 테스트용 저장 페이지(`data/`, `output/app/data/`, `collector/tests/fixtures/`): 원 게시 기관의 자료입니다.
- 호반우 캐릭터와 학교 상징 이미지(`tools/hobanu/`, `tools/avatars/`, `tools/branding/`, `output/app/data/` 아래 사본): 별도 권리가 있을 수 있습니다.

외부 모델과 라이브러리는 [THIRD-PARTY.md](THIRD-PARTY.md)를 참고하세요.

운영 코드는 공개 저장소 `hoyeol903/KNU-AUDIO-public`에서 관리합니다. 기존 `KNU-AUDIO`는 과거 기록을 보관하는 비공개 저장소입니다. 학번·주민등록번호·개인 휴대전화 형태와 학번에 연결된 명시적 성명은 저장 전에 가립니다. 검수는 **개인정보를 가린 원문**의 제목·날짜·마감·장소·신청 조건과 대조합니다. 자동 가림은 개인정보가 전혀 없다는 보증이 아니므로 새 자료의 공개 적합성도 확인해야 합니다. 자세한 전환 상태는 [공개 준비 점검](docs/public-readiness.md)을 참고하세요.
