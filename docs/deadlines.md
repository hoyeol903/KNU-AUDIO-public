# 공지 마감일 찾기

2026-10-01. 수집기에 마감일 추출을 붙였고, 이미 저장된 공지에도 적용했다. 새 의존성·LLM·외부 요청 없이 원문 제목과 읽은 본문으로 판단한다.

| 확인 결과 | 공지 수 |
|---|---:|
| 확실한 마감일을 찾아 저장 | **458** |
| 날짜·대상·조건이 애매해 검토 필요 | 2,005 |
| 읽은 텍스트에서 마감 표현을 찾지 못함 | 2,416 |
| 확인한 전체 공지 | **4,879** |

저장한 마감 중 2026-10-01 이후는 **15개**이며, 나머지는 과거 마감이다. 같은 학교 안내가 여러 게시판에 올라오면 각 공지 건으로 센다. 마감을 찾지 못했다는 것은 마감이 없다는 뜻이 아니다. 이미지·첨부 전용 본문은 아직 읽지 못한다.

최종 검토에서 상대적인 기한 표현이 섞인 7개를 추가 보류했다. 최초 465개 판정과 보류 내역은 `data/runs/deadlines-initial-20261001.json` 및 최종 보고서의 corrections에 남겼다. 최종 저장은 458개다.

## 어떻게 고르나

- 신청·접수·제출·등록·납부·모집 등의 기한/마감 표현과 **연·월·일이 모두 적힌 날짜**가 있어야 한다.
- 한 기간에 시작·종료 날짜가 모두 연도까지 적혔으면 종료일을 쓴다. 날짜가 하나인 신청기간은 `까지` 등 종료 근거가 있어야 한다.
- 연도가 빠진 `10월 7일까지`, `2026.9.30~10.7`은 연도를 채우지 않고 검토 대상으로 남긴다. 제목의 학년도나 게시일에서 연도를 빌리지 않는다.
- 서로 다른 마감·여러 회차·잘못된 날짜·선착순/조기 종료는 검토 대상으로 남긴다. 하나의 날짜 필드로 대상별 마감일을 합치지 않는다.
- 마감 시각까지 저장하는 기능은 없다. 날짜만 저장하므로 이 결과만으로 '오늘 아직 신청 가능'을 판단하지 않는다.
- 근거 문장과 판정 이유는 실행 보고서에 남긴다. DB의 마감 필드 외 원문·채널·최초 발견·마지막 사이트 확인 시각은 그대로 유지했다. 다시 실행하면 추가 변경은 0개다.

## 실행

프로젝트 루트에서, 현재 로컬 환경은 python 대신 `/opt/anaconda3/bin/python3`를 쓴다.

```bash
# 저장된 공지에서 미리 확인 (DB 변경 없음)
python -m collector.deadlines
# 비어 있는 마감일에만 저장
python -m collector.deadlines --apply
# 앞으로 수집하는 상세 공지에는 자동 적용
python -m collector.run
# 인터넷 없는 테스트
python -m pytest -q
```

`--db-path`로 다른 DB, `--report-path`로 보고서 경로를 지정할 수 있다. DB는 store로 원자적으로 갱신한다. 기존 마감일은 일괄 재분석에서 덮어쓰지 않는다. 실제 수집 때 원문이 바뀌면 새 판정을 적용하고 기존 마감을 확인하지 못한 경우 검토 목록에 남긴다.

테스트 **129개 통과**. 전체 4,879개 DB를 읽어 검증했고, 마감일·해시를 제외한 모든 필드 보존과 재실행 시 변경 0개를 확인했다. 원문 근거·전체 검토 목록은 `data/runs/deadlines-20261001.json`에 있다.

## 오늘 이후의 마감

저장 자료에는 대학원 공지도 포함돼 있다. 사용자에게 전달할 공지 목록은 신규·마감 알림 조건으로 정한다.

