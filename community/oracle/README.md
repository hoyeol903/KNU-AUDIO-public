# GitHub Pages + Oracle Cloud 공유 API

홈페이지는 `https://hoyeol903.github.io/KNU-AUDIO-public/`에 유지하고, Oracle Cloud의 Ubuntu 가상 서버에서 Node.js API와 SQLite DB를 실행한다. Oracle Autonomous Database를 사용하는 구성이 아니다. 기존 D1용 SQL과 API를 SQLite 어댑터로 재사용하므로 모집글·작성자 권한·신청 공개 범위가 동일하다. DB 용량은 서버 디스크의 여유 공간에 따른다. 무료 서버도 Oracle의 자원·지역·가용 용량 제한을 받는다.

## 먼저 준비할 것

1. [Oracle Cloud 무료 계정](https://www.oracle.com/cloud/free/)을 만든다. 회원가입과 본인·결제 수단 확인은 계정 소유자가 직접 진행한다.
2. Compute → Instances에서 Ubuntu 24.04 서버를 만든다. 무료 운영을 원하면 콘솔의 **Always Free eligible** 표시와 생성 전 비용을 확인한다. 무료 서버 자원이 없는 지역에서는 생성이 실패할 수 있다.
3. 공인 IP와 SSH 키를 준비한다. 키 내용은 저장소나 채팅에 넣지 않는다. 서버 SSH는 자신의 IP에서만 허용하고, 웹용 TCP 80·443은 인터넷에 허용한다. OCI 보안 목록/NSG와 OS 방화벽 양쪽을 확인한다.
4. API용 도메인 또는 무료 DNS 이름의 A 레코드를 서버 공인 IP에 연결한다. 홈페이지가 HTTPS이므로 API에도 브라우저가 신뢰하는 HTTPS 인증서가 필요하다. Caddy가 인증서를 자동 발급·갱신한다.

## 서버 실행

서버에 [Docker Engine 및 Compose](https://docs.docker.com/engine/install/ubuntu/)를 설치한 뒤, 이 PR이 반영된 저장소를 체크아웃한다. API는 외부 포트를 직접 열지 않고 Caddy만 80·443을 제공한다.

```bash
git clone https://github.com/hoyeol903/KNU-AUDIO-public.git
cd KNU-AUDIO-public
# PR 병합 전 검토하려면 Oracle 기능 브랜치를 선택한다.
# git checkout feat/oracle-community-api
cp community/oracle/.env.example community/oracle/.env
# .env의 KNUA_API_DOMAIN을 실제 API 도메인으로 바꾼다.
sudo docker compose --env-file community/oracle/.env -f community/oracle/compose.yaml up -d --build
```

도메인 설정 후 `https://<API 도메인>/health`가 `{"ok":true}`이고 `https://<API 도메인>/api/community/meetings`가 빈 목록을 반환하는지 확인한다. 로그 확인은 같은 compose 명령의 `logs --tail=100 api caddy`를 사용한다. 첫 실행에서 SQL 테이블과 인덱스를 생성한다. 기존 테이블·글은 시작 시 덮어쓰지 않는다.

## GitHub Pages 연결

API 배포가 끝난 뒤 `tools/knua-app.html`과 `output/app/index.html`에서 기존 `var COMMUNITY_API_BASE` 바로 앞에 아래 설정을 추가하고 PR로 반영한다.

```javascript
window.KNUA_COMMUNITY_API_BASE = 'https://<API 도메인>/api/community/';
```

API 주소는 공개 정보이고 관리자 토큰은 넣지 않는다. 이 준비 PR에는 가상의 API 주소를 등록하지 않는다. 주소가 설정되지 않은 GitHub Pages 화면은 기존처럼 연결 준비 중 안내를 표시한다. 새 API는 `https://hoyeol903.github.io`에서의 CORS 요청만 허용한다. 다른 홈페이지를 추가하면 compose의 `COMMUNITY_ALLOWED_ORIGINS`에 출처만 쉼표로 추가한다.

## DB와 백업

SQLite DB는 Docker의 `community_db` 영구 볼륨에 저장된다. 컨테이너 재시작·이미지 업데이트 후에도 유지된다. **`docker compose down -v`는 DB 볼륨을 삭제하므로 사용하지 않는다.** 서버 삭제나 디스크 고장은 별도 백업으로 대비한다.

SQLite WAL 사용 중 원본 파일만 복사하지 않는다. 다음 명령은 SQLite 백업 API로 일관된 스냅샷을 만든다. 아래 명령의 결과를 서버 외부에 보관한다. 로컬 테스트로 백업 복원도 확인한다.

```bash
sudo docker compose --env-file community/oracle/.env -f community/oracle/compose.yaml exec -T api node --input-type=module -e 'import {DatabaseSync,backup} from "node:sqlite"; const db=new DatabaseSync("/var/lib/knua/community.sqlite"); await backup(db,"/var/lib/knua/community-backup.sqlite"); db.close();'
# 실행 중인 API 컨테이너에서 파일을 추출한다.
sudo docker cp "$(sudo docker compose --env-file community/oracle/.env -f community/oracle/compose.yaml ps -q api)":/var/lib/knua/community-backup.sqlite ./community-backup.sqlite
```

신청 연락처가 포함된 DB·백업은 공개 저장소에 올리지 않는다. 기존 Cloudflare에 생성한 빈 D1을 자동으로 삭제하거나 이동하지 않는다. Cloudflare가 필요 없는 Oracle 구성이다.

## 검증

- `node community/test_api.mjs`: 공통 API의 권한, 검증, 신청 비공개, 한도, 페이지 이동 등.
- `node community/oracle/test_server.mjs`: 실제 HTTP와 파일 DB로 두 사용자 간 공유, 재시작 후 영속성, CORS preflight, 신청자 정보 보호, 작성자 권한, 본문 크기 제한.
- 최소 Node 24를 사용한다. 추가 npm 의존성 없이 Node 내장 HTTP·SQLite로 실행한다.
- 운영 확인은 실제 도메인의 HTTPS와 독립된 두 브라우저에서 등록→조회→신청→모집자 확인→마감→삭제까지 진행한다.
- Oracle 계정·서버와 Docker가 없는 로컬에서는 실제 VM 배포·Compose 실행·HTTPS 발급을 검증할 수 없다.

참고: [Oracle 인스턴스 생성](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm), [무료 자원](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [Caddy HTTPS](https://caddyserver.com/docs/automatic-https), [Node SQLite](https://nodejs.org/api/sqlite.html).
