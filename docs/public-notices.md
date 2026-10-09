# 학교·전자공학부에서 가져온 공지

2026-10-01 확인. 학교 학사공지 41개와 전자공학부 공지 150개를 DB에 저장했다. 오류는 0개다. 전체 DB는 4,570개다.

최신 공지와 상단 고정 공지부터 확인했다. 오래된 일반 글만 있는 페이지가 2번 연속 나오면 멈췄다. 확인한 구간의 오래된 글도 같이 저장했으며, 과거 글 전체를 가져온 것은 아니다. 처음 가져온 글이라 전부 오늘 새로 올라온 공지로 분류하지 않는다.

| 가져온 곳 | 목록 페이지 | 저장한 공지 | 실패 | 요청 횟수 | 걸린 시간(초) |
|---|---:|---:|---:|---:|---:|
| 학교 학사공지 | 4 | 41 | 0 | 45 | 48.546 |
| 전자공학부 공지 | 5 | 150 | 0 | 155 | 165.07 |

본문을 글자로 읽은 공지는 168개, 이미지로만 된 공지는 23개다. 이미지 내용과 첨부 파일 내용은 아직 읽지 않았다. 원문에서 마감일을 자동으로 뽑는 기능도 아직 없어 deadline은 null이다.

## 다음에 가져오는 방법

```bash
# 학교·전자공학부·국문·영문·수학을 같이 확인
python -m collector.run

# 학교·전자공학부만 확인
python -m collector.run --channel-id knu-academic --channel-id notice-df44dd8507c1

# 인터넷 없이 테스트
python -m pytest -q
```

매일 자동 실행은 아직 연결하지 않았다. 명령을 실행하면 학교 홈페이지를 다시 읽고, 저장한 글과 비교해 새로운 글과 수정된 글을 찾는다. 같은 글이 여러 페이지에 나와도 한 번만 저장한다.

처음 가져오는 게시판에는 --mode start로 최근 구간을 확인하고 운영 시작 시각만 남길 수 있다. 이번 두 게시판은 시작을 마쳤으므로 다음에는 기본 daily로 실행한다. 과거 전체 글 확인이 필요할 때는 수동 `--mode full`을 실행한다. 학교 별도 일반 공지 메뉴와 전자공학부 취업·세미나 게시판은 이번에 포함하지 않았다.

테스트 82개 통과. 공지 ID, 날짜, 다음 페이지, 중복 제거, 일부 글 실패 시 나머지 저장, 이미지 글 구분을 저장된 HTML로 확인했다. 실행 기록은 data/runs/public-notices-start-20261001.json이다.

## 학교 학사공지 목록

제목을 누르면 학교 원문이 열린다.

