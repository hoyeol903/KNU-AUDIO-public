# 교류 모집글 공유

이 저장소의 홈페이지는 GitHub Pages에 배포된다. GitHub Pages는 공유 API를 실행하지 않는다. 교류 상세·작성 화면과 예시는 바로 사용할 수 있으며, 실제 모집글 공유·신청은 별도로 배포한 Cloudflare Pages Functions API와 D1을 연결해야 한다. 글 제목을 누르면 상세 설명, 일정·장소, 참가 조건·비용, 인스타그램 또는 오픈카카오톡 참가 문의 링크를 볼 수 있다. 과팅은 팀·팀별 인원·희망 상대, 스터디는 공부 주제·목표, 소모임은 주요 활동을 입력한다.

## 공유와 작성자 권한

- 실제 글은 D1에 저장되며 다른 브라우저에서도 조회된다. 기존 30개 예시는 분리된 예시 목록에서 볼 수 있고 실제 참가 신청·연락 링크는 없다. 예시 링크를 임의의 실제 계정으로 만들지 않는다.
- 신청자는 이름·별명, 소개 메시지, 자신의 연락 링크를 제출한다. 신청은 참가 확정이 아니며 모집자가 확인한다. 신청자의 연락 링크와 메시지는 모집자만 조회할 수 있다.
- 초기 인증은 브라우저별 256비트 무작위 토큰이다. DB에는 토큰 SHA-256 해시만 저장하며 공개 API는 해시를 반환하지 않는다. 사용자가 브라우저 데이터를 지우거나 다른 기기로 이동하면 기존 글·신청 관리 권한을 복구할 수 없다. 학과·이름은 자기 기입 정보이며 경북대 재학생 인증을 제공하지 않는다. 다중 기기 계정 로그인은 후속 기능이다.
- 토큰은 앱 설정 초기화와 분리해서 `knua-community-device-v1`에 보관한다. 기존 `meetMine` 로컬 글은 공유 서버에 자동 업로드하지 않으며 개인 기록으로 유지한다.
- 작성자는 수정·마감·재개·삭제할 수 있다. 마감 글은 일반 목록에서 빠지고 '내 모집글'에 남는다. 삭제하면 신청도 같이 삭제된다. 신청자는 신청 내용을 수정하거나 취소할 수 있다. 모집자 내역에는 최근 100개를 표시한다.

## API

기본 주소 `/api/community`. 모든 응답은 JSON, `Cache-Control: no-store`. 변경 요청은 `Authorization: Bearer <browser-token>`과 `Content-Type: application/json`이 필요하다. 읽기에도 토큰을 전달하면 `mine`을 판별한다.

| 요청 | 역할 |
|---|---|
| `GET /meetings?category=study` | 최신 모집글 30개, 분류별 모집 수, nextCursor |
| `GET /meetings?category=study&mine=1` | 작성자 자신의 글, 마감 포함 |
| `GET /meetings?cursor=<created_at:id>` | 다음 페이지 |
| `POST /meetings` | UUID로 멱등 등록, 동일 요청 재시도 시 중복 없음 |
| `GET /meetings/:id` | 상세 |
| `PUT /meetings/:id` | 작성자만 수정·마감 상태 변경 |
| `DELETE /meetings/:id` | 작성자만 삭제, 신청 삭제 |
| `POST /meetings/:id/applications` | 신청·신청 내용 수정 |
| `GET /meetings/:id/applications` | 모집자만 신청 내역 조회 |
| `DELETE /meetings/:id/applications` | 자신의 신청 취소 |

등록 필수: category, title(60자), intro(2,000자), when(100자), contact(500자). 스터디는 goal, 소모임은 activity, 둘 다 capacity(정수 2~100). 과팅은 team(m/f), size(2:2/3:3/4:4). 선택: where, requirements, cost, want, dept, college. contact는 `https://instagram.com/...`, `https://www.instagram.com/...`, `https://open.kakao.com/...`만 허용한다. HTML은 화면에서 escape하며 인스타/카카오 외부 링크는 새 창과 noopener/noreferrer를 사용한다. 요청 본문 상한 16KB, 브라우저 응답 대기 15초. 실패 시 입력을 유지하고 성공 메시지를 띄우지 않는다.

