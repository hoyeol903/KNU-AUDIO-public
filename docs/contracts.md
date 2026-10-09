# 데이터 약속 (채널 단위)

조직·채널·필수 연결의 검토용 CSV는 `output/csv/`에 있다. CSV 열의 의미와 공지 저장 기능 사용법은 `docs/data-storage.md`를 참고한다. 설정 기준은 YAML이며 이 CSV 내보내기로 `items.json`·`briefing.json` 형식을 바꾸지 않는다.

이 문서는 크누아(KNU AUDIO)의 데이터 형식 기준이다. 형식을 바꿀 때는 **팀 합의 후 이 문서부터 고친다**. `CLAUDE.md`의 요약도 함께 일치시킨다.

## 공통 규칙

- 날짜는 전부 **Asia/Seoul 기준 `YYYY-MM-DD`**다.
- `deadline`, `dday`를 못 찾으면 `null`로 둔다. 날짜, 마감일, 장소, 시간은 원문 값만 사용하며 추측해서 채우지 않는다.
- "데이터가 없다"와 "못 읽었다"를 구분한다. 구조를 못 읽은 실패는 빈 값으로 숨기지 않고 예외를 던지거나 `errors`에 남긴다.
- 수집기 하나가 실패해도 나머지 데이터로 브리핑을 제공한다.
- 저장용 JSON 파일 읽기·쓰기는 `collector/store.py`를 통해서만 수행한다. 웹은 배포된 정적 결과 파일을 읽는다.
- 파일은 임시 파일에 쓴 뒤 이름을 바꾸어 교체한다. 중단되어도 기존 파일이 깨지지 않아야 한다.
- JSON 저장 옵션은 `ensure_ascii=False`, 들여쓰기 2칸, 키 정렬이다.

### `data/channels.yaml` — 채널 목록

수집기와 웹이 같이 읽는다.

```yaml
- id: knu-academic
  name: 학교 학사공지
  type: notice
  required: all
- id: see
  name: 전자공학부
  type: notice
  required: [전자공학부]
- id: meal-bokji
  name: 복지관 식당
  type: meal
  required: none
```

`required`는 `all`(모두 필수) / 학과 목록(그 학과면 필수) / `none`(선택)이다.

### `items.json` (collector → briefing)

```text
date, collected_at,
weather { summary, temp_min, temp_max, rain_prob },
channels: [ {
  channel_id,
  notices [ { id, channel_id, source, title, url, posted_at, deadline, dday, body, reason } ],
  meals [ { place, time, menu[] } ]
} ],
schedule [ { title, start, end, dday } ],
errors [ { source, message } ]
```

- `notices` 항목에 `channel_id`가 붙는다. 나머지 필드는 기존과 같다.
- 날짜는 전부 Asia/Seoul 기준 `YYYY-MM-DD`다.
- `deadline`, `dday`를 못 찾으면 `null`이다.
- `reason`은 `"new"`(오늘 처음 본 공지) 또는 `"reminder"`(마감 3일 전·1일 전·당일 재안내)다.

경로: `data/raw/<날짜>/items.json`. 위 표기는 필드 구조 설명이며 실행 가능한 JSON 예시는 아니다.

`weather`는 날씨 요약·최저/최고 기온·강수 확률, `meals`는 장소·식사 시간·메뉴 배열을 담는다. 공지는 식별자·채널 ID·출처·제목·원문 URL·게시 날짜·마감 날짜·남은 일수·본문·선정 이유를 담는다. `schedule`은 일정 제목·시작/종료 날짜·남은 일수, `errors`는 실패한 출처와 실패 내용을 담는다.

### 앱 브리핑 출력 (`output/app/data/briefing/segments.json`)

```text
date, voice,
segments: [ {
  id, channel_id, title, script, duration_sec, audio, kind?, channel_ids?, notice_refs?,
  items [ { section, title, detail, url, dday, postId } ],
  personal_template?, cues?: [ { text, start_sec, end_sec } ]
} ]
```

- 이 파일은 `briefing.app_export`가 생성하며 Cloudflare Pages 앱이 읽는다. 이전 `web/public/briefings/<날짜>/briefing.json` 경로를 사용하지 않는다.
- `segments[].audio`는 이 폴더 안 MP3 파일명이다. 한 앱 구간에 여러 내부 대본이 합쳐질 수 있다.
- `cues`는 합쳐진 MP3에서 원래 음성 파일별 대본과 시작·끝 초를 보존한다. 문장별 정렬 값이 아니다. 없는 이전 출력은 녹음 전체를 한 말풍선으로 표시하며 글자 수로 문장 전환을 추정하지 않는다. 이름 인사는 실제 기기 음성의 문장 시작 이벤트로 표시한다. 기본 인사 MP3로 대체하면 화면에도 이름 없는 `script`를 표시한다.
- 공통 인사·날씨·이벤트는 `intro`, 개인화 가능한 이름 없는 인사는 선택적 `greeting`, 마무리는 `outro`로 전달한다. 실제 학생 이름은 포함하지 않는다.
- 카드 구분 `items[].section`은 `날씨`, `마감 임박`, `학식`, `소식` 가운데 하나다. 공지 카드는 원문 제목·URL·ID를 보존한다. `dday`는 현재 null이며 앱이 오늘 날짜로 계산한다.
- `마감 임박`은 수집 reason이 reminder이고 내부 생성 manifest가 원문 마감일을 확인한 경우에만 붙는다.