| 게시일 | 제목 | 본문 |
|---|---|---|
| 2026-09-30 | [2026학년도 2학기 교직 적성 및 인성검사(1차) 결과 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790744244900) | 글자 |
| 2026-09-29 | [2026학년도 2학기 강의개선을 위한 중간 설문 실시 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790644315187) | 이미지 |
| 2026-09-22 | [2026학년도 겨울계절수업 희망과목 수요조사 실시 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790037102438) | 글자 |
| 2026-09-22 | [2026년도 제4차 평생교육사 자격증 신규 발급 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790036688409) | 글자 |
| 2026-09-22 | [2026학년도 겨울계절수업 및 디딤돌수업 실시 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790036258344) | 글자 |
| 2026-09-21 | [\[상주캠퍼스\] 예비군훈련(기본훈련, 동원훈련 Ⅱ형) 2차 일정 공지](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11789974286924) | 글자 |
| 2026-09-17 | [2026학년도 2학기 응급처치 및 심폐소생술 실습 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11789626757245) | 글자 |
| 2026-09-14 | [2026학년도 2학기 수강변경 후 폐강과목 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11789375936295) | 글자 |
| 2026-09-08 | [2026학년도 2학기 수강정정 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11788857835013) | 이미지 |
| 2026-09-04 | [2026학년도 2학기 교직 적성 및 인성검사(1차) 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11788485307325) | 글자 |
| 2026-09-04 | [예비군 대원신고 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11788480849417) | 글자 |
| 2026-09-03 | [\[대구캠퍼스\] 2026년 예비군 기본 2차훈련 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11788418937924) | 글자 |
| 2026-09-02 | [군 입대 휴학자에 대한 취득학점 인정 및 학점인정 신청서 제출 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11788338616576) | 글자 |
| 2026-09-01 | [2026학년도 2학기 전문 및 특수대학원 재학생 무논문 석사학위 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11788223764457) | 글자 |
| 2026-08-31 | [2026학년도 2학기 수강신청 후 폐강과목 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11788165320350) | 글자 |
| 2026-08-27 | [2026학년도 2학기 융합전공 이수 대상자 추가 선발 결과 공고](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11787814281098) | 글자 |
| 2026-08-20 | [2026학년도 2학기 수강변경 안내(수정)](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11787189649404) | 글자 |
| 2026-08-18 | [\[2026.2학기 조기취업 졸업예정자 출석인정\] 신청 안내(9월 1일(화)부터 통합정보시스템 신청 가능)](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11787012990172) | 글자 |
| 2026-08-14 | [학칙 개정에 따른 수강신청 제도 일부 변경사항 사전 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11786698005467) | 글자 |
| 2026-08-13 | [2026학년도 2학기 국가근로장학생 모집 안내(미술관)](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11786589938825) | 글자 |
| 2026-08-10 | [2026학년도 2학기 학사학위취득의 유예 신청자 등록금 납부 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11786348686961) | 글자 |
| 2026-08-10 | [2026년 8월 학위수여식(학·석·박사 통합) 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11786327219594) | 이미지 |
| 2026-08-07 | [2026학년도 2학기 융합전공 이수대상자 추가 선발 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11786082015217) | 글자 |
| 2026-08-06 | [2026학년도 2학기 수강꾸러미 신청 결과 공고](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11786003834262) | 글자 |
| 2026-08-03 | [\[앵커(舊라이즈)\] 2026학년도 2학기 대구라이즈공유대학 원격수업 학점교류(DRU) 강좌 수강신청 변경 안내_폐강과목 공지](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11785737876426) | 글자 |
| 2026-07-31 | [2026학년도 2학기 수강신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11785487873393) | 이미지 |
| 2026-07-29 | [\[상주캠퍼스\] 학생예비군 기본훈련 1차 일정(8월 27일 훈련) 공지](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11785288347194) | 글자 |
| 2026-07-27 | [2026학년도 2학기 (일반, 전문, 특수)대학원 재입학 신청 안내(여석 포함)](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11785111492485) | 글자 |
| 2026-07-23 | [2026년 8월 학부 및 대학원 졸업(수료)예정자 대출중지 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11784765006434) | 글자 |
| 2026-07-21 | [2026학년도 2학기 수강가능학점 조회 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11784591830956) | 글자 |
| 2026-07-15 | [\[앵커(舊라이즈)\] 2026학년도 2학기 대구라이즈공유대학 원격수업 학점교류(DRU) 강좌 수강신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11784102756142) | 이미지 |
| 2026-07-15 | [2026학년도 2학기 거점국립대학 원격수업 학점교류(KNU10) 강좌 수강신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11784097259440) | 이미지 |
| 2026-07-15 | [2026학년도 2학기 3학년 이상 개설 전공과목 중 일부 과목 성적 평가방법 지정 현황 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11784089154028) | 글자 |
| 2026-07-15 | [2026학년도 2학기 (일반, 전문, 특수)대학원 재입학 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11784078211599) | 글자 |
| 2026-07-15 | [2026학년도 2학기 수업시간표 공지(2차)](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11784076323640) | 글자 |
| 2026-07-13 | [2026학년도 2학기 대학 재입학 선발결과 공고](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11783904606215) | 글자 |
| 2026-07-10 | [\[창업대체학점\] 2026학년도 2학기 창업대체학점 인정제 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11783662257846) | 글자 |
| 2026-07-10 | [\[창업휴학\] 2026학년도 2학기 창업휴학 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11783662104186) | 글자 |
| 2026-07-08 | [2026학년도 2학기 수강꾸러미 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11783486119841) | 글자 |
| 2026-07-08 | [2026년 8월(2025학년도 후기) 졸업예정자에 대한 교원자격무시험검정 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=row&bltn_no=11783471582249) | 글자 |
| 2026-06-24 | [2026학년도 2학기 복학 및 휴학 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11782262478503) | 글자 |

