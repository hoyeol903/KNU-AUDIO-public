# UI 요청 5·9·11 — 호반우, 시작 화면, KNUA 로고

## 반영 위치

- `tools/knua-app.html`: `<head>`에 파비콘·홈 화면 아이콘, CSS 끝에 브랜드/호반우/스플래시 스타일, `#view` 밖 `#splash` 오버레이.
- `bootSplash`, `splashReady`, `dismissSplash`: 자료 요청과 동시에 시작, 자료 준비 + 최소 1.2초 후 종료, 늦어도 2.5초 종료. 터치와 오류는 즉시 종료. 모션 줄이기는 150ms. `loadMeta` 재시도나 화면 이동에서는 재등장하지 않음.
- `chapters`: 원래 구간 ID를 화면 내부 `CH[].id`로 보존. 원본 JSON은 그대로 사용.
- `moodOf`, `weatherMood`, `liveMood`, `hobanu`, `paintHobanu`: 상태 선택과 이미지 교체. `paintProgress`에서 그림이 달라질 때만 해당 DOM 갱신.
- `vPlayer`, `vChat`, `vHome`: 같은 판단 규칙으로 호반우 표시. 대본의 지난/앞 구간은 각각의 내용에 맞는 그림, 현재 구간은 재생 상태에 맞는 그림.
- `vStart`, `deptList`, `avatar`: 선택한 B안의 호반우형 로고와 단과대 그림을 학과 선택 목록에도 표시. 전용 그림이 없는 학부는 공통 호반우로 표시.
- `vFeedback`, `vWeek`: 알림·감사·쉬는 상황에 맞는 그림.
- `collector/export_app.py`: `tools/hobanu`, `tools/branding`을 `output/app/data/`로 복사하는 정적 자산 배포만 추가. 수집·대본·음성·JSON 계약은 변경하지 않음.

## 표정 규칙

| 상황 | 데이터 기준 | 그림 |
|---|---|---|
| 인사 | `greeting`, 또는 `intro`에서 날씨 문장 전 | 공식 손 인사 |
| 비 | 날씨 상태 `ok`, `rain >= 60` 또는 요약의 비·소나기·뇌우 | 우산 |
| 맑음 | 상태 `ok`, 요약에 맑음이며 흐림·구름 없음 | 선글라스·해 |
| 눈 | 상태 `ok`, 요약에 눈 | 기본 호반우 + 눈 아이콘 |
| 흐림·기타·실패 | 위 조건에 맞지 않는 날씨 | 중립 호반우 + 구름 아이콘; 맑음으로 추측하지 않음 |
| 마감 | 카드 `kind/section`이 `마감 임박` | 걱정하는 표정·시계 |
| 새 소식 | 일반 게시판 구간 | 공식 확성기 |
| 학식 | `meal-` ID 또는 카드 종류 `학식` | 공식 식사 |
| 공지 없음 | `empty` ID | 공식 센트럴파크에서 쉬는 모습 |
| 마무리 | `outro` 또는 재생 완료 | 공식 하트 |
| 일시정지 | 아직 완료되지 않았고 `P.playing === false` | 기본 자세, 반복 움직임 없음 |

`intro` 안의 날씨 문장 전환은 기존 대본 말풍선과 같은 글자 수 기반 추정 시간을 사용한다. 문장별 실제 음성 타임스탬프는 데이터에 없어 정확한 입 모양 동기화는 하지 않는다. `greeting` 구간이 별도로 있는 형식도 처리한다.

GIF 대신 투명 WebP와 CSS 움직임을 사용한다. 일시정지 때 반복 움직임을 멈추고 `prefers-reduced-motion`에서는 전체 앱의 애니메이션/전환이 꺼진다. 이미지 오류 시 기존 내장 호반우를 대신 표시한다.

## 자산

- `tools/hobanu/*.webp`: 9장, 각각 **480×480**, 공통 하단 기준선 **448px**, 투명 배경, 약 19~35KB/장.
- 외부 파일로 분리해 이미 큰 HTML의 base64 크기를 늘리지 않고 브라우저 캐시를 재사용한다.
- `tools/branding/logo-knua.svg`, `logo-knua-dark.svg`: **344×100**, 심볼 + KNUA. 글자는 직접 만든 path라 폰트 설치 여부와 무관하다.
- `logo-symbol.svg`, `logo-symbol-dark.svg`, `favicon.svg`: **100×100** viewBox. 파비콘 SVG는 기기 테마에 반응한다.
- `favicon-32.png`: **32×32**. `apple-touch-icon-180.png`: **180×180**, 불투명 와인색 바탕.
- 브랜드 주색 `#8B1E3F`, 어두운 배경의 밝은 버전 `#F2A6BB`.
- 로고 시안은 `docs/ui-branding/concepts/`와 `logo-concepts.png`. 선택된 B안은 짧은 뿔·넓은 귀·각진 얼굴·이마 줄무늬로 다듬었다.

## 공식 자료 확인 (2026-10-06)

