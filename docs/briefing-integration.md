# 브리핑과 앱 화면 연동

2026-10-07 기준 운영 경로다. 수집 자료를 입력으로 대본·음성을 만들고, 검증한 결과를 정적 앱 형식으로 내보낸다. 현재 웹 호스팅은 GitHub Pages다.

## 실제 흐름

```text
collector workflow
  └─ data/raw/<날짜>/items.json
       └─ briefing-kaggle workflow (수집 뒤 ENABLE_KAGGLE_BRIEFING=true일 때 연결)
            └─ 비공개 Kaggle T4 커널: SLM 대본 → 규칙 검수 → Qwen3 TTS
                 └─ 해시·날짜·파일 검증
                      └─ output/app/data/briefing/segments.json + MP3
                           └─ GitHub Pages
```

Kaggle 워크플로의 수동 실행은 저장된 스냅샷으로 생성·검증만 하며, `publish=true`를 선택하지 않으면 앱 데이터를 바꾸지 않는다. 수집 뒤의 자동 연결은 저장소 변수 `ENABLE_KAGGLE_BRIEFING=true`일 때만 실행한다. 대본이나 음성 검증이 실패하면 게시 단계는 진행하지 않는다. 세부 실행 절차와 오류 처리는 [Kaggle 브리핑 안내](briefing-kaggle.md)와 [운영 문서](operations.md)를 본다.

Kaggle에 보내는 입력은 모든 저장소가 아니라 `briefing/`, `collector/` Python 파일, 필요한 설정·의존성 목록·플레이어 파일, 선택 날짜의 `items.json`으로 구성한 명시적 파일 allowlist다. `items.json` 본문에는 공지 제목·본문·URL·연락처가 들어갈 수 있다. 커널 metadata는 `is_private=true`이며 결과 artifact는 GitHub Actions에서 3일 보관한다. 공개 전송 승인 여부와 보관 권한은 [공개 준비 점검](public-readiness.md)에서 따로 확인한다.

## 마감 날짜를 다루는 범위

`collector.deadlines.extract_deadline(title, body)`가 원문 제목·본문에서 단일 마감 날짜를 찾고 그 결과가 수집 자료의 `deadline`과 일치할 때만 날짜를 요약 입력의 확인 정보로 전달한다. 게시일 계열 날짜·다중 날짜·불일치·근거 누락은 미검증 처리한다. 날짜가 확인되지 않으면 대본 필수 항목, 브리핑 구간 D-day, 카드의 “마감 임박” 표시에서 마감 주장을 제외한다. 확인 결과와 원문 근거 문장은 내부 `output/briefing-report.json`의 `deadline_checks`에 남으며, 내부 판정 정보는 앱 manifest에 싣지 않는다.

명시적인 마감 날짜와 함께 본문에 행동명이 같은 줄에서 라벨로 적혀 있으면 해당 행동을 날짜와 연결해 안내한다. 이 행동명도 날짜가 검증된 경우에만 전달한다. 오늘 마감 문구와 D-day는 입력 `dday` 값을 믿지 않고 확인된 날짜와 자료 기준일을 비교해 계산한다.

대본 검수는 비어 있지 않은 3500자 이하 문자열인지, 원문에 없는 숫자값이 추가됐는지, 이메일·전화번호·학번/주민번호 형식 및 설정한 비속어 패턴이 있는지만 확인한다. 날짜 구분자/앞자리 0과 `17:00`·`오후 5시` 같은 표기 차이는 숫자값으로 정규화한다. 이 검사는 숫자가 어느 사실에 귀속되는지, 날짜·대상·장소·조건의 의미가 맞는지 판별하지 않는다. 패턴에 잡히지 않는 개인정보나 의미가 뒤집힌 문장도 통과할 수 있으며, 비속어 패턴은 모든 표현을 포괄하지 않는다. 첫 대본이 검수에 실패하면 지적 내용을 바탕으로 한 번 재생성한다. 두 번째 대본은 규칙 재검수 없이 음성 생성에 사용하며 `revision-unchecked`로 기록한다. 제외된 공지의 ID·제목·URL·오류는 내부 보고서에, 처리 상태와 구간 ID는 진행 기록에 남긴다. 제외된 공지의 원문/초안은 앱 manifest와 재생 구간에 싣지 않는다. 모델 연결·응답 실패, 음성 생성 실패는 전체 빌드를 계속 실패 처리한다. 최종 사실 확인은 원문 링크에서 별도로 해야 한다.

## 음성 구간 간 일관성