## 전자공학부 공지 목록

제목을 누르면 학교 원문이 열린다.

| 게시일 | 제목 | 본문 |
|---|---|---|
| 2026-10-01 | [KNU-K 10월 창업특강(K.I.T.I)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105663&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-30 | [(지역전략산업혁신연구소) 2026년 2학기 캡스톤디자인 프로그램 신청 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105661&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-30 | [\[교수학습센터\]2026학년도 MY CTL 리워드 프로그램 모집 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105658&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 이미지 |
| 2026-09-30 | [2026년도 SW연계 부전공 이수자 설문 조사](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105657&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-30 | [\[2026 스페이스 해커톤\] 대회 개최 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105656&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-30 | [수요기반 교양교과목 개발 관련 「내가 듣고 싶은 교양수업 공모전」안내(본교 기초교육센터 주관)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105654&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-30 | [2026학년도 학습컨설팅 운영 재안내(본교 교수학습센터 주관)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105653&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 이미지 |
| 2026-09-29 | [\[대학원\] 인공지능학과 오픈랩 안내 (10. 7.(수)~ 10.21.(수) )](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105650&gtid=notice&opt=&sword=&page=1) | 글자 |
| 2026-09-29 | [2026.2학기 강의개선을 위한 중간설문 시행 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105647&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-29 | [\[행사\] 제28회 경북대 가족 한마음 등반대회 행사 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105645&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-28 | [\[이경운 교수\] 운영체제 연구실 26학년도 학부연구생 추가 모집 (대학원 진학 예정자)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105643&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-28 | [2026학년도 학생의료공제회 독감 예방접종비 지원 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105642&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 이미지 |
| 2026-09-23 | [\[박세훈 교수\] 2026년도 2학기 학부연구생(대학원 진학 예정자) 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105640&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-22 | [2026학년도 겨울계절수업 개설희망과목 수요조사안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105639&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-22 | [(전력거래소 주관)2026년 하반기「전국 에너지 공동학점과정」참여 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105636&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-21 | [수업 중 저작권 침해 예방을 위한⌈대학생이 반드시 지켜야 할 저작권 상식⌋ 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105635&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-18 | [\[4단계 BK21\]BK런치세미나 '인공지능 특화연구그룹’ (9/30(수) 12:00, 선착순 280명)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105634&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-18 | [2026년 제55기(동계) WFK PAS 청년봉사단 단원 모집 안내(본교 자원봉사센터)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105633&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-18 | [2026학년도 2학기 첨성인 아너스 클럽 운영 계획 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105632&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-18 | [\[반도체특성화대학사업단\] 2026학년도 2학기 안전 교육 (2차) 시행 안내 (수정)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105631&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-18 | [2026학년도 2학기 응급처치 및 심폐소생술 실습 시행 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105630&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-17 | [\[반도체특성화대학사업단\]2026학년도 2학기 반도체특성화 트랙Ⅰ·Ⅱ(4기-3차) 참여학생 모집 안내(신청기간 변경)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105625&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-16 | [\[분실물\] 에어팟 보관중입니다.](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105624&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-16 | [\[AI부트캠프사업단\] 장학금·해외연수·인턴십 혜택 지원 프로그램 참여학생 및 경진대회 참가팀 모집 안내(~9/21 마감)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105623&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-16 | [2026 SEDEX 반도체대전 및 반도체 우수인재 채용박람회 지원 재게시(접수 : ~9/20)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105622&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-16 | [2026학년도 2학기 학생의료공제회비 2차 추가 납부 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105621&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 이미지 |
| 2026-09-16 | [(기한연장)★\[생활비500만원\]2026학년도 SL이충곤재단 장학생 추천: 9.21.(월) 10:00까지★](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105615&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-15 | [2026학년도 동계 해외봉사활동 파견 학생 모집 안내(본교 자원봉사센터 주관)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105612&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-14 | [\[강재모 교수\] 딥러닝 학습이론 및 응용 연구실(DeLTA LAB) 연구실원 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105611&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-14 | [\[AI부트캠프사업단\] 프로그램 참여학생 및 AI 경진대회 참가팀 모집 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105608&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 글자 |
| 2026-09-14 | [\[반도체특성화대학사업단\]2026학년도 2학기 반도체특성화 트랙Ⅰ·Ⅱ(4기-3차) 참여학생 모집 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105607&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-14 | [\[장재원 교수\] 대학원생 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105602&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-11 | [\[인공지능혁신융합대학사업단\] 2026학년도 2학기 캡스톤디자인 지원팀 선정 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105601&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-11 | [\[인공지능혁신융합대학사업단\] (중요 설문조사) 피지컬 AI 마이크로디그리 개발을 위한 학생 수요조사](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105600&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-10 | [\[인공지능혁신융합대학사업단\] 「AICOSS Career Compass 2026」 진로실태 설문조사 참여 안내(~9/30, 기간연장 및 참여대상 수정)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105599&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-10 | [\[우지용 교수\] 2027년 대학원 석사과정 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105598&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-09 | [2026. 2학기『다문화가정 장학금』선발 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105597&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-09 | [2026 SEDEX 반도체대전 참가 지원(접수: ~9/17)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105596&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-09 | [2026 IT대학 인권·젠더 대면교육 실시에 따른 공결신청 방법 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105595&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-09 | [(대구앵커사업) 2026학년도 2학기 「캡스톤디자인 운영」에 따른 신청 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105593&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-09 | [교원자격증 취득 요건(교직 적·인성 검사, 응급처치 실습, 성인지 교육) 이수 현황 확인 방법 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105592&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-09 | [2026학년도 2학기 학업 성장 챌린지 참여 학생 모집 안내\[본교 교수학습센터\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105591&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 이미지 |
| 2026-09-08 | [\[우성윤 교수\] 27년 1학기 대학원(한국전기연구원 학연과정) 석사 진학 예정자 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105588&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-08 | [\[인공지능혁신융합대학사업단\] AICOSS-UNLV 글로벌 프로그램 공고 (서류접수 ~9/15 17:00까지)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105587&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-08 | [2026.2학기 수강정정 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105586&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-08 | [제3회 AI-Cloud Big Tech 2026 개최 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105581&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 이미지 |
| 2026-09-08 | [대학원 전공 Open Fair 행사 안내 ( 9. 10.(목) 11시 30분 ~ 16시 30분 )](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105579&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 이미지 |
| 2026-09-08 | [「경북대학교 반도체특성화대학사업단」2026학년도 2학기(4기 3차) 반도체특성화트랙 설명회(전자공학부) 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105577&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-07 | [2026학년도 1학기 교원양성과정 성인지 교육 이수 현황 확인 방법 안내(교직이수자 대상)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105575&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-07 | [\[현대자동차그룹\] 2026 매치업 직무능력인증평가 (~9/21)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105573&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-07 | [(수정)\[기업탐방프로그램\] 2026 하반기 SL DAY(10.1/목) 신청 안내(공결 인정!!)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105567&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-07 | [★\[생활비500만원\]2026학년도 SL이충곤재단 장학생 추천: 9.16.(수) 10:00까지★](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105566&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-07 | [\[대회\] Physical AI Challenge 「PAC 2026」 참가팀 모집 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105565&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-04 | [2026년 51기 월드프렌즈코리아 청년봉사단 단원 선발 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105564&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-04 | [\[강인만 교수\] 2026학년도 2학기 학부연구생 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105563&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-04 | [\[AI부트캠프사업단\] 공통교과목 일부 변경 및 동계 현장실습 예정 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105561&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-03 | [\[반도체특성화대학사업단\] 2026학년도 2학기 안전 교육 (2차) 시행 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105558&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-03 | [\[반도체특성화대학사업단\]\[팹리스 점프업 일경험 프로그램 4기 참여자 모집\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105557&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-03 | [\[만족도조사\] 2026학년도 학생만족도조사 실시 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105555&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-03 | [2026학년도 2학기 교직 적성 및 인성검사(1차) 시행 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105554&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 글자 |
| 2026-09-03 | [연계과정 선발 학생의 졸업신청서(대학원 입학지원서) 제출 안내 \[~ 9.8.(화)까지\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105553&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-09-02 | [\[인공지능혁신융합대학사업단\] 2026학년도 2학기 캡스톤디자인 일정 변경 재안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105551&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-09-01 | [중요!!! 2027년 2월 졸업예정자 졸업진단표 제출 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105548&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-09-01 | [2026학년도 2학기 창의적 종합설계 프로그램(캡스톤디자인) 참가팀 모집 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105547&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-09-01 | [\[대학원\] yo 연구실 어때? _ 오픈랩 _참여연구실 공지](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105544&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-09-01 | [\[벨부볼루\] 신호및시스템 수강 관련](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105543&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-31 | [2026학년도 2학기 학생의료공제회비 추가 납부 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105541&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 이미지 |
| 2026-08-31 | [2026 KNU-UP 학생 창업아이템시작품제작 경진대회](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105532&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 이미지 |
| 2026-08-31 | [2026학년도 2학기 지도교수 배정 및 변경 알림](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105530&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-31 | [대학원 전자전기공학부 설명회 / 학·석 연계과정 안내 \[9. 8.(화) 12시 IT1-313호\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105529&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-31 | [\[대학원\] 2027학년도 일반대학원 1학기1차 모집요강 공고](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105528&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-31 | [2026학년도「제 5회 KNU 자기설계 융합전공 공모전」개최 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105527&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-28 | [2026학년도 2학기 학생 대상 재난안전 현장 체험교육 신청 홍보(일반학생 선착순)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105525&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-28 | [2026학년도 KNU-대구앵커 워라밸 취업박람회: 9.7(월)-9.11(금) GP경하홀](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105524&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-28 | [2026학년도 2학기 학습스터디 참여 팀 모집 안내(본교 교수학습센터)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105522&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 이미지 |
| 2026-08-28 | [2026학년도 2학기 2차 Learning Tube(학습법 특강) 운영 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105521&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 이미지 |
| 2026-08-27 | [2026학년도「첨성인 학생역량 진단검사」운영 안내(본교 교수학습센터)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105519&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 이미지 |
| 2026-08-27 | [2026학년도 2학기 지능신호처리 융합전공 선발 결과](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105518&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-27 | [2026학년도 2학기 튜터링 운영 계획 안내(본교 자원봉사센터)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105517&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-27 | [\[인공지능혁신융합대학사업단\] Microsoft AI-901 국제인증자격증 교육과정 안내(마감)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105516&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-26 | [\[인공지능혁신융합대학사업단\] AICOSS 공동운영마이크로디그리 신청안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105515&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-26 | [\[박대진 교수\] 소프트웨어-온-칩 연구실 2026년2학기 연구실 인턴 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105509&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-25 | [\[인공지능혁신융합대학사업단\] 2026년 인공지능혁신융합대학 Microsoft X SKKU Agenthon 교육 경진대회(수정 ~9/2)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105508&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-25 | [\[공모전\] 급수탑 주변 공원 명칭 공모전 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105505&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-25 | [\[반도체특성화대학사업단\] 2026학년도 2학기 안전 교육 시행 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105503&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-24 | [2026 IT대학 인권·젠더 대면교육 실시 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105502&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-21 | [2026년도 장학금 부정수급 자진신고 안내(∼10.9)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105500&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-20 | [2026학년도 2학기 첨성인 학습PT 모집 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105499&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 이미지 |
| 2026-08-20 | [\[인공지능혁신융합대학사업단\] 2026 2학기 캡스톤디자인 교과목 지원 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105498&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-20 | [제6회 반도체특성화 비교과 단기강좌 신청 결과 안내(선착순70명）](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105495&gtid=notice&opt=&sword=&page=3&f_opt_1=) | 글자 |
| 2026-08-20 | [2026년 9월~11월 국립대학육성사업 지역 AI·SW 혁신 인재 양성 프로그램 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105494&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-20 | [2026.2학기 수강변경 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105493&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-19 | [\[반도체특성화대학사업단\]에뮬레이터(Palladium Z3SS) 기반 V&V 실습 교육 참여학생 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105492&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-19 | [2026. 2학기 보훈(가족)장학 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105491&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-18 | [학칙 개정에 따른 수강신청 제도 일부 변경사항 사전 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105485&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-14 | [2026학년도 2학기 조기취업자 출석인정 신청 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105484&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-13 | [2026학년도 2학기 수강신청 초안지 제출관련 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105482&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-13 | [수강변경 기간중 일괄증원 안내(집적회로공정)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105481&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-13 | [2026학년도 2학기 학습관리시스템(LMS) 운영 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105480&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 이미지 |
| 2026-08-11 | [\[근로\]2026.2학기 국가근로장학생(전공실험실,학부사무실 근무) 신청 \[∼8.18/화 13시\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105479&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-11 | [2026.2학기 국가장학금/국가근로장학금/주거안정장학금 2차 신청(∼9.9)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105478&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 이미지 |
| 2026-08-11 | [\[반도체특성화대학사업단\] 향후 PBL 교과목 운영에 관한 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105477&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-11 | [\[반도체특성화대학사업단\] PBL 교과목 전공 학점 관련 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105476&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-07 | [긴급!!! '지능신호처리 융합전공' 참여학생 모집(기간연장 및 장학금 지급 조건 완화)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105474&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-07 | [\[반도체특성화대학사업단\] 2026학년도 2학기 반도체특성화 트랙 Ⅰ·Ⅱ (4기 2차) 선발 결과 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105473&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-07 | [2026학년도 우수 학부생 해외연수 대상자 추천(본교 학생과 주관) 결과 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105472&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-07 | [\[근로\]2026.2학기 교내근로장학생(학부사무실 근무) 신청 \[∼8.12/수 18시\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105471&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-07 | [\[AI부트캠프사업단\] 2026학년도 AI부트캠프 교육 프로그램 및 이수 혜택 안내(수정 26.08.11)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105470&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-05 | [(접수연장)\[생활비150만원\]2026 효석장학회 장학생 추천\[∼8.6/목 14:00\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105467&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-05 | [(우성윤 교수) 2027년도 상반기 대학원 석사/박사 진학예정자 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105466&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-05 | [인재원(2026.9.1.~ 10.31.) 학생동 단체이용 신청 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105465&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-05 | [2026. 08. 21.(금) 졸업장 배부 및 학위복 대여 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105464&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-04 | [2026.2학기 학부연구생프로그램(URP) 장학생 추천\[∼8.6/목 15시\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105463&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-04 | [(벨루볼루) 신호시스템 과목-군이러닝 수강생 필독](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105462&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-04 | [2026학년도 우수 학부생 해외연수 대상자 추천(본교 학생과 주관)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105461&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-04 | [2026년 8월 학사학위취득 유예신청자 대상 향후 일정 및 등록금 납부 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105460&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-03 | [\[학업지원비100만원\]2026 농제장학회 장학생 추천\[∼8.5/수 15:00\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105459&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-03 | [\[생활비150만원\]2026 효석장학회 장학생 추천\[∼8.5/수 15:00\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105458&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-03 | [2026년 8월 국립대학육성사업 지역 지역 AI·SW 혁신 인재 양성 프로그램 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105457&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-03 | [2026학년도 8월 전자공학부(모바일전공,반도체특성화전공 포함) 졸업예정자 명단](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105456&gtid=notice&opt=&sword=&page=4&f_opt_1=) | 글자 |
| 2026-08-03 | [2026학년도 2학기 수강신청 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105454&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-08-03 | [\[반도체특성화대학사업단\] 제6회 참여학생 역량 강화를 위한 비교과 단기강좌 개최 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105452&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-08-03 | [\[항공드론 혁신융합대학사업단\] 2026 항공드론 로컬이노베이션 창업캠프 참가 모집(~8/18)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105450&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-30 | [\[반도체특성화대학사업단\] 반도체 특성화 트랙 변경 신청 안내(08.07. ~ 08.10.)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105447&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-29 | [(수정)\[반도체특성화대학사업단\] 2026학년도 2학기 반도체특성화 트랙 Ⅰ·Ⅱ (4기 2차) 서류합격자(면접 대상자) 및 고사장 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105446&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-29 | [\[NHN\] NHN GAME X AI 해커톤 모집 홍보 (~8/10)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105445&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-29 | [대한전자공학회 제9회 IT 창의챌린지 개최](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105444&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-28 | [2026학년도 2학기 전자공학부 버디 선발 결과 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105443&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-28 | [\[4단계 BK21\] 제1회 KNU NEXT RF 융합 기술 워크숍](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105441&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-28 | [\[재업\](본교 대학원진학예정자)2026.1학기 G-Link장학금 신청\[∼8.11(화) 14:00\]](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105439&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-24 | [2026학년도 학부 신입생의 수강가능학점 적용시기 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105434&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-24 | [\[인공지능혁신융합대학사업단\] 2026-2학기 성균관대학교 학점교류 신청(~7/31 13시까지)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105430&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-22 | [\[인공지능혁신융합대학사업단\] (!!기프티콘 증정!!) 2026-1학기 교과목 학습자 만족도 조사 안내(기한연장)(~7/28)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105429&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-21 | [Adobe Creative Cloud Pro Plus 공동구매 특가 안내 (학생대상, 24만원/년)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105428&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 이미지 |
| 2026-07-21 | [(추가 주제 선발) \[PBL 프로젝트(대구RISE사업)\] 2026년 2학기 장병철 교수 과제 제안 및 팀 선발 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105427&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-21 | [2026학년도 2학기 재학생 등록금 수납 계획 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105426&gtid=notice&opt=&sword=&page=1) | 글자 |
| 2026-07-20 | [\[반도체특성화대학사업단\]2026학년도 2학기 반도체특성화 트랙Ⅰ·Ⅱ(4기-2차) 참여학생 모집 안내 (편입생 지원자격 한시적 확대)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105420&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-17 | [\[최정식 교수\] 학부연구생 모집 (본교 대학원 진학 예정자) 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105417&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-16 | [\[강인만 교수\] 여름계절 물리전자 성적확인 및 이의신청 관련 공지](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105416&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-16 | [\[인공지능혁신융합대학사업단\] 2026 CO-SHOW 연계 AIM 챌린지 추가 모집 안내 (선착순, ~7/19까지)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105415&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-16 | [\[송대건 교수\] 2027 1학기 석사/박사 및 2026 2학기 학부연구생 모집 관련](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105414&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-16 | [\[반도체특성화대학사업단\] 제7회 반도체특성화 취업역량 강화교육 개최 <직무적성검사>](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105413&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-15 | [★★ \[국제\] 2026학년도 2학기 전자공학부 버디 신청 안내 (~7/22 23시) ★★](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105411&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-15 | [\[대회안내\] ACPC 2026 (AWS × Codetree) 전국 대학생/대학원생 프로그래밍 경진대회 개최 안내 (마감 임박)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105410&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-15 | [\[산학-대학원 과정\] (주)퀴브에서 DGIST-경북대 석.박사 산학과정 모집합니다.](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105409&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-15 | [\[반도체특성화대학사업단\] 2026 STOB리그(반도체 경진대회) 문제 공개](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105408&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-15 | [\[국제\] 2026년 하반기 한미대학생연수(WEST) 참가자 모집 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105407&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-15 | [제577회 정기 TOEIC 시험 교내 시행 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105406&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
| 2026-07-14 | [\[한국수력원자력\] 2030세대 에너지리더캠프(선착순 30명) 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105403&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 이미지 |
| 2026-07-14 | [\[인공지능혁신융합대학사업단\] AIB컨소시엄 2026 하계 비교과 프로그램(2차) 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105402&gtid=notice&opt=&sword=&page=5&f_opt_1=) | 글자 |
