# 비교과 공지

홈의 '내 게시판'에서 **저장한 공지 바로 밑**에 '비교과 공지' 칸이 고정으로 있다. 학과 게시판과 별도로, 비교과 사이트의 공지를 한 화면에 모아 본다.

- 화면: KNUcube 바로가기, 모아 보는 사이트 켜고 끄기, 오늘의 소식(새 글·마감 알림), 사이트를 합친 최근 글(사이트마다 최근 30개).
- 새로 추가한 사이트는 모든 사용자에게 자동으로 켜진다. 사용자가 끈 사이트만 브라우저(`store.ncOff`)에 남는다.
- 비교과 글은 오늘 브리핑 음성과 홈 '오늘 숫자'에는 넣지 않는다. 학과 공지 브리핑을 길게 만들지 않기 위해서다.
- '원하는 비교과 사이트 추가 요청'은 피드백 구글 폼으로 연결한다. 요청이 오면 아래 순서로 팀이 추가한다.

## KNUcube를 수집하지 않는 이유

[KNUcube](https://knucube.knu.ac.kr/knucube_index.jsp)는 `robots.txt`가 `Disallow: /`로 자동 수집을 모두 거부하고, 첫 화면부터 통합 로그인(SSO)이 필요하다(2026-10-30 확인). 수집하려면 학생 계정 비밀번호를 수집 서버에 넣어야 해서 계정 위험이 크고, 로그인 뒤 내용을 공개 앱에 다시 싣는 문제도 있다. 그래서 바로가기만 둔다. 공식 목록·RSS를 학교에서 받으면 그때 수집 사이트로 추가한다.

## 사이트 추가 순서

1. 공개 여부 확인: 로그인 없이 목록·상세를 볼 수 있어야 한다. 학교 공통 CMS(`home.knu.ac.kr/HOME/...`) 게시판은 기존 학과 게시판과 같은 방식으로 수집한다(이 CMS의 `robots.txt`에는 `Disallow: /H*`가 있으며 기존 게시판도 같은 조건이다). 그 밖의 사이트는 `robots.txt`가 막는지 확인한다.
2. `data/channels.yaml`에 채널을 추가한다. `type: notice`, `classification: required`, `required: none`, `category: extracurricular`, `collection_enabled: true`, `evidence`(저장한 목록 페이지).
   - `required: none`이라 학과 필수 게시판에는 붙지 않고 비교과 칸에만 나온다.
3. 수집 틀 연결
   - 학교 홈페이지 공통 CMS(`home.knu.ac.kr/HOME/.../sub.htm?nav_code=...`)는 `template: knu-cms`를 쓴다. 채널 ID는 `notice-` + 주소 SHA-256 앞 12자리다. `collector/verify_knu_cms.py`와 같은 절차(목록·최근 상세 1건 확인)로 `data/knu-cms-validation.json`에 `verified` 기록을 남겨야 수집 대상이 된다.
   - 과거 글이 많은 게시판은 `first_collection: recent`를 적는다. 첫 정기 수집이 전체 목록 대신 최근 30일 구간만 읽는다(국제처 약 3,200건 → 첫 수집 44회 요청).
   - 그누보드 사이트는 `gnuboard` 틀과 아래 `OTHER_SOURCES` 등록을 거친다.
   - 그 밖의 사이트는 `collector/other_notices.py`에 목록·상세 읽기 함수를 만들고, `collector/run.py`의 `OTHER_SOURCES`(채널 ID → 틀·주소·게시판 ID)와 `collect()`의 분기에 연결한다. AI부트캠프(`parse_aiboot_*`)가 예시다.
4. `docs/channel-review-data.json`과 `docs/channel-review.html`의 채널 목록을 `channels.yaml`과 같게 맞추고 `python docs/check_channels.py`로 확인한다.
5. 저장한 페이지로 시험을 만든다(`collector/tests/test_aibootcamp.py` 참고). 다음 정기 수집부터 글이 모인다. 첫 수집은 기존 글을 처음 불러오는 것이라 '새 글'로 알리지 않는다.

## 현재 사이트

| 채널 | 사이트 | 틀 | 비고 |
|---|---|---|---|
| `notice-aibootcamp` | [AI부트캠프사업단 알림](https://aibootcamp.knu.ac.kr/notices/) | `aibootcamp` | 정적 사이트. 목록 한 페이지(오래된 글은 `/notices/archive`라 따라가지 않음). 상세의 '마감일'을 마감으로 쓴다 |
| `notice-423ad5624dbc` | [국제처 공지사항(국제화 프로그램)](https://home.knu.ac.kr/HOME/global/sub.htm?nav_code=glo1729572883) | `knu-cms` | 교환학생·해외 연수·세미나. 과거 글 약 3,200건이라 `first_collection: recent`. 외국인 유학생용 Notice 게시판은 넣지 않음 |
| `notice-5a80fc96a24d` | [자원봉사센터 공지사항](https://home.knu.ac.kr/HOME/volunteer/sub.htm?nav_code=vol1623744108) | `knu-cms` | 봉사활동·멘토링·튜터링. `first_collection: recent`. 국내·해외 봉사자 모집 게시판은 따로 있음(아직 넣지 않음) |
