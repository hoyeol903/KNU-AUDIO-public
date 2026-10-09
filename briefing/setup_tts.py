"""Mac의 MeCab/mecab 경로 충돌을 피하는 한국어 분석기 설치."""
from pathlib import Path
import platform
import subprocess
import sys


def main():
    pip = [sys.executable, '-m', 'pip']
    if platform.system() == 'Darwin':
        # 같은 site-packages에서 mecab와 MeCab가 충돌하므로 KR만 별도 설치한다.
        subprocess.run(pip + ['uninstall', '-y', 'python-mecab-ko'], check=True)
        subprocess.run(pip + ['install', '--force-reinstall', '--no-deps', 'mecab-python3==1.0.9'], check=True)
        target = Path(__file__).resolve().parents[1] / '.cache' / 'korean-mecab'
        subprocess.run(pip + ['install', '--upgrade', '--target', str(target), 'python-mecab-ko==1.3.7'], check=True)
    else:
        subprocess.run(pip + ['install', 'python-mecab-ko==1.3.7'], check=True)
    print('한국어 분석기 준비 완료. 음성 생성을 다시 실행하세요.')


if __name__ == '__main__':
    main()