| 마감 날짜 | 공지 | 원문 근거 |
|---|---|---|
| 2026-10-06 | [2026학년도 2학기 교직 적성 및 인성검사(1차) 결과 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790744244900) | - 교육 후 이수증 제출: 2026. 10. 6.(화)까지, 학과 사무실로 제출 ※ 기한 내 미 제출 시 차기 검사 참여 불가 |
| 2026-10-07 | [(지역전략산업혁신연구소) 2026년 2학기 캡스톤디자인 프로그램 신청 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105661&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 다. 제출기한: 2026. 10. 7.(수) 17:00까지(기한 엄수) |
| 2026-10-08 | [지역전략산업혁신연구소 2026년 2학기 캡스톤디자인 프로그램 운영 계획 및 신청 안내](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29456) | 다. 제출기한: 2026. 10. 8.(목) 12:00까지(기한 엄수) |
| 2026-10-08 | [2026년 제55기(동계) WFK PAS 청년봉사단 단원 모집 안내(본교 자원봉사센터)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105633&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 가. 신청마감: 2026. 10.8.(목)까지 |
| 2026-10-12 | [[안내] 학생상담센터 2026학년도 하반기 대학원생 마음건강증진캠프 참가자 모집 안내](https://home.knu.ac.kr/HOME/bcst2/sub.htm?mode=view&mv_data=aWR4PTgxOSZzdGFydFBhZ2U9MCZsaXN0Tm89NzAyJnRhYmxlPWV4X2Jic19kYXRhX2Jjc3QyJm5hdl9jb2RlPWJjczE2MTEwNjEyOTQmY29kZT1ub3RpY2Umc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPSZzZWNyZXRfbW9kZT0w) | 3. 모집 기간: 2026. 9. 30.(수) ~ 2026. 10. 12.(월) |
| 2026-10-12 | [2026년 제55기(동계) WFK PAS 청년봉사단 단원 모집 안내](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29452) | 가. 신청마감: 2026. 10. 12.(월)까지 |
| 2026-10-12 | [2026년 제55기(동계) WFK PAS 청년봉사단 단원 모집 안내](http://med.knu.ac.kr/pages/sub.htm?mode=view&mv_data=aWR4PTI1OTIzJnN0YXJ0UGFnZT0wJmxpc3RObz0yODc1JnRhYmxlPWNzX2Jic19kYXRhJm5hdl9jb2RlPWtudTE2NzA1ODM3NDgmY29kZT1ub3RpY2UwMDEmc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPQ==%7C%7C) | 가. 신청마감: 2026. 10. 12.(월)까지 |
| 2026-10-12 | [(대학원) 학생상담센터 2026학년도 하반기 대학원생 마음건강증진캠프 참가자 모집 안내](http://med.knu.ac.kr/pages/sub.htm?mode=view&mv_data=aWR4PTI1OTMzJnN0YXJ0UGFnZT0wJmxpc3RObz0yODgzJnRhYmxlPWNzX2Jic19kYXRhJm5hdl9jb2RlPWtudTE2NzA1ODM3NDgmY29kZT1ub3RpY2UwMDEmc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPQ==%7C%7C) | 3. 모집 기간: 2026. 9. 30.(수) ~ 2026. 10. 12.(월) |
| 2026-10-16 | [2026년 51기 월드프렌즈코리아 청년봉사단 단원 추천 안내](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29427&page=2) | 가. 신청마감: 2026. 10. 16.(금)까지 |
| 2026-10-16 | [2026년 51기 월드프렌즈코리아 청년봉사단 단원 선발 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105564&gtid=notice&opt=&sword=&page=2&f_opt_1=) | 가. 신청마감: 2026. 10. 16.(금)까지 |
| 2026-11-24 | [2026학년도 2학기 조기취업자 출석인정 신청 안내](https://chinese.knu.ac.kr/bbs/board.php?bo_table=notice&wr_id=13635&page=2) | 마. 제출 기간 - 학 생 → 학 과: 2026. 11. 24.(화)까지 |
| 2026-11-24 | [2026학년도 2학기 조기취업자 출석인정 신청 안내](https://home.knu.ac.kr/HOME/english/sub.htm?mode=view&mv_data=aWR4PTQ0MTcmc3RhcnRQYWdlPTAmbGlzdE5vPTEyMDgmdGFibGU9ZXhfYmJzX2RhdGFfZW5nbGlzaCZuYXZfY29kZT1lbmcxNjIxODUyMTczJmNvZGU9Sm9haTFoRVA4ckl0JnNlYXJjaF9pdGVtPSZzZWFyY2hfb3JkZXI9Jm9yZGVyX2xpc3Q9Jmxpc3Rfc2NhbGU9JnZpZXdfbGV2ZWw9JnZpZXdfY2F0ZT0mdmlld19jYXRlMj0=) | 마. 제출 기간: 학 생 → 학 과: 2026. 11. 24.(화)까지 |
| 2026-11-24 | [2026학년도 2학기 조기취업자 출석인정 신청 안내](https://home.knu.ac.kr/HOME/korean/sub.htm?mode=view&mv_data=aWR4PTEyNzMmc3RhcnRQYWdlPTAmbGlzdE5vPTMwNSZ0YWJsZT1leF9iYnNfZGF0YV9rb3JlYW4mbmF2X2NvZGU9a29yMTY1NzA3MTM1NyZjb2RlPVpFZkhDaUJQbFJCciZzZWFyY2hfaXRlbT0mc2VhcmNoX29yZGVyPSZvcmRlcl9saXN0PSZsaXN0X3NjYWxlPSZ2aWV3X2xldmVsPSZ2aWV3X2NhdGU9JnZpZXdfY2F0ZTI9) | 바. 신청 기간: 2026. 11. 24.(화)까지 [기한 엄수] |
| 2026-11-24 | [[학부] 2026학년도 2학기 조기취업자 출석인정 신청 안내](https://home.knu.ac.kr/HOME/math/sub.htm?mode=view&mv_data=aWR4PTMzNzgmc3RhcnRQYWdlPTQwJmxpc3RObz0yNzYxJnRhYmxlPWV4X2Jic19kYXRhX21hdGgmbmF2X2NvZGU9bWF0MTYyMzAyOTMwOCZjb2RlPXVEejJTU2VSbE5ydCZzZWFyY2hfaXRlbT0mc2VhcmNoX29yZGVyPSZvcmRlcl9saXN0PSZsaXN0X3NjYWxlPSZ2aWV3X2xldmVsPSZ2aWV3X2NhdGU9JnZpZXdfY2F0ZTI9) | 마. 제출 기간: 2026. 11. 24.(화)까지 |
| 2027-01-08 | [[인공지능혁신융합대학사업단] 2026학년도 2학기 캡스톤디자인 지원팀 선정 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105601&gtid=notice&opt=&sword=&page=2&f_opt_1=) | - 제출기한: 2027. 1. 8.(금) |

## 최근 공지 중 확인이 필요한 예시

최근 30일 게시물의 검토 대상은 97개다. 아래는 최신 30개이며 전체 근거는 보고서에 있다. 과거 공지의 검토 대상도 보고서에서 삭제하지 않았다.

| 게시일 | 공지 | 확인할 이유 |
|---|---|---|
| 2026-10-01 | [[안내] KNU-K 10월 창업특강(K.I.T.I) 안내](https://home.knu.ac.kr/HOME/bcst2/sub.htm?mode=view&mv_data=aWR4PTgxMyZzdGFydFBhZ2U9MCZsaXN0Tm89Njk2JnRhYmxlPWV4X2Jic19kYXRhX2Jjc3QyJm5hdl9jb2RlPWJjczE2MTEwNjEyOTQmY29kZT1ub3RpY2Umc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPSZzZWNyZXRfbW9kZT0w) | 조건부·상시 마감 |
| 2026-10-01 | [[안내] 2026년도 하반기 동물 실험 기법에 대한 워크숍 실시 안내](https://home.knu.ac.kr/HOME/bcst2/sub.htm?mode=view&mv_data=aWR4PTgxNSZzdGFydFBhZ2U9MCZsaXN0Tm89Njk4JnRhYmxlPWV4X2Jic19kYXRhX2Jjc3QyJm5hdl9jb2RlPWJjczE2MTEwNjEyOTQmY29kZT1ub3RpY2Umc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPSZzZWNyZXRfbW9kZT0w) | 연도까지 명시된 마감 날짜 없음 |
| 2026-10-01 | [[안내] 2026학년도 MY CTL 리워드 프로그램 모집 안내](https://home.knu.ac.kr/HOME/bcst2/sub.htm?mode=view&mv_data=aWR4PTgxNyZzdGFydFBhZ2U9MCZsaXN0Tm89NzAwJnRhYmxlPWV4X2Jic19kYXRhX2Jjc3QyJm5hdl9jb2RlPWJjczE2MTEwNjEyOTQmY29kZT1ub3RpY2Umc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPSZzZWNyZXRfbW9kZT0w) | 연도 생략 또는 여러 날짜·기간 |
| 2026-10-01 | [[안내] 2026학년도 2학기 생활관생 후보자 4차 추가 모집 안내](https://home.knu.ac.kr/HOME/bcst2/sub.htm?mode=view&mv_data=aWR4PTgxOCZzdGFydFBhZ2U9MCZsaXN0Tm89NzAxJnRhYmxlPWV4X2Jic19kYXRhX2Jjc3QyJm5hdl9jb2RlPWJjczE2MTEwNjEyOTQmY29kZT1ub3RpY2Umc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPSZzZWNyZXRfbW9kZT0w) | 연도 생략 또는 여러 날짜·기간 |
| 2026-10-01 | [KNU-K 10월 창업특강(K.I.T.I)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105663&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 조건부·상시 마감 |
| 2026-09-30 | [2026 개편 KOICA 콜롬비아 보고타 국립직업훈련학교 혁신창업교육 역량강화 프로젝트 봉사단 9기 모집 안내](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29455) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-30 | [2026학년도 2학기 생활관생 후보자 4차 추가 모집 안내](https://dent.knu.ac.kr/sub/board.html?mode=cont&bno=4489&snm=342&gotoPage=1&bid=k1news&sflag=&sword=&syear=&bcate=) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-28 | [★[대학원]2026학년도 2학기 대학원 심사용 학위논문 접수 안내(접수:9.30(수)~10.2(금))](https://dent.knu.ac.kr/sub/board.html?mode=cont&bno=4484&snm=342&gotoPage=&bid=k1news&sflag=&sword=&syear=&bcate=) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-23 | [[박세훈 교수] 2026년도 2학기 학부연구생(대학원 진학 예정자) 모집](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105640&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 조건부·상시 마감 |
| 2026-09-22 | [[학부] (전력거래소 주관)2026년 하반기 「전국 에너지 공동학점과정」 학생 참여 안내](https://home.knu.ac.kr/HOME/math/sub.htm?mode=view&mv_data=aWR4PTM0MjQmc3RhcnRQYWdlPTAmbGlzdE5vPTI4MDQmdGFibGU9ZXhfYmJzX2RhdGFfbWF0aCZuYXZfY29kZT1tYXQxNjIzMDI5MzA4JmNvZGU9dUR6MlNTZVJsTnJ0JnNlYXJjaF9pdGVtPSZzZWFyY2hfb3JkZXI9Jm9yZGVyX2xpc3Q9Jmxpc3Rfc2NhbGU9JnZpZXdfbGV2ZWw9JnZpZXdfY2F0ZT0mdmlld19jYXRlMj0=) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-22 | [(전력거래소 주관)2026년 하반기「전국 에너지 공동학점과정」참여 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105636&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-22 | [2026학년도 겨울계절수업 및 디딤돌수업 실시 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790036258344) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-22 | [2026년도 제4차 평생교육사 자격증 신규 발급 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11790036688409) | 연도 생략 또는 여러 날짜·기간; 연도까지 명시된 마감 날짜 없음 |
| 2026-09-21 | [N.O.V.A. 2026 대화형 의료 진단 AI 에이전트 대회 안내 협조 요청 (분당서울대학교병원 의료인공지능센터)](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29450) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-21 | [2026년 첨성인 독서에세이 공모전](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29451) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-21 | [[학부] 2026학년도 2학기 대구캠퍼스 글쓰기 튜터링 신청 기간 연장 안내](https://home.knu.ac.kr/HOME/math/sub.htm?mode=view&mv_data=aWR4PTM0MjEmc3RhcnRQYWdlPTAmbGlzdE5vPTI4MDEmdGFibGU9ZXhfYmJzX2RhdGFfbWF0aCZuYXZfY29kZT1tYXQxNjIzMDI5MzA4JmNvZGU9dUR6MlNTZVJsTnJ0JnNlYXJjaF9pdGVtPSZzZWFyY2hfb3JkZXI9Jm9yZGVyX2xpc3Q9Jmxpc3Rfc2NhbGU9JnZpZXdfbGV2ZWw9JnZpZXdfY2F0ZT0mdmlld19jYXRlMj0=) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-18 | [2026학년도 2학기 첨성인 아너스 클럽 운영 계획 에 따른 신청 안내 ( 대상 :2027.2월 졸업예정자)](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29446) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-18 | [[학부] 2026학년도 2학기 학생의료공제회비 2차 추가 납부 안내](https://home.knu.ac.kr/HOME/math/sub.htm?mode=view&mv_data=aWR4PTM0MTgmc3RhcnRQYWdlPTAmbGlzdE5vPTI3OTkmdGFibGU9ZXhfYmJzX2RhdGFfbWF0aCZuYXZfY29kZT1tYXQxNjIzMDI5MzA4JmNvZGU9dUR6MlNTZVJsTnJ0JnNlYXJjaF9pdGVtPSZzZWFyY2hfb3JkZXI9Jm9yZGVyX2xpc3Q9Jmxpc3Rfc2NhbGU9JnZpZXdfbGV2ZWw9JnZpZXdfY2F0ZT0mdmlld19jYXRlMj0=) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-18 | [[학부-교직] 2026학년도 2학기 응급처치 및 심폐소생술 실습 시행 안내](https://home.knu.ac.kr/HOME/math/sub.htm?mode=view&mv_data=aWR4PTM0MTkmc3RhcnRQYWdlPTAmbGlzdE5vPTI4MDAmdGFibGU9ZXhfYmJzX2RhdGFfbWF0aCZuYXZfY29kZT1tYXQxNjIzMDI5MzA4JmNvZGU9dUR6MlNTZVJsTnJ0JnNlYXJjaF9pdGVtPSZzZWFyY2hfb3JkZXI9Jm9yZGVyX2xpc3Q9Jmxpc3Rfc2NhbGU9JnZpZXdfbGV2ZWw9JnZpZXdfY2F0ZT0mdmlld19jYXRlMj0=) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-18 | [2026학년도 2학기 응급처치 및 심폐소생술 실습 시행 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105630&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-18 | [2026학년도 2학기 첨성인 아너스 클럽 운영 계획 안내](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105632&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-18 | [[4단계 BK21]BK런치세미나 '인공지능 특화연구그룹’ (9/30(수) 12:00, 선착순 280명)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105634&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 조건부·상시 마감 |
| 2026-09-17 | [2026학년도 2학기 학생의료공제회비 2차 추가 납부 안내](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29443) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-17 | [[교직]2026학년도 2학기 응급처치 및 심폐소생술 실습 시행 안내](https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29444) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-17 | [[자원봉사센터] 2026학년도 동계 해외봉사활동 파견 학생 모집 안내](http://med.knu.ac.kr/pages/sub.htm?mode=view&mv_data=aWR4PTI1OTE0JnN0YXJ0UGFnZT0xMCZsaXN0Tm89Mjg3MyZ0YWJsZT1jc19iYnNfZGF0YSZuYXZfY29kZT1rbnUxNjcwNTgzNzQ4JmNvZGU9bm90aWNlMDAxJnNlYXJjaF9pdGVtPSZzZWFyY2hfb3JkZXI9Jm9yZGVyX2xpc3Q9Jmxpc3Rfc2NhbGU9JnZpZXdfbGV2ZWw9JnZpZXdfY2F0ZT0mdmlld19jYXRlMj0=%7C%7C) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-17 | [(대학원) 2026학년도 2학기 대학원 수료생 (2차) 등록 신청자 수납 안내](http://med.knu.ac.kr/pages/sub.htm?mode=view&mv_data=aWR4PTI1OTE1JnN0YXJ0UGFnZT0wJmxpc3RObz0yODc0JnRhYmxlPWNzX2Jic19kYXRhJm5hdl9jb2RlPWtudTE2NzA1ODM3NDgmY29kZT1ub3RpY2UwMDEmc2VhcmNoX2l0ZW09JnNlYXJjaF9vcmRlcj0mb3JkZXJfbGlzdD0mbGlzdF9zY2FsZT0mdmlld19sZXZlbD0mdmlld19jYXRlPSZ2aWV3X2NhdGUyPQ==%7C%7C) | 연도 생략 또는 여러 날짜·기간; 연도까지 명시된 마감 날짜 없음 |
| 2026-09-17 | [[반도체특성화대학사업단]2026학년도 2학기 반도체특성화 트랙Ⅰ·Ⅱ(4기-3차) 참여학생 모집 안내(신청기간 변경)](https://see.knu.ac.kr/content/board/notice.html?pg=vv&fidx=105625&gtid=notice&opt=&sword=&page=1&f_opt_1=) | 연도까지 명시된 마감 날짜 없음 |
| 2026-09-17 | [2026학년도 2학기 응급처치 및 심폐소생술 실습 신청 안내](https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdViewBtin.action?menu_idx=42&bbs_cde=stu_812&note_div=top&bltn_no=11789626757245) | 연도까지 명시된 마감 날짜 없음; 조건부·상시 마감 |
| 2026-09-16 | [2026학년도 2학기 다문화가정 장학금 장학생 선발 안내](https://chinese.knu.ac.kr/bbs/board.php?bo_table=notice&wr_id=13653) | 연도 생략 또는 여러 날짜·기간 |
| 2026-09-16 | [(대학원) 2026학년도 2학기 G-KNU Scholarship 장학생(2차) 전일제 시스템 등록 안내(~10. 6.)](http://med.knu.ac.kr/pages/sub.htm?mode=view&mv_data=aWR4PTI1OTEzJnN0YXJ0UGFnZT0xMCZsaXN0Tm89Mjg3MiZ0YWJsZT1jc19iYnNfZGF0YSZuYXZfY29kZT1rbnUxNjcwNTgzNzQ4JmNvZGU9bm90aWNlMDAxJnNlYXJjaF9pdGVtPSZzZWFyY2hfb3JkZXI9Jm9yZGVyX2xpc3Q9Jmxpc3Rfc2NhbGU9JnZpZXdfbGV2ZWw9JnZpZXdfY2F0ZT0mdmlld19jYXRlMj0=%7C%7C) | 연도 생략 또는 여러 날짜·기간 |

## 다음 작업

오늘 처음 발견한 공지와 마감 3일 전·1일 전·당일 공지를 채널별로 고르는 작업이 다음이다. 본문에 마감일이 있어도 학과 내부 제출일·첨부 전용 정보는 추가 확인이 필요하다. `items.json` 생성·새벽 자동 실행은 아직 미구현이다.