경로: `output/app/data/briefing/segments.json` 및 같은 폴더의 MP3 파일. 실제 생성 구조는 `briefing/app_export.py`를 기준으로 한다.

| 필드 | 내용 |
| --- | --- |
| `date` | 브리핑 날짜 |
| `segments[].id` | segment 식별자 |
| `segments[].channel_id` | 해당 채널 ID 또는 공통 구간 `intro` / `outro` |
| `segments[].title` | segment 제목 |
| `segments[].script` | 최종 대본. 첫 대본만 검수하며 재생성 대본은 재검수하지 않는다. |
| `segments[].audio` | 앱 브리핑 폴더의 MP3 파일명 |
| `segments[].duration_sec` | 앱 구간 음성의 재생 시간(초) |
| `segments[].items[].section` | 요약 카드 구분 |
| `segments[].items[].title` | 요약 카드 제목 |
| `segments[].items[].detail` | 요약 카드 상세 내용 |
| `segments[].items[].url` | 관련 원문 URL |
| `segments[].items[].dday` | 현재 null. 앱이 오늘 날짜를 기준으로 계산한다. |

브리핑 빌드 내부 `dist/manifest.json`은 앱 출력 계약과 다르다. 내부 `dist/manifest.json`은 앱에 내보낼 segment와 검수 결과를 담지만, `briefing.build`는 `source_text`, `reference`, `required`, `constraints`, `deadline_verification` 필드를 앱 공개 segment에서 제외한다. 상세 마감 확인 기록은 내부 `output/briefing-report.json`의 `deadline_checks`에 남는다. 앱 출력 `output/app/data/briefing/segments.json`에는 이 원문·검수 증거를 넣지 않는다. 마감 날짜는 기존 `items.json`의 원문 제목·본문에서 추출된 단일 마감과 저장 deadline이 일치한 경우에만 내부 생성 검수에 확인 정보로 전달된다. 규칙 검수는 날짜 표현과 일부 마감 단어를 대상으로 하며 대상·장소·조건 등 전체 의미를 독립 검증하지 않는다. 한계와 처리 흐름은 [브리핑 연동 문서](briefing-integration.md)에 정리한다.

## 아직 정하지 않은 세부 사항

segment ID와 음성 파일 URL/이름 규칙, 필드별 세부 자료형과 그 밖의 누락 값 처리 방식은 아직 명시되지 않았다. 기존 전체 브리핑 목표(공백 포함 500~700자, 1분 30초~2분)를 사용자별 채널 조합에 어떻게 적용할지도 아직 정하지 않았다. 이 목표를 segment별 분량으로 가정하지 않는다. 구현 시 팀 합의 후 이 문서에 반영한다.

## 공지 영구 저장 (2026-09-30 확정)

### 운영 기준과 일일 확인 범위 (2026-10-01)

공지 DB 필드는 유지하고 `data/db/notices-collection-state.json`에 게시판별 운영 기준을 저장한다. 최상위는 `boards`, 각 게시판 값은 `initialized_at`(초기 적재 완료·운영 시작 기준, +09:00 ISO 8601 또는 null), `last_full_scan_at`(마지막 전체 확인 성공 시각 또는 null)이다. 사용자 지정 DB는 같은 폴더의 `<DB이름>-collection-state.json`을 사용한다. 모두 store를 통해 원자적으로 읽고 쓴다.

