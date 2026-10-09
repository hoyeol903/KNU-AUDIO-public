# 날씨·학식·학사일정 수집


2026-10-01 실제 요청 검증 완료. 추가 의존성·API 키 없이 기존 HTTP 요청기와 store를 쓴다. 서버별 요청 종료 후 1초 간격, 추가 재시도 최대 2회, 연결 하나를 유지한다.

## 실행

프로젝트 루트에서 실행한다. 현재 로컬 Python은 `/opt/anaconda3/bin/python3`다.

```bash
# Actions와 같은 자동 수집: 공지 + 날씨·일정 (식당 요청 없음)
python -m collector.run --write-items --collect-extras --skip-meals

# 로컬에서 필요할 때 여섯 식당만 수집 → 같은 날의 날씨·일정은 context.json에 보존
python -m collector.daily_sources --meals-only

# 학식 수집 → 앱 내보내기 → 새 브랜치 push와 PR 생성까지 한 번에
python -m tools.update_meals

# 당일 공지 보고서를 넣어 items.json 갱신 (인터넷 요청 없음)
python -m collector.daily_items --collection-report "data/runs/<당일-공지보고서>.json"

# 정적 미리보기 자료 갱신
python -m collector.export_app

# 날씨·학식·일정만 실제 수집 → context.json
python -m collector.daily_sources

# 저장된 오늘 공지 + 오늘 context.json → items.json (인터넷 요청 없음)
python -m collector.daily_items

# 원본도 보관할 때 (HTML/날씨 JSON)
python -m collector.daily_sources --fixtures collector/tests/fixtures/daily-sources

# 인터넷 없는 전체 검사
python -m pytest -q
```

`--collect-extras`는 `--write-items`와 함께 사용한다. Actions는 `--skip-meals`를 함께 사용해 날씨·일정만 요청한다. 여섯 식당은 로컬 `--meals-only` 명령에서만 요청하며, 같은 날짜의 날씨·일정 자료는 보존한다. 로컬 식단 반영 후 `daily_items`에는 당일 공지 수집 보고서(`data/runs/`의 해당 실행 파일)를 전달해야 공지 확인·오류 정보가 유지된다. 필요하면 `export_app`으로 정적 미리보기를 갱신한다. 로컬 식단 결과는 원격에 자동 업로드되지 않는다. 날짜가 다른 context는 병합하지 않는다. 공지 DB 변경 명령은 하나씩 실행한다.

수동 `daily_sources` 수집은 원격에 올리지 않는다. `python -m tools.update_meals`는 깨끗한 작업 트리, `gh` 로그인, 올바른 저장소를 확인한 뒤 새 기능 브랜치에서 학식을 수집하고 앱을 내보내 PR을 만든다. 일부 수집 오류가 있어도 오늘 메뉴 또는 주간 식단 중 사용할 자료가 있으면 오류를 PR에 기록한다. 사용할 식단 자료가 전혀 없으면 게시를 멈춘다. 공지 DB와 `items.json`은 이 명령에서 갱신하지 않는다. 실제 생협 요청은 발생하며, 오디오를 만들거나 PR을 자동 병합하지 않는다. PR이 병합되면 앱 배포 워크플로가 실행된다. 기존 수동 명령도 그대로 사용할 수 있다.

context.json은 data/raw/<날짜>/에 저장된다. date/collected_at/weather/channels/schedule/errors와 sources(출처 URL·실제 확인 시각)를 담은 수집 내부 자료다. 브리핑 담당에게 전달하는 items.json 형식은 그대로다. 한 출처가 실패해도 성공한 출처는 저장·전달한다. 실제 수집 명령은 오류가 있으면 종료 코드 1을 반환한다.

## 무엇을 가져오나

