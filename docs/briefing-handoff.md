# 브리핑 담당에게: 화면에 음성 붙이기

2026-10-03 기준. 대본·음성 담당이 파일 하나를 정해진 자리에 넣으면 앱 화면에서 바로 재생된다. 형식은 `docs/contracts.md`의 `briefing.json`을 그대로 쓰면 된다.

## 한눈에

| 항목 | 내용 |
| --- | --- |
| 받는 자료 | `data/raw/<날짜>/items.json` (지금과 같다) |
| 넣을 자리 | `output/app/data/briefing/segments.json` |
| 음성 파일 | 같은 폴더(`output/app/data/briefing/`)에 넣고 파일 이름을 `audio`에 적는다 |
| 예시 | `samples/briefing.example.json` (2026-10-03 실제 자료로 만든 것) |

## 5분 만에 확인하기

```bash
python -m collector.export_app
mkdir -p output/app/data/briefing
cp samples/briefing.example.json output/app/data/briefing/segments.json
python -m http.server 8000 --directory output/app
```

http://127.0.0.1:8000 을 열고 이름과 학과(전자공학부)를 넣으면 홈에 재생 버튼이 생긴다. 예시에는 음성 파일이 없어서 브라우저가 대본을 대신 읽는다. 예시의 `date`가 화면 자료의 기준일과 다르면 재생 버튼이 나오지 않으니, 그때는 `date`를 `output/app/data/meta.json`의 `asOf`와 같게 고친다.

## 파일 형식

계약 문서의 이름 그대로다. `postId` 하나만 더 넣기를 권한다.

```text
{ "date": "YYYY-MM-DD",
  "segments": [ {
    "id": "...", "channel_id": "...", "title": "...",
    "script": "...", "audio": "파일 이름 또는 null", "duration_sec": 22.4,
    "items": [ { "section": "날씨|마감 임박|학식|소식", "title": "...", "detail": "...",
                 "url": "...", "dday": null, "postId": "..." } ]
  } ] }
```

| 필드 | 화면이 쓰는 방식 |
| --- | --- |
| `date` | 화면 자료의 기준일(`asOf`)과 같아야 재생된다. 다르면 "브리핑이 아직 준비되지 않았어요"로 나온다 |
| `channel_id` | 어느 구간인지 정한다. 아래 "구간 규칙" 참고 |
| `title` | 재생 화면의 구간 제목, 잠금 화면 제목 |
| `script` | 대본 보기에 그대로 나온다. `audio`가 null이면 브라우저 음성이 이 글을 읽는다 |
| `audio` | `output/app/data/briefing/` 기준 파일 이름. 예: `intro.mp3` |
| `duration_sec` | 진행 막대 길이. 없으면 음성 파일의 실제 길이를 쓴다 |
| `items[]` | 구간을 듣는 동안 보이는 요약 카드 |
| `items[].postId` | `items.json`의 공지 `id`. 넣으면 카드의 "자세히"가 그 글을 열고 남은 일수를 화면이 계산한다 |
| `items[].url` | 카드의 "원문 보기" 주소. 공지의 `url`을 그대로 넣는다 |
| `items[].dday` | `postId`가 없을 때만 쓴다. 넣지 않아도 된다 |

## 구간 규칙

사람마다 고른 게시판이 달라서, 화면이 구간을 골라 이어 붙인다. 순서는 인사 → 오늘 소식이 있는 내 게시판 → 내 식당 → 마무리다.

| `channel_id` | 누가 듣나 |
| --- | --- |
| `intro` | 모두. 인사와 날씨 |
| 게시판 채널 ID (`knu-academic`, `notice-df44dd8507c1` 등) | 그 게시판을 고른 사람만. `items.json`의 `channels[].channel_id`와 같다 |
| 식당 채널 ID (`meal-46` 등) | 그 식당을 켠 사람만 |
| `empty` | 내 게시판에 오늘 소식이 하나도 없는 사람만. 게시판 구간 대신 들어간다. 없어도 된다 |
| `outro` | 모두. 마무리 |

- 오늘 소식이 없는 게시판은 구간을 만들지 않는다. 만들어도 화면이 건너뛴다.
- 구간은 하나만 들어도 자연스러워야 한다. 앞뒤에 어떤 구간이 올지 모른다.
- 사용자 이름은 대본에 넣을 수 없다. 음성은 모두가 같은 파일을 듣는다.
- 제목, 날짜, 마감일, 메뉴는 `items.json`의 값 그대로 쓴다.

## 화면이 알아서 하는 것

- 구간 이어 재생, 이전·다음 구간, 재생 속도, 잠금 화면 제어.
- 파일이 없거나 날짜가 다르면 재생 영역만 비활성으로 두고 나머지 화면은 그대로 쓴다.
- 음성 파일을 못 불러온 구간은 건너뛴다.

## 아직 같이 정할 것

1. **파일 위치.** 계약 문서에는 `web/public/briefings/<날짜>/briefing.json`으로 적혀 있다. 지금 화면은 `output/app/data/briefing/segments.json`을 읽는다. 화면을 그대로 쓰기로 했으니 이 위치로 맞추고 계약 문서를 고치자고 제안한다.
2. **음성 파일 형식.** 휴대폰 브라우저에서 바로 재생되는 형식(mp3 또는 m4a)이어야 한다.
3. **식당 구간.** 식당이 6곳이고 사람마다 켠 곳이 다르다. 식당마다 구간을 따로 만들지, 학식 구간을 빼고 화면에서만 보여줄지 정한다.
4. **매일 실행 순서.** 수집 → 브리핑 생성 → 화면용 자료 내보내기 순서로 한 워크플로에 묶어야 한다.