- 기본 `daily`: 목록을 최근 구간부터 읽고 일반 공지가 모두 오늘−30일보다 오래된 페이지가 2번 연속 나오면 중단한다. 고정 공지는 경계 판단에서 제외하고 날짜 미확인 일반 공지가 있으면 그 페이지는 오래된 페이지로 간주하지 않는다. 그 경계까지의 첫 발견 글·최근 7일/고정 공지를 확인한다. 그 외 글은 마지막 상세 성공 확인 후 7일 이상일 때 확인한다. DB의 마감 예정·날짜 미확인·needs-review 공지는 범위 밖이어도 상세를 확인한다.
- daily 실행은 주기적으로 전체 점검으로 전환되지 않는다. 오래된 목록 뒤쪽의 새 글·수정 확인은 자동 수집 범위에서 보장되지 않으며 필요할 때 `full`을 명시해 전체 목록을 확인한다. `full`은 즉시 전체 점검, `init`은 명시적 초기 적재다. 전체 목록과 필요한 오래된 본문을 재확인하며 아직 7일이 안 된 일반 오래된 본문은 생략한다.
- 신규 게시판의 첫 실행 또는 init 중 발견한 글은 과거 적재로 처리한다. 오류·페이지 제한이 있으면 초기화/전체 점검 성공 시각을 갱신하지 않는다. 중간에 저장된 글은 재시작 시 재사용한다.
- `start`는 새 게시판을 최근 구간부터 운영할 때 쓰는 명시적 초기 적재다. daily와 같은 30일·오래된 일반 페이지 2개 경계까지 확인한다. 이 범위를 오류 없이 마치면 initialized_at만 기록하고 last_full_scan_at은 null로 유지한다. 이후에도 daily는 이 범위를 유지하며 필요하면 수동 full로 과거 전체를 확인한다. 과거 전체 적재 완료를 뜻하지 않으며 bootstrap으로 당일 신규 후보에서 제외한다. 이미 initialized_at이 있는 게시판에는 start를 다시 적용하지 않는다.
- `new`는 기존대로 **DB에 처음 저장된 ID**다. 브리핑의 오늘 신규와 다르다. `new_candidates`는 initialized_at 이후에 처음 저장됐고 최초 발견의 한국 날짜가 오늘이며 게시일이 최근 30일 범위인 ID다. 같은 날 재실행에서도 DB 이력으로 다시 계산하므로 앞선 저장 후 실행이 중단돼도 발견 이력이 사라지지 않는다. 초기 적재 글은 제외한다.
- 운영 시작 이후 오늘 처음 저장했으나 게시일이 오래됐거나 미확인인 ID는 `late_discoveries`다. 자동으로 오늘 신규로 전달하지 않는다. 본문 변경은 `updated`로 분리하며 신규로 바꾸지 않는다. items.json의 reason은 기존 new/reminder를 유지한다.
- 보고서에 `mode`, `bootstrap`, `new_candidates`, `late_discoveries`, `window_complete`, `direct_checks`(목록 범위 밖 저장 글의 직접 상세 확인 수)를 추가한다. 초기화·전체 점검은 errors 없음, truncated=false인 경우만 성공으로 기록한다. daily의 정상 30일 경계 중단은 truncated가 아니며 window_complete=true다. 상세 실패는 errors에 별도로 남긴다.

오래된 날짜로 목록 뒤쪽에 추가한 글·오래된 글의 수정은 daily 범위에서 보장되지 않는다. 사용자가 수동 full을 실행하면 전체 목록을 확인하지만, 날짜 정렬의 불규칙한 구간·목록 이동 중 누락 가능성은 남는다. 한정된 범위를 확인했다고 전체 게시판 확인 성공으로 기록하지 않는다.

경로는 `data/db/notices.json`이고 최상위는 공지 레코드 배열이다. DB 서버를 사용하지 않는다. 파일을 처음 만들기 전에는 빈 배열로 읽지만, 존재하는 파일의 JSON·형식·해시가 잘못되면 예외를 발생시킨다. 손상된 파일을 빈 DB로 바꾸지 않는다.

| 필드 | 자료형 | 규칙 |
|---|---|---|
| id | 문자열 | `source_board_id:source_post_id`. store에서 생성 |
| source_board_id | 문자열 | 원문 게시판의 안정적인 식별자. 소문자 영문·숫자·하이픈·밑줄, 첫 글자는 영문 또는 숫자. 페이지·검색·세션 조건 제외 |
| source_post_id | 문자열 | 원문 글 ID. 비어 있거나 앞뒤 공백이 있으면 오류. 화면 목록 순번 사용 금지 |
| channel_ids | 문자열 배열 | 해당 글을 제공할 채널 ID. 비어 있지 않으며 중복 제거·정렬. 기존 채널 연결과 합침 |
| title | 문자열 | 비어 있지 않은 원문 제목 |
| url | 문자열 | 비어 있지 않은 HTTP(S) 원문 상세 주소 |
| posted_at | 문자열 또는 null | 원문 게시일, Asia/Seoul `YYYY-MM-DD`. 미확인은 null |
| deadline | 문자열 또는 null | 원문 마감일, Asia/Seoul `YYYY-MM-DD`. 미확인은 null |
| body | 문자열 또는 null | 확인한 원문 텍스트. 아래 본문 상태에 따라 기록 |
| body_status | 문자열 | text / image-only / attachment-only / empty / needs-review |
| first_seen_at | 시각 문자열 | 최초 발견 시각. 이후 갱신에도 유지 |
| last_checked_at | 시각 문자열 | 마지막 상세 확인 성공 시각. 최초 발견보다 빠를 수 없음 |
| content_hash | 문자열 | 제목·본문·게시일·마감일·본문 상태를 JSON 키 정렬로 직렬화한 SHA-256. store에서 생성 |

