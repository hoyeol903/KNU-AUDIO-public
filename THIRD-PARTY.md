# 외부 모델과 라이브러리

모델 가중치는 이 프로젝트에 포함하지 않습니다. 설치할 때 공식 저장소에서 받습니다.

- Qwen3 4B Instruct 2507(`qwen3:4b-instruct-2507-q4_K_M`): Apache-2.0. https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507 및 https://ollama.com/library/qwen3
- Ollama: 로컬 실행 엔진. https://github.com/ollama/ollama
- 이전 버전 MeloTTS 소스 및 Korean 모델: MIT 표기. https://github.com/myshell-ai/MeloTTS 및 https://huggingface.co/myshell-ai/MeloTTS-Korean
- MeloTTS 설치 안내: https://github.com/myshell-ai/MeloTTS/blob/main/docs/install.md
- FFmpeg 및 Python 라이브러리는 각자의 라이선스를 따릅니다. MeloTTS의 언어 처리기/보조 모델도 별도 의존성입니다.

모델·라이브러리를 재배포할 때는 해당 버전의 라이선스와 저작권 고지를 함께 보존하세요. 특정 실존 성우의 목소리 복제는 구현하지 않았습니다.

현재 앱에 넣는 음악은 `assets/bgm/catalog.json`에 기록된 Kevin MacLeod의 Incompetech 원본 30곡이며, 2026-10-09 아침용 새 30곡으로 교체했다. 각각 CC BY 4.0 크레딧과 공식 다운로드 출처를 기록하며 원본 재배포 시에도 해당 표시를 보존한다. 일괄 표시는 `assets/bgm/ATTRIBUTION.txt`를 참고한다. 곡별 출처·앱 표시 방법은 [하루 배경음악](docs/daily-bgm.md)을 따른다.

권리 확인 필요: `Mas Cafe - Casa Rosa.mp3`는 이전 사용자 제공 파일로 현재 작업 트리에는 없지만 `knu-audio-qwen3-staging/assets/Mas Cafe - Casa Rosa.mp3` 경로가 Git 이력에 남아 있다. 이전 문서에 재배포 허락 범위가 확인되지 않았다고 기록되어 있다. 이 파일의 저장소 이력 공개 및 서비스 재생 권한을 확인하기 전에는 전체 Git 이력을 공개하지 않는다. 현재 Incompetech 30곡의 라이선스와 이 과거 파일의 권리는 별도로 취급한다. 이 기록은 허가가 확인됐다는 뜻이 아니다.

- 현재 음성 모델: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice, Apache-2.0. https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
- 현재 음성 라이브러리: qwen-tts 0.1.1, Apache-2.0. https://github.com/QwenLM/Qwen3-TTS
- Sohee·Aiden은 모델의 기본 화자입니다. 한국어는 Korean으로 명시합니다. 현재 1.7B CustomVoice에는 고정된 스타일 지시를 사용합니다.

공개 저장소는 정리한 최신 스냅샷으로 시작하며 위의 과거 사용자 제공 음악 파일과 기존 Git 이력은 포함하지 않습니다. 해당 파일이 포함된 기존 저장소는 비공개로 보관합니다.
