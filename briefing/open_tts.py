"""MeloTTS 공식 KR 화자. 유명인 음성/성별 변환을 사용하지 않는다."""
from pathlib import Path
import os
import ssl
import sys
import importlib.util
import re
import shutil
import subprocess
import tempfile
from datetime import date

VOICE_NAMES = {'kr': 'MeloTTS 한국어 기본 목소리'}

_FULL_DATE = re.compile(r'(?<!\d)(\d{4})\s*(?:년|[./-])\s*(\d{1,2})\s*(?:월|[./-])\s*(\d{1,2})\s*일?(?!\d)')
_CLOCK = re.compile(r'(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)')
_ACRONYMS = {
    'AI': '에이아이', 'HWP': '에이치더블유피', 'ICT': '아이씨티',
    'IT': '아이티', 'KNU': '케이엔유', 'PDF': '피디에프',
    'URL': '유알엘', 'WFK': '더블유에프케이',
}
_ACRONYM_RE = re.compile(r'(?<![A-Za-z])(?:' + '|'.join(sorted(_ACRONYMS, key=len, reverse=True)) + r')(?![A-Za-z])', re.I)


def _spoken_date(match):
    year, month, day = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return match.group(0)
    return f'{year}년 {month}월 {day}일'


def _spoken_clock(match):
    hour, minute = map(int, match.groups())
    return f'{hour}시' + (f' {minute}분' if minute else '')


def spoken_text(text):
    # KR 모델의 발음 기호 목록에 없는 URL/이메일 기호를 발화 가능한 문장으로 바꾼다.
    # 원문 대본은 별도로 유지한다.
    text = re.sub(r'''https?://[^\s<>()\[\]"']+''', '화면의 원문 링크', text)
    letters = dict(zip('abcdefghijklmnopqrstuvwxyz',
                       ['에이','비','씨','디','이','에프','지','에이치','아이','제이','케이','엘','엠',
                        '엔','오','피','큐','알','에스','티','유','브이','더블유','엑스','와이','지']))
    symbols = {'@':'골뱅이', '.':'점', '_':'언더바', '-':'하이픈', '+':'플러스', '%':'퍼센트'}
    def email(match):
        return ' '.join(letters.get(c.lower(), symbols.get(c, c)) for c in match.group())
    text = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', email, text)
    text = re.sub(r'(\d+)\.(\d+)(?=\s*(?:도|퍼센트))', r'\1점\2', text)
    return text.replace('@', ' 골뱅이 ').replace('_', ' 언더바 ').replace('\ufeff', '')


def qwen_spoken_text(text):
    """Qwen-specific date/time and acronym cues; legacy Melo text stays unchanged."""
    text = spoken_text(text)
    # Give common structured dates and 24-hour times Korean unit cues so the
    # speech model does not alternate between reading punctuation as decimals.
    text = _FULL_DATE.sub(_spoken_date, text)
    text = _CLOCK.sub(_spoken_clock, text)
    text = _ACRONYM_RE.sub(lambda match: _ACRONYMS[match.group().upper()], text)
    # 느낌표는 그 문장만 들뜨게 읽히게 한다. 화면 대본은 그대로 두고 음성 입력에서만 마침표로 바꾼다.
    return re.sub(r'[!！]+', '.', text)


def prepare_language_resources():
    """macOS Python의 기본 CA가 없으면 certifi를 사용한다. TLS 검증 유지."""
    import certifi
    korean_packages = Path(__file__).resolve().parents[1] / '.cache' / 'korean-mecab'
    if korean_packages.is_dir() and str(korean_packages) not in sys.path:
        sys.path.insert(0, str(korean_packages))
    if importlib.util.find_spec('mecab') is None:
        raise RuntimeError('한국어 분석기 준비가 필요합니다. python -m briefing.setup_tts를 실행하세요.')
    if not os.environ.get('SSL_CERT_FILE') and ssl.get_default_verify_paths().cafile is None:
        os.environ['SSL_CERT_FILE'] = certifi.where()
    import nltk
    directory = Path(__file__).resolve().parents[1] / '.cache' / 'nltk_data'
    directory.mkdir(parents=True, exist_ok=True)
    if str(directory) not in nltk.data.path:
        nltk.data.path.insert(0, str(directory))
    for resource, location in [('cmudict', 'corpora/cmudict.zip'),
                               ('averaged_perceptron_tagger', 'taggers/averaged_perceptron_tagger.zip')]:
        try:
            nltk.data.find(location)
        except LookupError:
            print(f'발음 자료 준비: {resource}', flush=True)
            if not nltk.download(resource, download_dir=str(directory), quiet=True, raise_on_error=True):
                raise RuntimeError(f'발음 자료 다운로드 실패: {resource}')


def prepare_mecab_dictionary():
    """KR도 Melo의 일본어 모듈을 import한다. 비어 있는 UniDic만 보완한다.

    설치 파일을 수정하지 않고 이 프로세스의 MeCab 기본 경로를 지정한다.
    완전한 UniDic 사전이 있으면 그대로 사용한다.
    """
    import unidic

    def complete(directory):
        return all((Path(directory) / name).is_file()
                   for name in ('mecabrc', 'dicrc', 'sys.dic', 'unk.dic', 'matrix.bin', 'char.bin'))

    if complete(unidic.DICDIR):
        return unidic.DICDIR
    try:
        import unidic_lite
    except ImportError as exc:
        raise RuntimeError('MeCab 사전이 없습니다. python -m unidic download를 실행하세요.') from exc
    if not complete(unidic_lite.DICDIR):
        raise RuntimeError('MeCab 사전 데이터가 불완전합니다. python -m unidic download를 실행하세요.')
    unidic.DICDIR = unidic_lite.DICDIR
    return unidic.DICDIR


class Melo:
    def __init__(self):
        self.model = None

    def verify(self, voice, role, model):
        if voice != 'KR' or role != 'kr' or model != 'myshell-ai/MeloTTS-Korean':
            raise ValueError('이 버전은 MeloTTS Korean의 KR 화자만 지원합니다.')
        if not shutil.which('ffmpeg'):
            raise RuntimeError('MP3 변환용 ffmpeg가 필요합니다. START-HERE.md를 확인하세요.')

    def synthesize(self, text, voice, model, tempo):
        if self.model is None:
            try:
                prepare_language_resources()
                prepare_mecab_dictionary()
                from melo.api import TTS
            except ImportError as exc:
                raise RuntimeError('MeloTTS 설치가 필요합니다. START-HERE.md의 음성 환경을 준비하세요.') from exc
            self.model = TTS(language='KR', device='cpu')
        with tempfile.TemporaryDirectory() as td:
            wav, mp3 = Path(td) / 'voice.wav', Path(td) / 'voice.mp3'
            self.model.tts_to_file(spoken_text(text), self.model.hps.data.spk2id[voice], str(wav), speed=tempo)
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(wav),
                            '-codec:a', 'libmp3lame', '-b:a', '96k', str(mp3)], check=True,
                           timeout=180, capture_output=True)
            return mp3.read_bytes()