이력 시각은 `2026-09-30T05:37:00+09:00` 같은 Asia/Seoul ISO 8601 문자열이다. 시각의 예시는 형식 설명이며 실제 수집 기록이 아니다. 원문 날짜와 우리 서비스가 발견한 시각을 혼동하지 않는다.

- `text`: 공백만으로 이뤄지지 않은 본문 문자열이 필요하다.
- `image-only`, `attachment-only`: 텍스트를 읽지 못한 전용 본문이며 `body: null`이다.
- `empty`: 원문에서 정상적인 빈 본문을 확인했을 때만 `body: ""`를 저장한다.
- `needs-review`: HTML 접근은 성공했으나 수동 검토가 필요한 본문이다. 확인한 문자열 또는 null을 기록한다. 요청·파싱 실패를 이 상태의 빈 공지로 바꿔 저장하지 않는다.

`load_notices()`는 저장된 레코드를 읽는다. `upsert_notices(notices, checked_at=..., path=...)` 입력은 위에서 store가 생성하는 네 필드(`id`, `first_seen_at`, `last_checked_at`, `content_hash`)를 제외한 필드 전체다. 누락·알 수 없는 필드·잘못된 타입·날짜는 예외로 알린다. `checked_at`을 생략하면 실행 시점의 한국 시각을 쓴다. `path`는 테스트 등에서 저장 파일을 지정할 때 사용한다.

반환은 `new`, `updated`, `unchanged` 각각의 공지 ID 배열이다. 내용 해시 변경만 `updated`로 분류하며 URL·채널 연결·확인 시각만 바뀐 경우는 `unchanged`다. 새 내용으로 갱신하면서 최초 발견 시각은 유지하고 채널 ID는 합친다. 같은 입력을 같은 시각에 두 번 저장해도 결과 파일은 같다. 과거 확인 결과로 더 최신의 저장 레코드를 덮어쓰지 못하게 한다.

한 호출의 입력을 모두 검증한 후 공지 ID 순으로 저장한다. 같은 글의 동일한 중복 입력은 합치고, 같은 글의 상충하는 입력은 저장하지 않는다. 입력 또는 파일 교체 실패 시 기존 파일을 보존하고 예외를 전달한다. 임시 파일은 원본과 같은 디렉터리에 만들고 flush·fsync 후 `os.replace`로 교체한다. JSON은 UTF-8, `ensure_ascii=False`, 들여쓰기 2칸, 키 정렬, 마지막 줄바꿈을 사용한다.

요청·파싱에 실패한 수집 결과는 upsert에 전달하지 않고 그날 `errors`에 기록한다. 수집기 구현 시 성공한 소스만 병합해 부분 실패를 허용한다. `dday`와 `reason`은 날짜별 `items.json` 생성 단계에서 계산한다. 첫 운영의 과거 공지를 모두 당일 새 소식으로 선정하지 않는 정책도 그 단계에서 적용한다. 저장 기능은 단일 writer를 전제로 하며 운영 워크플로 실행을 직렬화한다.

## 채널 카탈로그 검토 필드

`data/channels.yaml`에는 기본 `id`, `name`, `type`, `required` 외에 조사·검토용 필드를 추가한다. `required`의 기존 all/학과 이름 목록/none 의미는 유지한다.

- `required_department_ids`: `data/departments.yaml`의 학과 ID 목록. 소속이 다른 동명 학과를 구분하는 기준이다. `required: all`이면 모든 학과에 적용하고, 그 외의 필수 채널 판단은 ID 목록을 우선한다.
- `classification`: required / optional / review / excluded. 마지막 두 값은 사용자가 검토하거나 신입생 대상에서 제외할 채널이다.
- `category`, `organization_ids`, `menu_labels`, `classification_reason`: 원문 조직·메뉴와 분류 이유.
- `source_url`, `template`, `status`, `evidence`: 주소·파서 계열·확인 상태·근거 파일. 주소 미확인은 null이며 임의로 만들지 않는다.
- `collection_enabled`: 현재 조사상 수집 대상으로 사용할 수 있는지. false이거나 주소가 없는 채널은 요청하지 않는다. 수집기가 구현됐다는 의미는 아니다.
- `review_needed`, `review_reasons`: 사용자가 확인할 항목. 일반 공지의 개별 글 대상은 아직 판별되지 않아 필수 채널 초안에도 검토 표시가 있을 수 있다.

