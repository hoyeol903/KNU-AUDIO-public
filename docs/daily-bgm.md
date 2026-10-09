# 하루 배경음악

`tools.download_bgm`은 Kevin MacLeod의 Incompetech 공식 원본 30곡을 내려받고, 곡별 출처, ISRC, 다운로드 주소, CC BY 4.0 이용 조건, 수정 여부, SHA-256, 재생 시간을 `assets/bgm/catalog.json`에 기록합니다. 원본 MP3는 자르거나 변환하지 않습니다. 실행은 인터넷 연결이 필요합니다.

곡은 [Incompetech 공식 음악 목록](https://incompetech.com/music/royalty-free/full_list.php)과 해당 사이트의 `pieces.json`에서 ISRC·제목·파일명을 대조한 뒤 공식 MP3 주소에서 받습니다. 모든 곡에는 Kevin MacLeod와 Incompetech 출처를 표시하고 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 조건을 따릅니다. 앱 설정의 ‘배경음악 출처’에는 오늘 배포된 한 곡의 크레딧과 원본·라이선스 링크가 표시됩니다.

`python -m tools.daily_bgm --output <앱>/data/bgm`은 한국 날짜와 파일명 목록으로 하루 한 곡을 고르고, 내용 SHA-256 파일명과 `track.json`을 기록합니다. 카탈로그가 있으면 선택된 곡의 항목과 파일 해시를 확인하며, 불일치하면 배포 파일을 만들지 않습니다. 같은 날짜와 목록이면 같은 곡이며, 빈 폴더에서는 `audio: null`을 기록합니다.

`collector.export_app`은 로컬 내보내기 결과를 만들 때 선택기를 호출합니다. Pages 배포도 앱 파일 복사 후 같은 선택기를 실행하므로 원본 음악은 배포하지 않고 선택곡 하나만 올립니다. 앱의 ♪ 버튼으로 BGM을 켜고 끌 수 있습니다.

음악은 기본 음량 10%로 반복되며, 브리핑을 멈추거나 끝내면 함께 멈춥니다. 음악을 불러오지 못해도 공지 음성은 계속 재생됩니다. 모든 사용자가 같은 곡을 듣지만 랜덤 선택이므로 다른 날에도 같은 곡이 뽑힐 수 있습니다. 곡 변경은 한국 날짜가 바뀐 뒤 다음 배포에서 반영됩니다. 자정에 별도 작업을 실행하지는 않습니다. 당일 원본 파일 목록을 바꾸면 선택곡도 바뀔 수 있습니다.

확인 명령:

```bash
python -m pytest -q collector/tests briefing/tests
node collector/tests/test_daily_bgm_player.mjs
```

`assets/bgm/`에 공식 원본 MP3 30곡과 검증된 카탈로그가 있습니다. 앱 자료에는 날짜별로 선택된 한 곡만 포함합니다. 음성·음악 동시 재생은 휴대폰 브라우저에서 확인하세요.
