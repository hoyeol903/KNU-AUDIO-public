# 정적 앱 미리보기

학교 사이트를 호출하지 않고 현재 저장된 DB와 일일 자료를 GitHub Pages용 파일로 내보낸다.

```bash
python -m collector.export_app
python -m http.server 8000 --directory output/app
```

브라우저에서 `http://127.0.0.1:8000/`을 연다. 결과는 `output/app/` 아래에 생성되며, `data.json`에 채널 카탈로그와 판정 snapshot을 저장하고 본문은 게시판별 `details/<게시판 ID>.json`으로 나눈다. 이 자료는 내부 검토용 정적 복사본이므로 저장소 공개 전에 내용을 확인한다. 다시 내보내면 화면이 갱신된다.

학과별 필수 공지는 자동 포함되며, 다른 학과의 필수 공지와 식당을 추가할 수 있다. 장학·취업 등 선택 공지 채널은 현재 선택 목록에서 제외했다. 다른 학과 공지를 골라도 공통 공지는 중복 표시하지 않는다.

`python -m collector.preview`의 `http://127.0.0.1:8765/app`은 기존 로컬 API 화면으로 유지한다. 정적 앱의 하위 경로에서도 `./data.json` 기준 상대 경로를 사용한다. 날짜가 현재 한국 날짜와 다르면 화면은 자료 기준일을 표시한다.

GitHub Pages의 Source는 **GitHub Actions**로 설정한다. 현재 `.github/workflows/deploy.yml`이 `output/app`의 배포용 파일을 Pages artifact로 업로드한다. 구체적인 실행 조건과 공개 파일은 아래 배포 안내를 참고한다. 기본 `GITHUB_TOKEN`으로 파일을 커밋하는 수집 작업은 push 트리거 대신 워크플로 완료 이벤트로 배포를 잇는다.

## 새 화면과 화면용 자료 (2026-10-03)

`python -m collector.export_app`은 기존 출력에 더해 아래를 만든다. `index.html`은 새 화면(`tools/knua-app.html`)이고, 이전 시험 화면은 `legacy.html`로 열 수 있다. `data.json`과 `details/`는 이전 화면용으로 그대로 둔다.

| 파일 | 내용 |
| --- | --- |
| `data/meta.json` | 홈 한 장에 필요한 자료. `asOf`, `checkedAt`, `weather`, `schedule`, `cafes`, `departments`, `boards`, `issues` |
| `data/boards/{채널 ID}.json` | 그 게시판의 최신순 30개와 오늘 알릴 글. `id`, `title`, `date`, `deadline`, `url`, `body`, `bodyStatus` |
| `data/briefing/segments.json` | 수집기는 만들지 않는다. 음성 담당이 넣으면 화면이 읽는다 |
| `data/schedule.json` | 캘린더용 학사일정 전체. 수집기가 받은 해의 학교 학사일정 목록(`context.json`의 `schedule_year`) 중 가장 최근 것과 받은 날짜(`from`). 없으면 `status: empty`이고 화면은 `meta.json`의 가까운 일정만 쓴다 |

- 게시판 ID는 `items.json`과 같은 채널 ID다. 화면은 사용자가 고른 게시판과 식당만 걸러 보여준다.
- `status`는 `ok`, `empty`(자료가 없다), `failed`(가져오지 못했다)를 구분한다. 날씨는 `ok`와 `failed`만 있다. 식단은 "미게시"와 휴무를 `empty`로, 접속·구조 오류와 미수집을 `failed`로 둔다.
- D-day와 학사일정의 "진행 중"은 저장하지 않고 화면이 Asia/Seoul 날짜로 계산한다. `asOf`가 오늘이 아니면 화면이 "기준일"로 표기한다.
- `boards[].today`는 기존 선정 규칙(`decide_notice`) 결과다. `kind`는 `new` 또는 `deadline`이고 홈 목록용으로 `title`, `date`, `deadline`을 함께 싣는다.
- `cafes[].groups[]`는 메뉴 항목 하나씩이다. `label`(조식·중식·석식), `hours`, `price`(원), `menu`, `head`(대표 음식 이름이 `menu` 앞에서 몇 줄인지)를 싣는다. 화면은 끼니마다 카드를 만들고, 항목이 여럿인 끼니는 가격별로 묶는다. 끼니·가격은 주간 표(`meal_week`)에서만 읽으며 `items.json`의 식단 형식(`place`, `time`, `menu`)은 그대로다.
- `cafes[].days[]`는 식당 주간 표에 있는 날짜별 식단(`date`, `status`, `hours`, `groups`)이다. 식단을 수집할 때 받은 같은 페이지에서 읽으므로 추가 요청이 없고, `context.json`의 `meal_week`에 저장된다. 식당 화면의 날짜 단추가 이 값을 쓴다. 표에 있는 약 6일만 고를 수 있다.
- 식단은 로컬에서 가끔만 수집한다. 오늘 식단을 수집하지 않은 날에는 최근 6일 안에 받은 주간 표 중 오늘 날짜가 들어 있는 가장 새 것을 쓰고, 그 수집일을 `cafes[].menuFrom`에 싣는다. 화면은 오늘 받은 표가 아니면 받은 날짜를 함께 보여준다. 그런 표가 없으면 `failed`다.
- `departments[].avatar`는 그 학과 단과대학의 캐릭터 사진 경로(`avatars/04.webp`)이고, 사진이 없는 학부는 null이다. 사진 원본은 `tools/avatars/`에 있고 내보낼 때 `data/avatars/`로 복사한다. 단과대학과 사진 번호의 짝은 `export_app.py`의 `COLLEGE_AVATARS`에 있다. 화면은 홈 왼쪽 위와 처음 게시판 고르는 화면에 보여준다.
- `issues`는 `{source, text}`다. `source`는 `weather`, `schedule`, `meals`, 채널 ID 중 하나다.