학과를 선택하면 공통 필수와 해당 학과 ID가 배정된 소속 필수 채널을 합친다. 앱에서는 다른 학과의 필수 공지와 식당 채널을 추가 선택할 수 있으며, 공유 공지는 중복 없이 표시한다. 장학·취업 등 선택 공지 채널 73개는 현재 앱 선택 목록에서 제외했다. 수집은 게시판별 한 번 수행하고 사용자별로 채널 구간을 고른다. 검토 화면의 메모는 별도 JSON이며 자동으로 이 계약이나 YAML을 변경하지 않는다.

### 사용자 확인 후 전공별 연결

`data/departments.yaml`의 `child_department_ids`와 `notice_urls`는 학부가 전공별 게시판으로 연결되는 경우 사용한다. `notice_scope: child-major-boards`는 공통 게시판 발견을 뜻하지 않는다. 학부 선택 후 실제 전공을 지정해 그 전공의 필수 채널을 배정한다. 채널의 `parent_organization_ids`와 `user_comments`는 이 연결의 검토 근거다. `operating_status: needs-confirmation`은 폐지 추정 메모가 있지만 공식 운영 여부가 미확정인 항목으로, 관련 주소 미확인 채널의 자동 필수 배정을 보류하고 조사 항목을 보존한다.

## 단일 게시판 실행 보고서

`collector/store.py`의 `save_collection_report(report, path)`로 `data/runs/<실행시각>-korean.json`을 원자적으로 저장한다. `channel_id`, `source_board_id`, `started_at`, `finished_at`, `initial_import`, `scope`, `pages`, `max_pages`, `truncated`, `listed`, `successful`, `new`, `updated`, `unchanged`, `errors`를 기록한다. 오류 항목은 `source`, `url`, `message`다. 실행 보고서는 브리핑 입력인 `items.json`을 대신하지 않는다. `initial_import`는 실행 전 그 게시판의 저장 레코드가 없었다는 뜻이며 당일 신규 공지 여부와 다르다.

페이지 순회 보고서의 `scope`는 `page-traversal`, `pages`는 파싱한 목록 페이지 수다. `max_pages`는 실행 상한, `truncated`는 다음 페이지가 있으나 상한으로 중단했는지 나타낸다. 범위 미완료는 성공한 데이터 저장과 별개로 종료 코드 1로 표시한다.

실행 보고서에 `skipped`(정책상 상세 요청을 생략한 공지 ID 배열), `needs_review`(게시일 미확인 또는 기존 마감일 재확인 필요 ID 배열)를 추가한다. 목록 파서의 `pinned`는 현재 상단 고정 여부이며 영구 공지 DB 필드는 아니다. 상세를 생략한 레코드의 last_checked_at은 갱신하지 않는다. 상세 재확인 정책은 `docs/collection.md`에 정의한다.

## 다중 채널 실행 보고서 (2026-10-01)

### 필수 KNU CMS 확대 검증·공유 게시판

- `data/knu-cms-validation.json`은 `collector.verify_knu_cms`가 생성한 목록·대표 상세 검증 결과다. `channels[]`에 channel_id/name/source_url/source_board_id/status/listed/next_url/files/errors/checked_at을 기록한다. 요청 실패 시 아직 확인하지 못한 필드는 없다. `verified`는 목록·페이지 링크 구조와 대표 상세 1건의 ID·제목·게시일 일치, `empty`는 정상적인 빈 목록, `failed`는 요청·구조·일치 검증 실패다. 빈 게시판은 상세 검증 전이며 새 글이 생기면 상세 파싱에서 오류가 날 수 있다.
- CLI 확대 대상은 현재 YAML의 URL과 검증 당시 source_url이 같고 status가 verified/empty인 KNU CMS 채널이다. `--required-knu-cms`는 이 중 필수 채널을 선택한다. collection_enabled는 주소 수집 허용이며 모든 틀의 수집기가 구현됐다는 뜻은 아니다.
- 게시판 ID는 공식 `*.knu.ac.kr` 주소의 `/HOME/<site>/sub.htm`과 nav_code를 소문자 식별자로 정규화한다. 원문 URL의 대소문자는 보존하며 공식 별칭 호스트가 같은 site/nav_code를 가리키면 같은 게시판으로 묶는다. 서로 다른 nav_code는 별개다.
- 공유 게시판은 한 번 수집한다. 보고서의 channel_id는 대표 ID, channel_ids는 함께 연결한 논리 채널 배열이다. 상세를 생략하는 기존 글도 store의 link_board_channels로 채널 연결만 병합한다. `linked`는 이 연결이 추가된 기존 글 수이고 원문 변경인 updated와 다르다. first_seen_at/last_checked_at/content_hash는 변경하지 않는다.
- 확대 검증은 대표 샘플 확인이며 전체 과거 글 적재나 모든 페이지·첨부 내용의 성공을 보장하지 않는다. 확인이 필요한 결과는 목록에서 삭제하지 않고 이유를 보존한다.

