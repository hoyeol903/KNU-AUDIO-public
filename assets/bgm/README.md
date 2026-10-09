이 폴더에는 Kevin MacLeod의 Incompetech 공식 원본 MP3 30곡을 받을 준비가 되어 있습니다. `python -m tools.download_bgm` 실행 후 곡별 ISRC, 공식 출처와 다운로드 URL, CC BY 4.0 라이선스, 출처 표시, 수정 여부, SHA-256, 재생 시간을 `catalog.json`에 기록합니다.

이 폴더에 원본 MP3 30곡과 생성된 `catalog.json`이 있습니다. 앱에는 날짜별로 고른 한 곡만 포함됩니다. 자세한 내용은 `docs/daily-bgm.md`를 참고하세요.

앱 배포에는 `tools/daily_bgm.py`가 하루 한 곡만 골라 `data/bgm/`에 넣습니다. 원본 폴더 전체는 배포하지 않습니다.
