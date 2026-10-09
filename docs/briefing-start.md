# 처음 실행하기 — Qwen3-TTS 남녀 목소리

대본은 Qwen3 4B, 음성은 Qwen3-TTS **1.7B CustomVoice**입니다. 현재 기본 설정은 여자 Sohee이며 차분하고 또렷한 아침 라디오 스타일 지시를 적용합니다. 모델에는 남자 Aiden도 남아 있어 `voices` 설정으로 선택할 수 있지만, 여성 스타일 지시는 전달하지 않습니다. Aiden은 영어 기반 화자로 한국어 발음을 실제로 확인하세요. 두 목소리 모두 모델의 기본 화자이며 Typecast나 특정 연예인 음성을 사용하지 않습니다.

## 1. 새 음성 환경 준비

VS Code에서 KNU-AUDIO-slm 폴더를 열고 Terminal → New Terminal을 엽니다. 기존 MeloTTS 환경에 덮어 설치하지 않습니다. Python 3.10~3.12, FFmpeg가 필요합니다. 공식 Qwen 가이드는 Python 3.12 새 환경을 권장합니다.

이전에 만든 .venv-tts가 있다면 프로젝트 폴더에서 한 줄씩 입력하세요.

```bash
.venv-tts/bin/python -m venv .venv-qwen-tts
source .venv-qwen-tts/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-tts.txt
```

기존 환경이 없으면 첫 줄 대신 `python3.12 -m venv .venv-qwen-tts`를 사용합니다. Mac에서 FFmpeg는 Homebrew가 있으면 `brew install ffmpeg sox`로 설치합니다. 이 버전은 MeCab/UniDic 설정이 필요하지 않습니다.

## 2. 목소리만 먼저 듣기

```bash
python -m briefing.voice_samples
```

첫 실행에 1.7B 모델을 다운로드합니다. output/qwen-samples/female.mp3와 male.mp3를 Finder에서 열어 들어보세요. 1.7B 모델은 큰 편이므로 CPU 생성은 오래 걸릴 수 있습니다. GPU 브리핑은 Kaggle T4를 사용하며, API 키는 필요하지 않습니다.

## 3. 전체 브리핑 만들기

Ollama 앱을 실행하고 대본 모델을 준비합니다.

```bash
ollama pull qwen3:4b
python -m briefing.build --input data/raw/2026-10-03/items.json --allow-archive
python -m http.server 8766 --directory dist --bind 127.0.0.1
```

브라우저에서 http://127.0.0.1:8766/ 를 엽니다. 이미 해당 서버가 실행 중이면 마지막 명령을 중복 실행하지 말고 화면을 새로고침하세요.

**안내 목소리**에서 여자/남자를 고르고 **내 브리핑 듣기**를 누릅니다. **음성 재생 속도**는 0.75~2배이며 재생 중에도 변경됩니다. 음높이를 유지하고 배경음악은 기본 속도로 재생합니다. WAV 저장 파일에는 재생 배속과 배경음악이 포함되지 않습니다.

기존 MeloTTS로 만든 dist는 새 음성을 생성하기 전까지 이전 목소리로 남습니다. 예전 음성을 여자/남자로 복제해 표시하지 않습니다. 새 생성이 성공하면 두 Qwen 목소리로 목록이 교체됩니다.

`--allow-archive`는 과거 자료 시험 전용입니다. 매일 운영에는 오늘의 items.json을 사용합니다. 입력 구조만 확인하려면 `--plan`, 대본만 만들려면 `--text-only`를 붙입니다. 대본 생성에는 Ollama가 필요합니다.

## 설정과 문제 확인

config/briefing.yaml의 tempo는 **생성 파일 속도**, 화면의 배속은 **듣는 사람의 재생 속도**입니다. 기본 생성 속도는 1입니다. tts.device는 auto(사용 가능한 CUDA 또는 CPU), cpu, cuda:0을 지원합니다. Mac은 현재 CPU 경로를 사용합니다. Sohee의 말투 지시는 `tts.instructions.female`에 설정하며, 남성 Aiden에는 여성 지시를 보내지 않습니다.

검수 실패는 output/review.json에서 확인합니다. 규칙은 의미 전체의 사실 검증을 보장하지 않습니다. 전체 학과 × 두 목소리를 CPU로 만드는 작업은 오래 걸리므로 GitHub의 하루 실행 시간과 생성 문자 상한을 관찰하세요. 모델/화자 변경은 새 캐시로 생성되어 이전 Melo MP3를 재사용하지 않습니다.

자동 실행 설정은 [GITHUB-AUTO-SETUP.md](GITHUB-AUTO-SETUP.md), 친구에게 전달할 목록은 [HANDOFF.md](HANDOFF.md)를 참고하세요.