### 배치 결과

학교 학사공지 채널 `knu-academic`(menu_idx=42, stu_812)의 게시판 ID는 `knu-wbbs-stu_812`, 전자공학부 채널 `notice-df44dd8507c1`(gtid=notice)은 `knu-see-notice`다. 각각 bltn_no와 fidx를 원문 글 ID로 사용하며 화면 목록 순번은 사용하지 않는다. 학교 목록의 doRead 인자를 읽어 상세 GET 주소를 조립하고, 페이지 이동은 menu_idx와 page/pageIndex를 보존한다. 이 지원은 학교의 별도 일반공지 메뉴나 전자공학부의 취업·세미나 게시판까지 포함하지 않는다. 본문 상태·해시·오류·저장 계약은 기존과 같다.

현재 CLI의 `data/runs/<실행시각>-channels.json`은 `channels`(기존 채널 보고서 배열)와 `request_count`(모든 실제 HTTP 요청 시도 합계)를 갖는다. 각 채널에 `request_count`, `duration_sec`를 추가한다. 요청 수는 재시도·리다이렉트 포함, 경과 초는 요청 간격 대기·파싱·저장 포함이다. 이전 단일 채널 보고서는 그대로 보존한다. 게시판 ID는 `knu-<HOME 사이트 코드>-<nav_code>`이며 페이지·검색 조건은 제외한다.

`load_collection_report(path)`는 store를 통해 실행 보고서를 읽으며 파일 누락·JSON 손상·객체가 아닌 형식은 예외로 알린다. 긴 제목이 목록에서 `..`로 축약된 경우 글 ID·게시일·상세 제목 접두부를 확인하고 상세의 전체 제목을 저장한다. 이 표시 차이만으로 수정된 공지로 분류하지 않는다.

### 추가 필수 게시판 (2026-10-01)

그누보드의 원문 글 ID는 `wr_id`, 의대 `med-cms`는 `mv_data`의 `idx`, 치대 `custom-bid-board`는 `bno`다. 게시판 ID·허용 URL은 `collector/run.py`의 OTHER_SOURCES에 고정하고 설정의 URL·틀이 일치할 때만 선택한다. 미검증 선택 게시판으로 지원 범위를 자동 확장하지 않는다.

인공지능계열(aicollege)과 컴퓨터학부(computer)의 `sub6_1_a`는 목록 2페이지의 ID·제목·게시일·고정 여부와 대표 상세 제목·날짜·본문 일치를 확인한 공유 게시판으로 `knu-computer-sub6_1_a`에 함께 저장한다. 원문 URL은 요청한 공식 호스트 주소를 유지한다. 후에 별도 게시판으로 분리되면 공유 ID를 바꾸기 전에 자료를 재확인한다.

그누보드 상세가 2자리 연도를 표시하면 목록의 4자리 게시일과 대조해서 목록의 원문 날짜를 쓴다. 세기를 추측하지 않는다. 날짜 미확인·변경으로 대조가 안 되면 오류를 남긴다. 본문·이미지·첨부 상태와 영구 저장 필드는 기존 계약을 유지한다.

## 마감일 추출 (2026-10-01)

영구 공지 DB의 필드는 유지한다. `collector/deadlines.py`가 제목·본문의 명시된 신청/제출 등 종료 날짜를 판정한다. 연도가 생략된 날짜는 추측하지 않는다. 한 기간의 시작·끝이 모두 연도까지 명시되면 끝 날짜를 사용하며, 여러 마감·조건부 마감은 null/needs-review로 남긴다. `deadline`은 날짜만 담으므로 당일 마감 시각을 뜻하지 않는다.

추출 결과는 deadline/status/evidence/reason이다. status는 found/not-found/needs-review이며 evidence는 원문 근거 문장 배열이다. not-found는 읽은 텍스트에서 확실한 마감을 못 찾았다는 뜻이며 원문에 마감이 없다는 뜻이 아니다. `collector.run`의 deadline_checks에는 notice_id와 추출 결과를 남기고 모호한 공지를 needs_review에도 연결한다. 이 검토 상태는 영구 DB의 body_status와 별개다.

