# 하루 수집과 새벽 자동 실행

2026-10-06 기준 운영 구성과 과거 실측을 분리해 적었다. 현재 범위는 `.github/workflows/collect.yml`의 실행 인자를 기준으로 확인한다.

## 실제 하루 수집 점검

아래 표는 2026-10-01 당시의 5개 게시판 수동 측정값이며 현재 전체 운영량의 추정치가 아니다. 현재 GitHub Actions의 `full`은 `--all-required --write-items --collect-extras --skip-meals`로 필수 게시판 전체와 날씨·학사일정을 수집한다. 식당 사이트는 요청하지 않으며 여섯 식당은 로컬에서 `python -m collector.daily_sources --meals-only`로 별도 갱신한다. 예약 수집은 cron-job.org의 `KNU-AUDIO 매일 수집` 작업에서 켜고 끈다.

| 출처 | 요청 수 | 걸린 시간 | 상세 성공 |
|---|---:|---:|---:|
| 학교 학사공지 | 21 | 22.566초 | 17 |
| 전자공학부 | 72 | 77.192초 | 67 |
| 국어국문학과 | 19 | 20.661초 | 16 |
| 영어영문학과 | 12 | 13.880초 | 9 |
| 수학과 | 48 | 56.011초 | 42 |
| 날씨·식당 두 곳·일정 | 4 | 전체 시간에 포함 | 공지 상세와 별개 |

- 최초 게시판 시작부터 items 생성까지 **193.281초(약 3분 13초), HTTP 176회**. 설치·테스트 시간 제외. 재시도/리다이렉트도 요청 수에 포함한다.
- 요청/구조 오류 0개, 신규 저장 3개, 기존 본문 수정 0개. DB 총 4,882개.
- 당시 전달 자료: 7채널, 신규 공지 3개, 식단 13개. 학사일정 원본은 1개이며 현재는 전달 자료에 모두 포함한다.
- 이미지 본문 미확인 표시 2개. 요청 성공과 본문 확인 성공은 다르다.

보고서는 data/runs/operations-20261001.json, 종합 측정은 data/runs/operations-summary-20261001.json, 전달 파일은 data/raw/2026-10-01/items.json에 있다. 이 점검의 종합 시간은 실제 시작/생성 시각 차이로 계산했다. 이후 collector.run 보고서는 시작/종료·전체 경과 초·전체 HTTP 요청 수와 extras의 원문 주소/오류/요청 수도 자동 저장한다.

## 자동 실행 설정

cron-job.org의 `KNU-AUDIO 매일 수집` 작업(8595508)이 매일 **01:07 Asia/Seoul**에 GitHub의 `workflow_dispatch`를 호출한다. 수집은 GitHub Actions에서 계속 실행한다. GitHub 자체 `schedule`은 제거했으며, 이전 변수 `ENABLE_COLLECTION`은 더 이상 수집을 제어하지 않는다. 기존 HTTP 규칙을 유지하고 DB를 갱신하는 실행은 동시에 하나만 진행한다. 대기 후 최신 기본 브랜치에서 시작한다.

