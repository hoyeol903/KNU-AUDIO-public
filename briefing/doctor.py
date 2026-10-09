"""python -m briefing.doctor: 다운로드/생성 없이 현재 환경만 확인."""
import importlib.util
import shutil
import sys
from briefing.build import ROOT, read_yaml
from briefing.slm import Ollama


def main():
    print('Python:', sys.version.split()[0])
    print('FFmpeg:', shutil.which('ffmpeg') or '미설치')
    print('Qwen3-TTS:', '설치됨 (실제 모델 로드는 별도)' if importlib.util.find_spec('qwen_tts') else '미설치')
    try:
        identity = Ollama(read_yaml(ROOT / 'config/briefing.yaml')['slm']).identity()
        print('SLM:', identity)
    except RuntimeError as exc:
        print('SLM:', exc)


if __name__ == '__main__':
    main()