기존 DB의 재분석 보고서는 created_at/mode/checked/counts/proposed/updated/checks를 담는다. checks는 판정 대상의 notice_id/title/url/posted_at/previous_deadline과 추출 결과를 담는다. apply는 기존 deadline이 null인 found 항목만 store.update_deadlines로 갱신한다. 이 함수는 전체 입력 검증 후 원자적으로 저장하고 deadline/content_hash 이외의 필드를 바꾸지 않는다. 실제 HTTP 확인을 하지 않았으므로 first_seen_at/last_checked_at을 갱신하지 않는다. 재실행 시 같은 결과는 저장하지 않는다.

기존 마감일은 일괄 재분석에서 덮어쓰지 않는다. 실제 상세를 다시 수집할 때는 판정된 마감을 반영하며, 기존 마감을 못 찾더라도 제목·본문·게시일·본문 상태가 같으면 기존 값을 보존한다. 원문이 바뀌고 기존 마감을 확인할 수 없으면 null과 검토 필요로 남긴다. 근거와 현재 한계는 docs/deadlines.md에 있다.

## 일일 공지 선정과 items.json (2026-10-01)

- `collected_at`은 파일을 만드는 한국 시각의 +09:00 ISO 8601이다. 실제 사이트 확인 시각은 각 DB 레코드와 실행 보고서에 있으며 파일 생성 시각과 구분한다.
- `new`: 운영 시작 기준 이후, 대상 날짜에 처음 발견했고 게시일이 대상 날짜 기준 최근 30일 이내인 공지. 초기 적재·수정만 된 글·미래 게시일·게시일 미확인은 제외한다. `reminder`: 마감일까지 3일/1일/0일 남은 공지. 둘 다 해당하면 new 하나만 내보낸다. 선정된 공지는 제목·본문의 참여 대상과 관계없이 모두 포함한다.
- 이미 마감한 공지는 자동 선정에서 제외한다. 당일 알림은 마감 시각 확인 전이며 '지금 신청 가능'을 보장하지 않는다.
- 선정되는 공지는 대상 날짜에 실제 상세 확인에 성공한 데이터여야 한다. 오래된 저장 자료만 있으면 내보내지 않고 해당 채널 오류를 남긴다. 부분 실패 시 성공한 글은 제공하고 실행 보고서의 실패도 errors에 남긴다. 보고서에서 상세 실패가 확인된 URL은 제외한다.
- 같은 글은 한 채널 안에서 한 번, 공유 게시판 글은 연결된 각 채널에 한 번씩 담는다. 사용자별 여러 채널의 최종 중복 제거는 전달받는 쪽에서 공지 id를 기준으로 처리한다. source는 읽기 쉬운 채널 이름이다.
- 날씨·학식·학사일정을 수집하지 않았거나 실패하면 해당 값은 null/빈 배열로 두고 errors에 이유를 명시한다. 정상적인 자료 없음으로 표현하지 않는다. 실제 수집은 아래 항목과 docs/daily-sources.md를 따른다.
- 공지가 없는 채널도 channels에 남긴다. 운영 전·오늘 확인 없음·요청 실패를 errors로 구분한다. 이미지/첨부 본문은 원문 body의 null을 유지하고 확인하지 못한 본문을 오류에 표시한다.
- 오늘 날짜의 파일만 현재 DB에서 만든다. 과거·미래의 재현은 당시 DB 스냅샷과 판정 시각이 필요하다. 임의 날짜로 최신 DB를 과거 자료라고 쓰지 않는다.

## 날씨·학식·학사일정 값 (2026-10-01)

최상위 전달 구조는 유지한다. weather 기온은 섭씨 숫자/null, rain_prob는 0~100의 일 최대 강수 확률(%, 비·눈 포함)/null, summary는 일별 대표 날씨 문자열/null이다. 현재 대구 대표 지역 예보이며 캠퍼스 관측/아침 현재 날씨와 다르다. 메뉴는 음식 이름의 비어 있지 않은 문자열 배열, place는 원문 식당명, time은 원문에 적힌 시간 범위 문자열 또는 null이다. 다른 메뉴의 시간을 복사하지 않는다. 현재 지원하는 여섯 식당 채널은 모두 선택 채널이다.

schedule의 start는 공식 달력 연도로 확인한 시작 날짜, end는 원문에 명시된 종료 날짜 또는 null, dday는 start에서 대상 날짜를 뺀 정수다. 오늘부터 3일 이내 시작하거나 종료일까지 진행 중인 일정만 전달하며 진행 중이면 dday가 음수일 수 있다. 단일 시작 날짜로 종료일을 추정하지 않는다. 대학원 일정도 원문 제목 그대로 포함한다.

data/raw/<날짜>/context.json은 수집 내부 자료이며 date/collected_at/weather/channels/schedule/errors/sources를 담는다. sources는 source/url/checked_at 배열이다. 실제 확인 시각과 파일 생성 시각을 구분하며 대상 날짜와 한국 시각이 맞는 자료만 합친다. 읽기·쓰기는 store를 이용한다. 브리핑 담당은 기존 items.json을 읽는다.