- 예약 관리: https://console.cron-job.org/jobs/8595508 — `Enable job`을 끄면 자동 수집을 중지한다. Actions의 수동 실행은 유지한다.
- 요청: `POST https://api.github.com/repos/hoyeol903/KNU-AUDIO-public/actions/workflows/collect.yml/dispatches`, JSON 본문 `{"ref":"main","inputs":{"collection_mode":"full","retry_report":""}}`.
- 헤더: `Accept: application/vnd.github+json`, `Content-Type: application/json`, `Authorization: Bearer <토큰>`. 실제 토큰은 예약 서비스에만 저장하며 저장소·로그·문서에 넣지 않는다.
- 토큰은 `KNU-AUDIO-cron`, KNU-AUDIO-public만 선택, Actions Read and write, Metadata Read-only. 현재 만료일은 **2026-11-06**이다. 만료 전에 사용자가 재발급하고 예약 서비스의 Authorization 값을 교체해야 한다. GitHub 토큰 설정: https://github.com/settings/personal-access-tokens
- 아래 연결 테스트는 이전 비공개 저장소 기준이다. 공개 저장소로 옮긴 뒤 예약 서비스의 요청 주소와 토큰의 저장소 선택을 위 값으로 바꿔야 하며, 바꾼 뒤의 연결 확인은 아직 이 문서에 기록되지 않았다.
- 2026-10-07 연결 테스트에서 HTTP 204(1.78초)를 받았고 [실제 수집](https://github.com/hoyeol903/KNU-AUDIO/actions/runs/37573281219)이 13:49 한국시간에 시작됐다. 이는 연결 성공 확인이며 수집 완료나 정시 예약 실행의 보장은 아니다.
- 예약 서비스의 성공은 GitHub가 요청을 접수했다는 뜻이다. 수집 실패는 GitHub 실행 보고서와 기존 이슈 알림에서 확인한다. 401/403이면 토큰 만료·저장소 선택·Actions 쓰기 권한을 확인한다.

1. Python 3.11과 requirements.txt 설치.
2. 인터넷 없는 테스트와 채널 설정 검사.
3. 필수 게시판 전체 + 날씨/학사일정 실제 수집 및 items.json 생성. 식당은 요청하지 않는다.
4. DB·전달 자료·실행 보고서을 Actions 다운로드 파일로 14일 보관.
5. 변경된 결과 파일만 기본 브랜치에 한국어 메시지로 자동 커밋. 성공한 부분 자료도 보존한다.
6. 수집 실행이 실패했으면 자료 저장 후 실행을 실패로 표시한다. 이미지 본문 미확인은 자료 내 확인 표시이며 요청 실패와 구분한다.
7. 실행 보고서의 요청 오류·잘린 수집 범위를 `output/app/data/collection-failures.csv`와 기존 `매일 수집 결과` 이슈 댓글에 정리한다. 70여 건의 본문 미확인 안내는 실패 목록에 넣지 않으며, 이메일 알림은 GitHub 사용자 설정에 따른다.

자동 커밋은 이미 프로젝트 구조에서 정한 운영 결과 저장 예외다. 기능 개발은 feat 브랜치와 PR 규칙을 유지한다. 자동 저장은 data/db·data/raw·data/runs에 한정한다. .env와 기능 코드는 저장하지 않는다. 강제 푸시하지 않으며 다른 DB 변경과 충돌하면 커밋 반영을 중단한다. 백업 자료에서 복구할 수 있다.

외부 예약도 지연·실패할 수 있으며 GitHub 실행 서버 대기가 남아 01:07 정각 시작을 보장하지 않는다. GitHub 자체 예약에서 발생하던 이벤트 지연을 피하기 위한 전환이다. [GitHub 예약 실행 설명](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 주간 학식 알림

`.github/workflows/meal-reminder.yml`은 매주 월요일 09:00 한국시간에 `주간 학식 로컬 수집 알림` 이슈를 만들거나 댓글로 알린다. Actions 탭에서 수동 실행도 가능하다. 여섯 식당 메뉴는 로컬에서만 수집하며 자동 수집·업로드하지 않는다. GitHub 이메일 알림은 [알림 설정](https://github.com/settings/notifications)의 Participating에서 Email을 켜야 받을 수 있다. 예약 실행은 GitHub 상황에 따라 늦어질 수 있다. 주간 표에는 실제 게시된 날짜의 메뉴만 포함되므로 한 주 전체가 미리 채워지지는 않는다.

## GitHub Actions에서 수동 실행

수동 실행은 저장소의 Actions 탭에서 `매일 경북대 자료 수집` 워크플로를 열고 `Run workflow`를 선택한다. 자동 실행은 cron-job.org 예약에서 별도로 활성화한다.

- Actions가 활성화되어 있어야 하며 contents: write 권한과 기본 브랜치의 운영 커밋 허용 여부를 확인한다. 브랜치 보호로 봇 푸시가 거부되면 백업은 남고 자동 반영은 실패한다. [권한 설정](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
- 실행 후 로그, 저장 커밋, 당일 items.json, 다운로드 파일을 확인한다. GitHub Actions의 수동 실행은 공지·날씨·학사일정 사이트에 요청을 보낸다. 식당 사이트는 요청하지 않는다.
- 수집 자체에는 API 키가 필요 없다. Kaggle 음성 생성을 연결하려면 GitHub Secret `KAGGLE_API_TOKEN`이 필요하다. 로컬 키는 `.env`에만 두고 커밋하지 않는다.
- 수집 뒤 음성 생성 연결은 변수 `ENABLE_KAGGLE_BRIEFING=true`일 때만 실행한다. 기본값은 꺼짐이며, 외부 예약의 활성화 여부와 별개다. 이번 수집에서 생성된 `items.json`의 날짜와 저장 커밋을 Kaggle 작업에 전달한다. 일부 수집 실패가 있어도 앱 자료와 입력 저장이 완료되면 연결할 수 있다. 실패 전에 남아 있던 오래된 입력은 보내지 않는다.
- 음성 생성·검증에 성공하면 별도 저장 단계가 원래 수집 자료의 입력 해시를 다시 확인하고 이미 게시된 음성보다 최신이면 음성·대본만 커밋하고 배포를 요청한다. 생성 실패나 자료 변경 시 기존 결과를 보존한다. 자동 커밋 뒤 배포는 `workflow_dispatch`로 요청한다. [GitHub 실행 트리거 설명](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow), [Kaggle 실행 안내](briefing-kaggle.md).

## 실패했을 때

- 요청 오류: 실행 보고서와 items.errors의 출처/주소 확인. 정상 데이터 없음과 구분한다. 일부 오류도 성공한 자료는 저장된다.
- 2026-10-03 GitHub Actions 실행에서는 여섯 식당 요청 모두 `http://errdoc.gabia.io/403.html`로 이동해 식당 이름을 확인하지 못했다. 이를 메뉴 미게시나 휴무로 처리하지 않고 수집 오류로 남겼다. 로컬 사이트 응답이 정상이어도 GitHub runner에서의 접근 성공을 보장하지 않는다.
- 이미지/첨부 글: 원문 링크에서 확인. 현재 OCR·PDF/HWP 내용 추출은 없다.
- 구조 변경: 해당 파서의 위쪽 선택자 상수 수정 후 저장 HTML로 테스트.
- DB 손상: 읽기에서 오류를 내므로 자동 덮어쓰지 않는다. 저장된 커밋/Actions 백업에서 정상 파일 복원 후 한 번만 실행한다.
- 실행 중단/시간 초과: 원자적으로 저장된 마지막 DB/실행 보고서까지만 남을 수 있다. 취소/러너 종료 시 백업·커밋 단계 실행은 보장하지 않는다.
- Git 충돌/브랜치 보호: 강제로 덮어쓰지 않는다. 다운로드 자료와 원격 DB를 비교하고 사람이 반영한다.

테스트는 오프라인 회귀 검증이다. 2026-10-06 통합 검증에서 `.venv/bin/python -m pytest -q -p no:cacheprovider collector/tests briefing/tests`가 321개 통과했다. 테스트 수는 이후 바뀔 수 있으므로 아래 명령으로 현재 상태를 확인한다.

```bash
python -m pytest -q -p no:cacheprovider collector/tests briefing/tests
```

## 공개 전 확인

이 저장소를 private에서 public으로 바꾸면 Git 이력뿐 아니라 기존 Issues/PRs와 Actions 실행 로그·아직 보관 중인 artifact도 공개될 수 있다. 수집 artifact는 `data/db/`, `data/raw/`, `data/runs/`, `output/app/`을 14일 보관하고, Kaggle 브리핑 artifact는 실행 입력 context·생성 파일·실패 로그 일부를 최대 3일 보관한다. 이 데이터에는 공지 본문, URL, 공개 연락처가 들어갈 수 있다. 공개 전 기록과 권리 확인 항목은 [공개 준비 점검](public-readiness.md)을 따른다.

수집 워크플로는 `contents: write`, `issues: write`, `actions: write` 권한으로 결과를 커밋·이슈 알림·선택적 Kaggle 작업 시작에 사용한다. 결과 알림은 GitHub Issue 댓글이며 개인 이메일 발송 기능은 없다. 이슈 댓글의 메일 수신 여부는 각 GitHub 사용자의 알림 설정에 따른다. 필요한 이유와 공개 전 점검은 저장소 공개 설정과 함께 확인한다.


### Kaggle 음성의 부분 실패
음성 하나의 생성·MP3 검증이 실패하면 그 구간만 제외하고 나머지는 계속 생성한다.
중복 공지가 공유하던 음성이 실패하면 연결된 게시판 모두에서 해당 공지를 제외한다.
정상 음성만 게시하고, 전부 실패하면 기존 게시 결과를 유지한다. 모델·화자 초기 검증 실패는 전체 실패다.
실패 항목·게시판·원인·재실행 안내는 진단 artifact의 `briefing-report.json`에 남는다.
GitHub의 **브리핑 실패 알림** Issue에 소유자를 멘션하여 기존 메일 알림으로 전달한다.
부분 실패도 알리며 자동 재시도는 하지 않는다. 길이 상한이면 대본을 짧게 나눈 뒤 다시 실행한다.
커널 업로드 전에 `kaggle quota`로 GitHub에 저장된 토큰의 인증과 남은 GPU 시간을 확인한다.
Kaggle에서 토큰을 발급한 뒤에는 GitHub Secrets의 `KAGGLE_API_TOKEN`도 갱신해야 한다.

Kaggle 브리핑은 별도 2시간 실행·대기 제한을 두지 않는다. GitHub 생성 작업은 플랫폼 최대 360분을 사용한다. 개별 상태 조회의 120초 연결 제한은 유지한다. Kaggle 자체 세션 제한은 플랫폼 정책을 따른다.


### 중단 후 음성 이어가기
Kaggle 자동 생성은 커널 하나에서 음성을 2시간까지 만든다(`briefing/kaggle_worker.py`의 `AUDIO_BATCH_SECONDS`). 개수 기준 30개였을 때는 2026-10-09 실행이 커널 9개로 나뉘어 준비 과정을 9번 반복했다. 시간이 차면 진행 중인 음성까지 마친 뒤 음성·대본 캐시와 실패 목록을 비공개 Kaggle 결과로 저장하고 정상 종료한다. 다음 묶음은 이전 결과를 입력으로 연결하여 완료한 음성은 다시 만들지 않는다. 전체가 끝난 뒤에만 사이트에 게시한다.

- 같은 GitHub 실행에서 **Re-run failed jobs**를 누르면 이전 시도의 마지막 저장 묶음을 자동으로 찾는다. GitHub가 강제로 종료해 artifact를 남기지 못해도 정상 완료된 Kaggle 묶음은 남아 있다.
- 새 workflow 실행에서 이어가려면 **resume_kernel**에 실패 메일/진단 자료의 저장된 커널 ID를 입력한다. 날짜도 이전과 같게 선택한다.
- 입력 공지·코드·대본/음성 모델 설정이 다르면 이전 캐시를 사용하지 않는다. 파일 경로와 SHA-256을 검사한 뒤 복원한다.
- 생성에 실패한 음성은 이후 묶음에서도 제외한다. 해당 음성을 다시 시도하려면 이어갈 자료 없이 새 실행을 시작한다.
- 강제 종료된 현재 묶음은 아직 저장되지 않았으므로 다시 처리할 수 있다. 저장된 이전 묶음은 재사용한다.
- 묶음마다 패키지 설치·모델 준비 시간이 추가되므로 묶음 수를 줄이는 쪽이 빠르다. 강제 종료되면 저장 전인 현재 묶음(최대 2시간 분량)을 다시 만든다.

## 완료 결과 자동 게시

음성 생성은 기본적으로 게시까지 요청한다. 수집 날짜가 다음 날로 넘어가도 생성된 음성을 게시하며, 이미 게시된 더 최신 날짜 또는 같은 날짜의 더 최신 실행을 이전 결과로 덮어쓰지 않는다. 생성 당시 commit의 원래 입력 해시·GPU 실행·파일 해시 검증은 유지한다. 같은 날짜의 수집 파일이 나중에 갱신되어도 원래 commit으로 검증한다.

GitHub의 6시간 대기 제한 등으로 생성 워크플로가 중단되면 `완료된 Kaggle 음성 자동 게시`가 별도로 마지막 커널을 기다리고, 전체 생성이 완료된 결과를 받아 게시·배포한다. 게시를 끈 시험 실행은 자동 복구하지 않는다. 전체 생성이 아직 미완료인 checkpoint는 게시하지 않으며, 기존 이어가기 기능으로 생성부터 마쳐야 한다. 과거 실행은 이 워크플로에서 원래 실행 ID를 넣어 수동으로 가져올 수 있다.

이어가는 묶음은 입력·프롬프트·검수 기준과 일치하는 대본 캐시를 모두 확인한 경우 Ollama 설치·모델 다운로드·실행을 생략한다. 대본 누락이나 검수 불일치가 하나라도 있으면 기존 준비·생성 절차로 돌아간다. 재생성한 두 번째 대본의 검수 생략 정책은 유지한다. 준비 시간 절약의 실제 효과는 별도 Kaggle 실측이 필요하다.

Kaggle 음성 모델은 비공개 데이터셋에서 읽는다. 연결 및 고정 버전 검증 정보는 `briefing/model_cache.py`와 [Kaggle 운영 안내](briefing-kaggle.md)를 참고한다. 첫 데이터셋 등록 이후에도 패키지 설치·GPU 모델 적재 시간은 남으며 실제 음성 생성 시간 자체가 줄어드는 변경은 아니다.