등록 한도는 작성자 하루 20개, IP 하루 100개. 신청·수정은 작성자 하루 100회, IP 하루 500회. 공유 IP의 한도는 여러 사용자가 합산한다. DB 카운터는 하루별로 초기화하고 오래된 키를 정리한다. 분류·날짜·작성자 인덱스와 커서 페이지 이동을 사용한다. 비용·접근 권한 경계의 기본 방어이며 학교 인증·신고/차단·자동 스팸 판별을 포함하지 않는다.

## GitHub Pages와 공유 API 연결

이 PR은 기존 `.github/workflows/deploy.yml`의 GitHub Pages 배포를 유지한다. 홈페이지 공개만으로 API·DB가 만들어지지 않는다. GitHub Pages에서 API 주소가 설정되지 않았으면 네트워크 요청을 보내지 않고 연결 준비 중 안내를 표시한다. 실제 공유 등록 성공으로 처리하지 않으며 예시 상세·작성 칸은 볼 수 있다.

공유 백엔드는 Cloudflare Pages Functions + D1을 별도로 배포해야 한다. 이 저장소의 `functions/`, `community/api.mjs`, `migrations/`는 그 백엔드 코드이다. `community/setup.py`는 기존 `knu-audio` Cloudflare 프로젝트의 D1 스키마·바인딩 설정 도구이고 GitHub Pages 배포에서는 자동 실행하지 않는다. 해당 계정의 Pages 편집·D1 편집 권한이 있는 환경에서 `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`를 지정하고 `python3 community/setup.py --environment preview` 또는 production을 실행할 수 있다. 프로젝트가 없거나 계정이 다르면 먼저 별도 프로젝트 설정이 필요하다.

백엔드 배포 후 다음 두 항목을 설정한다.

1. 홈페이지의 첫 앱 script보다 앞에 `window.KNUA_COMMUNITY_API_BASE = 'https://<백엔드주소>/api/community/';`를 설정한다. 이 값은 공개 API 주소이며 비밀 토큰이 아니다. `tools/knua-app.html`과 앱 출력에 함께 반영한다. 같은 출처의 Cloudflare Pages/로컬에서는 기존 `/api/community/`를 기본으로 사용한다.
2. 백엔드 환경 변수 `COMMUNITY_ALLOWED_ORIGINS`에 `https://hoyeol903.github.io`를 지정한다. 브라우저 Origin에는 `/KNU-AUDIO-public/` 경로를 넣지 않는다. 여러 출처는 쉼표로 구분한다. 허용한 출처에만 CORS 응답과 Authorization/Content-Type preflight를 제공한다.

DB 바인딩 이름은 `COMMUNITY_DB`. preview와 production DB는 분리한다. Cloudflare 배포에서는 `output/app/_routes.json`으로 API 경로만 Functions에 보낸다. GitHub Pages에서는 이 파일이 API 기능을 활성화하지 않는다. 비밀 토큰은 브라우저 HTML·공개 저장소에 넣지 않는다. 공지 수집·내보내기는 공유 DB를 덮어쓰지 않는다.

## 검증

`node community/test_api.mjs` (Node 22.13 이상, 내장 SQLite 필요). 메모리 DB에서 타 브라우저 조회, 작성자 권한, 신청 정보 비공개, URL 검증, 재시도, 커서 페이지 이동, 등록 한도, 마감·삭제를 확인한다.

로컬 브라우저 미리보기는 D1 바인딩을 포함한 `npx wrangler@4 pages dev output/app --d1 COMMUNITY_DB`를 사용한다. 초기 스키마 적용은 동일한 로컬 D1에 해야 한다. 단순 `python -m http.server`는 API가 없어 공유할 수 없다. 운영 반영 전에 독립된 두 브라우저로 등록→조회→신청→모집자 확인→수정→마감→취소를 검사한다.