| 항목 | 원문 | 처리 |
|---|---|---|
| 대구 날씨 | [Open-Meteo 공식 문서](https://open-meteo.com/en/docs) | 일별 최저·최고 기온(°C), 일 최대 강수 확률(%), 일별 대표 날씨 코드. 코드·단위·날짜·한국 시간대를 검증 |
| GP감꽃식당 | [생협 식단](https://coop.knu.ac.kr/sub03/sub01_01.html?shop_sqno=46) | meal-46, 오늘 메뉴와 각 메뉴에 명시된 운영시간 |
| 정보센터식당 | [생협 식단](https://coop.knu.ac.kr/sub03/sub01_01.html?shop_sqno=35) | meal-35, 오늘 중식·석식 메뉴. 다른 메뉴의 시간을 복사하지 않음 |
| 공학관 교직원 식당 | [생협 식단](https://coop.knu.ac.kr/sub03/sub01_01.html?shop_sqno=85) | meal-85, 원문 이름 `공학관교직원식당(외부업체)` 기준으로 식단 확인 |
| 공학관 학생 식당 | [생협 식단](https://coop.knu.ac.kr/sub03/sub01_01.html?shop_sqno=86) | meal-86, 원문 이름 `공학관학생식당(외부업체)` 기준으로 식단 확인 |
| 복지관 교직원 식당 | [생협 식단](https://coop.knu.ac.kr/sub03/sub01_01.html?shop_sqno=36) | meal-bokji, shop_sqno=36으로 연결해 원문 식당명·날짜 확인 |
| 카페테리아 첨성 | [생협 식단](https://coop.knu.ac.kr/sub03/sub01_01.html?shop_sqno=37) | meal-37, 오늘 메뉴와 원문 식당명·날짜 확인 |
| 학사일정 | [학교 공식 2026 일정](https://www.knu.ac.kr/wbbs/wbbs/user/yearSchedule/index.action?menu_idx=43&vo.search_year=2026) | 오늘 진행 중이거나 3일 이내 시작하는 일정. 대학원 일정도 원문대로 포함 |

여섯 식당 채널은 모두 선택 채널이다. 수집했다고 모든 사용자가 필수로 듣는다는 뜻이 아니다. 지원 식당은 GP감꽃, 정보센터, 공학관 교직원·학생, 복지관 교직원, 카페테리아 첨성이다. 상주 지역 날씨는 지원하지 않는다.

대구 좌표 35.87028/128.59111은 Open-Meteo 지명 검색에서 country_code=KR, admin1=Daegu인 결과를 사용했다. 캠퍼스 관측값이 아닌 대구 대표 지역 예보다. API가 반환한 예보 격자 좌표는 요청 좌표와 다를 수 있다. summary는 그날의 대표 기상 상태이며 아침 현재 날씨를 뜻하지 않는다. rain_prob는 비·눈 등을 포함한 강수 확률이다.

생협은 selDate=YYYY-MM-DD로 날짜를 지정한다. HTML 날짜 열의 MM/DD로 메뉴를 선택한다. 실제 페이지에 2026-10-01이 월요일로 표시되는 요일 오류가 있어 요일 문구는 사용하지 않는다. 연도는 요청 날짜를 사용하며 원문 날짜 열과 식당 이름을 확인한다. 주간 표에 오늘 날짜가 없거나 메뉴 표가 없으면 오류다. 빈 메뉴도 미게시 오류이며 휴무로 추정하지 않는다. 원문에 휴무가 명시된 경우에만 정상 빈 식단을 허용한다. 시간 미제공은 null, 가격·운영시간 안내는 음식 이름에서 제외한다. 같은 식사 구분에서도 메뉴별로 배열 항목을 나누며 현재 전달 계약에는 별도 중식/석식 필드가 없다.

학사일정은 월별 제목의 달력 연도와 span.day의 시작일을 대조한다. 기간에 명시된 종료일만 사용하고 종료일 없는 단일 날짜 표시는 end=null로 남긴다. 연말 기간은 명시된 다음 연도만 인정한다. 연도가 생략된 역전 기간은 추측하지 않고 오류다. 12월 말에는 다음 3일에 걸치는 다음 연도의 공식 페이지도 요청한다. 현재는 공식 HTML을 직접 읽으며 수동 data/schedule.yaml 반영 기능은 추가하지 않았다.

## 실제 결과

- 오늘 기본 공지 5채널 + 선택 식당 2채널 = items.json 7채널. (이 결과는 2026-10-01 당시 기록이며 현재 지원 식당은 6곳이다.)
- 공지 선정 0개(신규·마감 알림 조건에 해당하는 오늘 확인 자료 없음).
- 날씨: 부분적으로 흐림, 최저 14.1°C / 최고 21.3°C, 일 최대 강수 확률 45%. 확인 시점 예보이며 실제 날씨·확률은 이후 달라질 수 있다.
- GP감꽃 식단 1개 + 정보센터 식단 12개 = 13개. 식당 수나 음식 이름 수와 다르다.
- 진행 중 일정 1개: [대학원] 심사용 논문 접수, 2026-09-30~2026-10-02, dday=-1.
- 수집/생성 오류 0개. 원본은 collector/tests/fixtures/daily-sources/에 있다.

전체 테스트 159개 통과. 오프라인 검사에는 날짜별 메뉴 선택·미게시/휴무 구분·식당 불일치·학사일정 연도와 기간·날씨 단위/누락/범위·부분 실패·지난 자료 거부·잘못된 JSON 저장 시 원래 파일 보존이 포함된다.

2026-10-03에는 추가 식당 4곳의 오늘 주소를 각 한 번 확인해 모두 HTTP 200을 받았다. 원문 식당명·주간 표 구조는 확인했지만 토요일 메뉴 항목이 게시되지 않아 네 곳 모두 context에 확인 오류로 남겼다. 휴무로 추정하지 않았다. 보관한 원문 fixture의 2026-10-06 식단은 기존 parser로 확인했으며, 이 날짜 자료는 오늘 메뉴로 전달하지 않는다.

다음 후보: 운영 점검, 저장소 이전 후 새벽 자동 실행. 수동 공지는 사용자가 필요할 때 넣기로 했다. 자동 실행은 아직 설정하지 않았다.