Qwen3-TTS 1.7B CustomVoice의 Sohee 화자를 사용하고, 설정의 여성 화자 문장에 맑고 안정감 있는 아침 라디오 스타일 지시를 넣는다. 남성 Aiden은 `voices`에 포함하면 선택할 수 있으며, 여성 음역 지시는 Aiden에 전달하지 않는다. 생성은 샘플링 설정을 유지하되 각 대본마다 같은 Torch 난수 seed를 별도 RNG 범위에서 적용해, 같은 입력의 재생성이 일관되도록 한다. 발화 텍스트에서는 `YYYY.MM.DD` 날짜, 24시간 시각, 사전에 정한 일부 약어(KNU, WFK, AI, PDF 등)를 한국어 단위·글자 읽기로 정규화한다. 이는 해당 표기만 다루며, 이름과 임의 약어의 발음을 보장하지 않는다.

날씨 조언은 `좋겠어요`보다 `좋을 것 같아요`처럼 차분한 라디오 말투를 쓴다. 각 MP3는 앞뒤 무음의 긴 꼬리를 보수적으로 정리하고 짧은 끝 여백을 넣은 뒤, FFmpeg 2회 측정·보정으로 통합 음량을 -19 LUFS, 트루피크를 -2 dBTP 목표로 맞춘다. 실제 출력값은 음성 길이와 입력 음량에 따라 달라질 수 있다. 앱의 개인화 인사는 브라우저 SpeechSynthesis가 읽으므로 Qwen 음성과 같은 화자·음량 처리가 적용되지 않는다. Qwen 캐시 버전과 키에 모델·화자별 지시·seed·발음 텍스트·음량·여백 정책을 포함해 이전 MP3 캐시를 재사용하지 않는다. 전체 브리핑 2분 목표와 사람 청취 품질은 별도의 실제 재생 샘플로 확인해야 한다.

## 앱 출력 계약

브리핑 빌드 내부 `dist/manifest.json`과 앱이 읽는 출력은 구분한다. 앱 데이터는 `output/app/data/briefing/segments.json`이며 상단에 기준 날짜와 음성 이름, `segments` 배열을 둔다. 각 구간에는 ID, 채널 ID, 제목, 읽을 대본, 재생 길이, MP3 파일명, 카드 `items`가 들어간다. 이름 인사에는 선택적인 `personal_template`이 있고 실제 학생 이름은 저장하지 않는다. 카드에는 구분, 원문 제목, 날짜/출처 상세, 원문 URL, 공지 ID가 들어가며 화면 D-day 값은 현재 null로 둔다.

`briefing.app_export`는 새 출력에서 공지별 음성을 유지하고 관련 채널들을 연결한다. 인사·날씨나 식당처럼 여러 내부 음성을 묶는 구간은 FFmpeg concat stream copy를 사용한다. 이전 manifest의 게시판별 출력도 계속 지원한다. 공지 원문 제목과 링크를 카드에 남긴다. 카드의 “마감 임박” 표시는 수집 reason이 reminder이면서 브리핑 manifest의 `deadline_verified`가 true일 때만 쓴다.

## 배경음악과 라이선스

Pages 배포는 `tools.daily_bgm`이 Incompetech CC BY 4.0 카탈로그에서 하루 한 곡을 선택해 앱 데이터에 넣는다. 현재 원본 30곡과 크레딧 목록은 [하루 배경음악](daily-bgm.md) 및 `assets/bgm/catalog.json`을 참고한다. 이전 staging 경로에 남아 있는 음악 파일은 별도 공개 준비 검토 대상이며, 현재 앱에 쓰는 30곡의 라이선스와 혼동하지 않는다.

## 확인 및 한계

2026-10-06 PR 통합 검증에서 아래 명령이 321개 테스트를 통과했다. 테스트 수는 이후 변할 수 있으므로 현재 결과는 명령으로 다시 확인한다.

```bash
python -m pytest -q -p no:cacheprovider collector/tests briefing/tests
node collector/tests/test_daily_bgm_player.mjs
```

오프라인 테스트 통과는 사실 의미의 완전한 검증이나 실제 Kaggle/Qwen TTS 실행을 보증하지 않는다. 개별 공지 제외 경로도 mock 기반 테스트이며 실제 사이트별 음성 생성은 별도로 확인해야 한다.

음성 생성의 총 15,000자 제한은 제거했다. 실제 생성 문자 수는 실행 보고서의 `new_characters`에 계속 기록한다. 모델 응답 오류와 비어 있는 대본, 음성 생성 오류는 실패 처리한다. 재생성 대본에는 잘못된 숫자나 개인정보가 남아 있어도 규칙으로 다시 차단하지 않는다.