브리핑 파일 형식(화면이 읽는 모양):

```text
{ "date": "YYYY-MM-DD",
  "segments": [ { "id": "intro | outro | 게시판 채널 ID | 식당 채널 ID", "title", "audio": "파일 경로 또는 null",
                  "duration": 초, "script", "cards": [ { "kind": "날씨|마감 임박|학식|소식", "title", "desc", "url", "postId" } ] } ] }
```

`audio`는 `data/briefing/` 기준 상대 경로다. `date`와 `meta.json`의 `asOf` 차이가 3일 이내이면 날짜가 다른 최신 음성도 받아들이고 그 음성 날짜를 표시한다. 파일이 없거나 허용 범위를 벗어나면 브리핑 없음으로 표시한다. 재생 목록은 intro, 오늘 소식이 있는 내 게시판, 내 식당, outro 순서로 화면이 만든다. `audio`가 없고 `script`만 있는 구간은 브라우저 음성으로 읽는다. 화면은 `docs/contracts.md`의 `briefing.json` 이름(`channel_id`, `duration_sec`, `items`, `section`, `detail`)도 그대로 읽는다. 브리핑 담당용 안내는 `docs/briefing-handoff.md`, 예시는 `samples/briefing.example.json`이다.

주소 끝에 `?test`를 붙이면 테스트 패널(밝기, 바로 가기, 저장 지우기)이 보인다.

## 배포: GitHub Pages (2026-10-09)

공개 저장소로 옮기면서 GitHub Pages(https://hoyeol903.github.io/KNU-AUDIO-public/)에 올린다. GitHub Actions(`.github/workflows/deploy.yml`)가 파일을 직접 올리며, 저장소 Settings → Pages의 Source는 GitHub Actions다. 이전 Cloudflare Pages 사이트(`knu-audio.pages.dev`)는 더 이상 이 저장소에서 배포하지 않는다.

| 언제 | 설명 |
| --- | --- |
| `main`에서 `output/app/`이 바뀐 push | PR 머지 포함 |
| "매일 경북대 자료 수집" 워크플로 완료 | 자동 커밋은 push 트리거를 시작시키지 않아 완료 이벤트로 잇는다 |
| 수동 실행 | Actions 탭 → "GitHub Pages 배포" → Run workflow |

배포에 별도 Secret은 필요하지 않다.

새 화면(`index.html`), 개인정보 안내(`privacy.html`)와 화면용 자료(`data/`)를 올린다. 이전 시험 화면(`legacy.html`, `data.json`, `details/`)은 올리지 않는다. 배포한 사이트는 누구나 볼 수 있다. 일시적인 Pages 배포 오류는 워크플로에서 한 번 다시 시도한다.


## 월 일정·교류 구역·저장 공지 (2026-10-07)

- 캘린더의 월 전체 일정은 날짜순으로 처음 5개만 표시한다. 6개 이상이면 나머지 보기/접기로 펼치며 선택한 날짜의 일정은 별도로 유지한다.
- 교류 탭은 스터디·과팅·소모임 구역으로 나뉜다. 구역을 누르면 해당 분류의 공유 모집글과 내 모집글, 예시 목록으로 이동하고, 뒤로 버튼은 교류 첫 화면으로 돌아간다. 2026-10-09 기준 예시는 각 분류 1개, 총 3개다.
- 공지 상세에서 `공지 저장`을 누르면 홈의 내 게시판 → 저장한 공지에 모인다. 다시 누르거나 저장 목록의 해제 버튼으로 뺀다. 저장한 최신 순서로 표시한다.
- 저장 공지는 `knua-app-v1`의 `savedPosts`에 게시판 식별자, 제목, 날짜, 본문, 원문 링크를 보관한다. 최근 30개 목록에서 빠지거나 선택 학과가 바뀌어도 다시 열 수 있다. 본문 로딩 전에 저장했다면 로딩이 끝났을 때 보완한다. 브라우저 데이터 삭제 또는 처음부터 다시 기능은 저장 공지도 지운다. 다른 브라우저나 기기로 동기화하지 않는다.
- 공지 저장 회귀 검사: `node collector/tests/test_saved_notices_player.mjs`.


## 공유 교류 검사

`node community/test_api.mjs`로 공유 조회·작성자 권한·신청 정보 비공개·재시도·페이지 이동·한도를 확인한다. 별도 브라우저 두 개로 모집글 작성 → 상세 조회 → 참가 링크 → 신청 → 모집자 내역 → 수정 → 마감·재개 → 취소 → 삭제를 검사한다. 각 분류의 필수 입력과 잘못된 연락 링크, 서버 실패 시 입력 유지도 확인한다. 예시는 실제 모집글과 분리되고 신청 버튼이 없어야 한다. 계정 연결과 초기 인증 한계는 [교류](community.md)를 참고한다.
