# 오늘 전달할 공지 고르기


최신 추가: 날씨·학식·학사일정도 수집해 합칠 수 있다. `docs/daily-sources.md` 참고. 전체 수집은 `python -m collector.run --write-items --collect-extras`, 기존 DB와 오늘 context.json 합치기는 `python -m collector.daily_items`. 실제 파일은 7채널·공지 0개·식단 13개·일정 1개·오류 0개다. 아래 초기 결과는 공지 부분만 구현한 시점의 기록이다.

2026-10-01. 저장된 공지에서 오늘 신규와 마감 알림을 골라 `data/raw/<날짜>/items.json`으로 전달한다. 대본·음성·웹 기능은 만들지 않았다.

## 고르는 기준

| 경우 | 선정 |
|---|---|
| 운영 시작 이후 오늘 처음 발견했고 게시일이 최근 30일인 글 | new |
| 마감까지 3일·1일·0일 남은 글 | reminder |
| 신규와 마감 알림에 동시에 해당 | new 한 번 |
| 처음 적재한 과거 공지·수정만 된 글 | 신규로 선정하지 않음 |
| 이미 마감·미래 게시일 | 제외 |
| 오늘 상세를 확인하지 못한 후보 | 제외하고 errors에 남김 |

공지는 채널별로 넣고 각 글에 channel_id/source/dday/reason을 붙인다. 같은 게시판을 공유하는 채널은 같은 공지 ID를 각각 받는다. 한 채널 안에서는 중복 저장하지 않는다. 사용자별 채널을 합칠 때는 받은 공지 ID로 중복을 제거할 수 있다. 마감 시각은 검증하지 않으므로 당일 공지를 '지금 신청 가능'이라고 단정하지 않는다.

수집기 실행 보고서에 상세 실패가 있는 주소는 제외한다. 일부 글을 못 읽어도 성공한 글은 전달하고 실패 내용을 errors에 넣는다. 이미지·첨부 전용 글은 body=null을 유지하며 제목과 원문 링크만 제공하고 본문 미확인을 표시한다.

## 실행

프로젝트 루트에서, 현재 로컬은 python 대신 `/opt/anaconda3/bin/python3`를 쓴다.

```bash
# 수집한 뒤 입력 파일까지 만들기 (기본 5개 채널)
python -m collector.run --write-items

# 필요한 채널만 수집해서 만들기
python -m collector.run --channel-id knu-academic --write-items

# 기존 DB로 생성; 새 인터넷 요청 없음
python -m collector.daily_items

# 기존 DB와 해당 날짜의 수집 보고서를 함께 반영
python -m collector.daily_items \
  --collection-report data/runs/daily-window-20261001.json \
  --collection-report data/runs/public-notices-start-20261001.json

# 인터넷 없는 테스트
python -m pytest -q
```

`collector.daily_items`도 --channel-id 반복 지정과 --db-path/--output을 지원한다. 보고서는 대상 채널의 오늘 실행 결과를 전달한다. 다른 날짜의 보고서는 받지 않는다. 단독 생성은 DB에 기록된 오늘 상세 확인 시각을 사용하며 보고서를 주지 않으면 최근 수집 오류를 전달할 수 없다. 실제 운영에서는 `collector.run --write-items`로 연결한다. 같은 DB를 갱신하는 명령은 하나씩 실행한다.

테스트 DB를 사용할 때는 `collector.run --db-path ... --report-path ... --write-items --items-path ...`로 모든 결과 경로를 별도로 지정한다. `--items-path`는 --write-items와 함께 사용한다. 전달 파일의 JSON 쓰기는 store에서 검증 후 원자적으로 수행한다.

## 실제 결과와 샘플

- 실제 저장 자료로 생성한 `data/raw/2026-10-01/items.json`: 기본 학교·전자공학부·국문·영문·수학 **5개 채널, 선정 공지 0개**. 초기 적재를 오늘 신규로 잘못 내보내지 않았고, 이번 날짜에는 확인된 마감이 3일/1일/당일에 해당하지 않았다. 새 사이트 요청은 하지 않았다.
- 다른 담당자의 연결 시험용 `samples/items.example.json`: 가상 신규 1개와 마감 3일 전 공지 1개. 제목·출처에 샘플임을 표시했고 example.com 주소를 사용했다. 실제 공지와 섞지 않는다.
- 날씨·학식·학사일정 수집은 아직 없다. 날씨 필드는 null, meals/schedule은 빈 배열이며 **미구현 3개를 errors에 명시**했다. 정상적으로 자료가 없다는 뜻이 아니다.
- 기존 공지 DB·운영 기준은 이 파일 생성으로 바뀌지 않는다. 과거/미래 날짜의 생성은 당시 DB 스냅샷 없이 제공하지 않는다.

테스트 148개 통과. 신규·마감 경계, 초기 적재, 오래된 자료, 부분 실패, 공유 채널, 이미지 본문, 중복·잘못된 dday 저장 거부, 실제 수집 명령과 파일 생성 연결을 인터넷 없이 확인했다.

날씨·학식·학사일정 실제 값 수집은 추가했다. 수동 공지는 필요할 때 추가한다. 다음 후보는 선택 출처 보강·운영 점검·저장소 이전 후 매일 새벽 자동 수집이다.