## 운영 측정 보고서 (2026-10-01)

collector.run의 최종 보고서는 기존 channels와 request_count에 started_at/finished_at/duration_sec를 추가한다. request_count는 날씨·학식·일정을 함께 수집하면 그 요청도 포함한다. extras에는 request_count/errors/sources를 담는다. 중간 저장 보고서는 완료한 게시판만 담을 수 있다. context.json에도 해당 수집 요청 수 request_count를 추가한다. 기존 전달 items.json 구조는 유지한다. 측정 범위·실제 결과·새벽 설정은 docs/operations.md를 따른다.


### 개인화 인사 확장 (2026-10-06)

앱용 `segments`에 선택적인 `greeting` 구간을 추가한다. `channel_id`도 `greeting`이며, 기존 필드에 `personal_template: "안녕하세요, {name}님. ..."`을 제공한다. 실제 학생 이름은 JSON에 포함하지 않는다. `audio`는 이름 없는 기본 인사 MP3로 필수 제공한다. `intro`는 날씨와 확인된 학교 이벤트를 제공한다. `greeting`이 없는 이전 파일은 기존 `intro`를 그대로 재생한다. 공지 카드의 원문 제목·링크는 요약으로 바꾸지 않는다.

## 게시판 간 같은 공지의 공유

수집 DB와 `items.json`은 게시판별 원본을 그대로 보존한다. 중복 비교용 사본에서 제목의 `[안내]`, `[공지]`, `[공통]`, `[교직]`, `[대학원]`, `[학부]`, `[재안내]` 접두어와 장식 기호, 본문의 미리보기 UI 문구·붙임 목록·단순 인사·연락처 안내를 정리한다. `[필수]`는 의미를 보존한다. 저장 원문과 모델 입력은 바꾸지 않는다. 정리한 제목·본문·저장 마감일이 같으면 합친다. 제목·마감일이 같고, 본문의 숫자 순서·횟수와 대상·자격·장소·신청·일정·예정/확정·불가/제외 등을 포함한 보호 문장이 같으면 100자 이상 본문에 한해 양방향 문자열 유사도 90% 이상도 합친다. 보호 문장 비교는 규칙이므로 모든 의미 차이를 판별하지는 못한다. 본문 없는 글과 짧은 유사 문장은 서로 다른 ID끼리 합치지 않는다. 대표 글과 직접 비교하며 유사한 글을 연결해서 연쇄 병합하지 않는다.

내부 공지 segment의 `notice_refs`에는 모든 원문을 `{channel_id, postId, title, url, posted_at, deadline, reason}`으로 보존하고 `channel_ids`에는 관련 채널을 연결한다. 동일 그룹의 대본과 음성은 한 번만 만든다.

새 앱 출력의 공지 segment는 `kind: notice`와 고유 `id`, 관련 `channel_ids`, `notice_refs`를 제공한다. `channel_id`는 이 공지 구간의 ID이며 채널 선택에는 `channel_ids`를 사용한다. 카드의 `channel_id`와 `postId`로 해당 학과 원문을 연다. 여러 학과를 골라도 재생 목록은 segment ID당 한 번만 추가하고 카드에는 선택한 학과의 원문만 표시한다. 인사·날씨·식당·마무리와 이전 게시판 단위 출력은 기존 방식으로 지원한다. 기존 배포 음성은 자동으로 변경하지 않으며 다음 브리핑 생성부터 새 방식이 적용된다.

## 공개 자료와 원문 대조

운영 저장소는 `hoyeol903/KNU-AUDIO-public`이며, 기존 저장소는 비공개 기록 보관용입니다. `collector/privacy.py`가 저장 전에 명시적 학번·주민등록번호·010 휴대전화와 학번에 연결된 성명을 `[개인정보 가림]`으로 대체합니다. 날짜·마감·장소·조건과 공식 부서 연락처는 유지합니다. 검수 기준은 개인정보를 가린 원문입니다. items.json과 DB 필드는 변경하지 않으며, 저장된 내용 해시는 가린 내용으로 계산합니다. 가림 표시는 사실 정보로 읽거나 대본에 넣지 않습니다. 새 개인정보 형태는 사람이 검토하며, 자동 가림만으로 공개 적합성을 보증하지 않습니다.


## 교류 모집글 API

교류 모집글·신청은 수집 공지 JSON과 분리된 공유 API에 저장한다. 상세 필드·권한·API 계약은 [교류](community.md)를 따른다. 기존 브라우저 개인 글은 공유 서버에 자동 업로드하지 않는다. GitHub Pages는 교류 API를 실행하지 않으며 별도 API 주소 연결이 필요하다.