- [경북대 캐릭터](https://www.knu.ac.kr/wbbs/wbbs/contents/index.action?menu_url=intro/about04_03&menu_idx=9)
- [경북대 로고 및 UI](https://www.knu.ac.kr/wbbs/wbbs/contents/index.action?menu_url=intro/about04&menu_idx=194)
- 공식 감정 PNG: [Character_Emoticon_png.zip](https://www.knu.ac.kr/wbbs/wbbs/download/Character_Emoticon_png.zip). 인사·공지알림·자신감·사랑 B에서 전신을 추출하고 비율 유지·투명 여백·WebP 변환.
- 공식 캠퍼스 PNG: [new_ch_app2_png.zip](https://www.knu.ac.kr/wbbs/wbbs/download/new_ch_app2_png.zip). 복돈이, 본관+센트럴파크를 사용.
- 비·맑음·마감 3장은 기존 호반우를 참조해 생성한 **프로젝트용 응용 이미지**다. 학교가 제공한 공식 표정으로 표기하지 않는다. 사용한 프롬프트는 `ui-branding/image-prompts.md`.
- 교류 카드의 `community.webp`와 캘린더 제목의 `calendar.webp`는 사용자 선택·참조 이미지로 만든 프로젝트용 응용 이미지다. 생성·배경 추출 기록은 `ui-branding/image-prompts.md`에 있으며, 학교 공식 배포 이미지로 표기하지 않는다.
- 피드백 화면의 `feedback.webp`(책상에 앉아 노트북으로 피드백을 읽는 호반우)는 사용자가 이미지 생성 도구로 만든 프로젝트용 응용 이미지다. 투명 배경을 유지한 채 여백을 정리해 480×480 WebP로 저장했다. 학교 공식 배포 이미지로 표기하지 않는다.
- 로고는 경북대의 붉은 색 계열과 호반우의 형태를 참고한 크누아 자체 심볼이며 학교 엠블럼을 사용하지 않는다.
- 시작 화면 뒤 원은 경북대 공식 엠블럼(`emblem_jpg.zip`의 원형 엠블럼, [로고 및 UI](https://www.knu.ac.kr/wbbs/wbbs/contents/index.action?menu_url=intro/about04&menu_idx=194))을 배경 투명 PNG(`tools/branding/knu-emblem.png`)로 바꿔 테마 색 10% 불투명도로 깐다. 학교 안내상 KNU UI는 상표 등록되어 있고 상업적 사용은 금지된다. 교내 비상업 프로젝트 기준으로 쓰며, 상업적 사용이나 외부 배포 시에는 학교 대외협력홍보과(053-950-2826)에 확인한다.

### 단과대 확인

공식 페이지의 단과대 다운로드는 20개 PNG다. 현재 저장소의 23장과 같은 원본 이미지 세트가 아니어서, 기존 파일을 공식 파일이라고 단정하지 않았다. 기존 그림·이름 연결은 유지하고 선택 화면에서 보이도록 연결했다.

| 공식 파일 번호 | 공식 그림의 학부/단과대 | 현재 대응 파일 |
|---|---|---|
| 01 | 인문대학 | 06.webp |
| 02 | 사회과학대학 | 09.webp |
| 03 | 자연과학대학 | 07.webp |
| 04 | 경상대학 | 14.webp |
| 05 | 공과대학 | 02.webp |
| 06 | IT대학 | 04.webp |
| 07 | 농업생명과학대학 | 01.webp |
| 08 | 예술대학 | 13.webp |
| 09 | 사범대학 | 03.webp |
| 10 | 의과대학 | 16.webp |
| 12 | 치과대학 | 17.webp |
| 13 | 수의과대학 | 15.webp |
| 14 | 생활과학대학 | 12.webp |
| 15 | 간호대학 | 18.webp |
| 16 | 약학대학 | 19.webp |
| 17 | 첨단기술융합대학 | 10.webp |
| 18 | 생태환경대학 | 08.webp |
| 19 | 과학기술대학 | 05.webp |
| 20 | 행정학부 | 22.webp |
| 21 | 자율전공학부/자율미래인재학부 공용 | 20.webp / 21.webp |

**글로벌자율학부 전용 그림은 해당 공식 페이지·다운로드에서 확인하지 못했다.** AI대학(11.webp)과 공과대학/농업생명과학대학(23.webp)도 공식 다운로드의 별도 전용 그림을 확인하지 못했다. 글로벌자율학부에는 학부 전용이라고 표시하지 않는 공통 호반우를 사용한다.

## 확인

```sh
.venv/bin/python -m collector.export_app
.venv/bin/python -m http.server 8000 --directory output/app
node --test tests/ui-branding.test.mjs
.venv/bin/python -m pytest -q -p no:cacheprovider collector/tests/test_export_app.py collector/tests/test_app_profile.py briefing/tests/test_app_export.py
```

브라우저 확인 항목: 390px 라이트/다크, 첫 실행 이름·학과→게시판 선택→사용법 안내, 기존 사용자, 호반우 구간 전환·일시정지·대본, 빠른/응답 없는 연결, 오류/재시도, 스플래시 터치 생략, 화면 이동 시 재등장 방지, 모션 줄이기.
