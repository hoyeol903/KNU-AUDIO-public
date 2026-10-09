# 신고와 관리자 화면

일반 이용자는 공유 모집글 상세에서 **이 글 신고하기**를 눌러 1~300자로 사유를 남긴다. 개인정보를 적지 않는다. 같은 브라우저가 같은 글을 다시 신고하면 기존 신고를 유지한다. 신고만으로 자동 숨김 처리하지 않는다.

관리자는 모임 서버의 `/admin`에서 로그인하고 신고된 글을 숨기거나 다시 공개한다. 현재 주소는 https://knua-community-api.knua-public-pr73.workers.dev/admin 이다. GitHub Pages 홈페이지의 `/admin` 주소가 아니다. 로그인 화면은 누구나 열 수 있지만 신고 자료와 숨김 기능은 관리자만 사용할 수 있다.

숨긴 글은 일반 목록·상세·신청·알림에서 제외된다. 작성자의 내 모집글에서는 확인·수정·삭제할 수 있으나 수정해도 숨김은 풀리지 않는다. 숨김은 기존 신청이나 글을 삭제하지 않는다. 관리자 삭제와 브라우저 권한 복구는 이번 작업에 포함하지 않는다.

## 팀원이 서버에 적용할 순서

이 PR은 서버 배포와 실제 계정 등록을 하지 않는다. **0003 데이터베이스 변경이 필요하다.** 기존 PR #47의 배포만으로는 사용할 수 없다.

1. 기존 Worker/D1에 연결된 실제 설정 파일을 사용한다. 새 데이터베이스를 만들지 않는다.
2. 먼저 데이터베이스 변경을 적용한다.
   ```sh
   npx wrangler@4 d1 migrations apply knua-community --remote --config community/wrangler.local.toml
   ```
3. Worker를 배포한다.
   ```sh
   npx wrangler@4 deploy --config community/wrangler.local.toml
   ```
4. 관리자가 자신의 터미널에서 계정을 정하고 등록한다. 비밀번호는 입력할 때 화면에 표시되지 않으며 파일에 저장하지 않는다.
   ```sh
   python community/admin_credentials.py --config community/wrangler.local.toml
   ```
5. 홈페이지 배포 후 실제 글 1개를 신고하여 관리자 숨김·해제와 일반 목록 반영을 확인한다.

설정 파일 이름이 다르면 실제 파일 경로로 바꾼다. `community/setup.py`는 옛 Pages 연결용으로 이 Worker 배포에 사용하지 않는다. 현재 D1 이름이 예시와 다르면 실제 이름을 사용한다. 새 관리자 계정은 `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` Worker Secrets로 등록한다. 평문 비밀번호를 GitHub나 채팅에 올리지 않는다.

비밀번호는 PBKDF2-SHA256(210,000회, 무작위 salt)로 해시 처리한다. 로그인 쿠키는 HTTPS·HttpOnly·SameSite=Strict이며 8시간 뒤 만료된다. 로그아웃 또는 계정 변경으로 기존 세션을 무효화한다. 로그인은 IP별 시간당 10회, 서버 전체 시간당 200회 제한한다. 관리자 변경 요청은 같은 서버 출처에서만 받는다. 신고 사유는 일반 이용자에게 공개하지 않는다.

## 오프라인 확인

```sh
node --test community/test_api.mjs community/test_worker.mjs community/test_admin.mjs
python -m pytest -q community
```
