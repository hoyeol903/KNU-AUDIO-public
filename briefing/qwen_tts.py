"""Qwen3-TTS Base 모델로, 저장해 둔 참고 음성의 목소리를 모든 구간에 고정해 읽는다."""
from pathlib import Path
import math
import os
import re
import shutil
import subprocess
import tempfile
import json
from contextlib import contextmanager

from briefing.open_tts import qwen_spoken_text
from briefing.model_cache import MODEL as DATASET_MODEL, verify_model_directory

# ponytail: 실행할 때마다 Hugging Face에서 받는다(약 30초). 받지 못하는 날이 생기면 Kaggle 데이터셋에 올려 model_cache 검증을 붙인다.
MODEL = 'Qwen/Qwen3-TTS-12Hz-1.7B-Base'
# 참고 음성: 이전 CustomVoice 모델의 기본 화자 Sohee가 읽은 인사말(실존 인물의 녹음이 아니다). 대본과 음성이 일치해야 한다.
REFERENCES = {'female': (Path(__file__).resolve().parents[1] / 'assets/voice/sohee-reference.flac',
                         '안녕하세요, 좋은 아침이에요! 오늘 알아두면 좋을 학교 소식을 짧게 전해 드릴게요.')}

VOICES = {'female': 'Sohee', 'male': 'Aiden'}
VOICE_NAMES = {'female': '여자 · Sohee (한국어)', 'male': '남자 · Aiden'}
MODE = 'slm-qwen3-tts'
# Bump when model/version/normalization or generation parameters change.
CACHE_VERSION = 'qwen-tts-0.3.0-1.7b-base-clone-sohee-seeded-normalized-v6'
GENERATION = dict(max_new_tokens=2048, do_sample=True, subtalker_dosample=True)
SEED = 20261007
AUDIO_POSTPROCESS = dict(target_lufs=-19, true_peak_db=-2, loudness_range=7,
                         trim_start_duration_sec=.05, trim_end_duration_sec=.1,
                         trim_start_threshold_db=-55, trim_end_threshold_db=-50,
                         preserved_start_silence_sec=.05, preserved_end_silence_sec=.08,
                         # 구간 끝에 붙이는 쉼. 인사→날씨→공지가 붙어서 들려 0.18초에서 0.25초 늘렸다(남겨 둔 0.08초와 합쳐 약 0.5초).
                         added_tail_silence_sec=.43,
                         # 구간이 툭 시작하고 툭 끝나지 않게 양 끝의 소리 크기를 짧게 올리고 내린다(말소리에 흔히 쓰는 범위).
                         fade_in_sec=.02, fade_out_sec=.10,
                         # loudnorm은 처리 방식에 따라 출력 표본화율이 달라진다(24kHz 또는 48kHz).
                         # 구간마다 달라지면 이어 붙인 MP3가 브라우저에서 경계에서 끊기므로 모델 출력과 같은 값으로 고정한다.
                         sample_rate=24000)
CACHE_PROFILE = dict(sampling=GENERATION, seed=SEED, postprocess=AUDIO_POSTPROCESS)


def gpu_count():
    try:
        import torch
    except ImportError:
        return 0
    return torch.cuda.device_count()


def cached_model_source(model, cache_root):
    """Use an already-downloaded HF snapshot directly, including offline builds."""
    dataset_path = os.environ.get('KNU_TTS_MODEL_PATH')
    if dataset_path:
        if model != DATASET_MODEL:
            raise ValueError('연결된 모델과 요청한 음성 모델이 다릅니다.')
        print('Kaggle에 저장된 음성 모델을 검증합니다. 다운로드하지 않습니다.', flush=True)
        return verify_model_directory(dataset_path)
    repository = 'models--' + model.replace('/', '--')
    repo_cache = Path(cache_root) / 'hub' / repository
    ref = repo_cache / 'refs' / 'main'
    if ref.is_file():
        revision = ref.read_text(encoding='utf-8').strip()
        snapshot = repo_cache / 'snapshots' / revision if re.fullmatch(r'[0-9a-f]{40}', revision) else None
        required = ('config.json', 'model.safetensors', 'tokenizer_config.json', 'vocab.json', 'merges.txt',
                    'speech_tokenizer/config.json', 'speech_tokenizer/model.safetensors')
        if snapshot and all((snapshot / name).is_file() for name in required):
            return str(snapshot)
    return model


def _audio_filters(tempo):
    profile = AUDIO_POSTPROCESS
    trim_edges = (f'silenceremove=start_periods=1:start_duration={profile["trim_start_duration_sec"]}:'
                  f'start_threshold={profile["trim_start_threshold_db"]}dB:'
                  f'start_silence={profile["preserved_start_silence_sec"]},areverse,'
                  f'silenceremove=start_periods=1:start_duration={profile["trim_end_duration_sec"]}:'
                  f'start_threshold={profile["trim_end_threshold_db"]}dB:'
                  f'start_silence={profile["preserved_end_silence_sec"]},'
                  # 뒤집힌 상태에서 앞을 올리면, 다시 뒤집었을 때 끝이 서서히 작아진다.
                  f'afade=t=in:st=0:d={profile["fade_out_sec"]},areverse,'
                  f'afade=t=in:st=0:d={profile["fade_in_sec"]}')
    return f'atempo={tempo},{trim_edges},apad=pad_dur={profile["added_tail_silence_sec"]}'


@contextmanager
def seeded_rng(torch, runtime_device):
    devices = [0] if runtime_device == 'cuda:0' else []
    with torch.random.fork_rng(devices=devices):
        torch.manual_seed(SEED)
        if devices:
            torch.cuda.manual_seed_all(SEED)
        yield


def normalize_audio(wav, mp3, tempo, *, runner=subprocess.run):
    """음량을 측정한 뒤 모든 구간에 같은 방식(고정 증폭 + 피크 리미터)으로 목표 음량에 맞춘다."""
    base = _audio_filters(tempo)
    target = 'I=-19:TP=-2:LRA=7'
    measurement = runner(
        ['ffmpeg', '-nostdin', '-v', 'info', '-i', str(wav), '-af', f'{base},loudnorm={target}:print_format=json',
         '-f', 'null', '-'], check=True, timeout=180, capture_output=True, text=True)
    matches = re.findall(r'\{\s*"input_i".*?\}', measurement.stderr, flags=re.S)
    if not matches:
        raise RuntimeError('FFmpeg 음량 측정 결과를 읽지 못했습니다.')
    stats = json.loads(matches[-1])
    required = ('input_i', 'input_tp')
    if any(stats.get(key) in (None, '-inf', 'inf', 'nan') for key in required):
        raise RuntimeError('음성 구간의 음량을 안정적으로 측정하지 못했습니다.')
    # loudnorm 2차 처리는 구간에 따라 전체 음량만 올리거나(선형) 음량을 실시간으로 조절해(동적)
    # 구간마다 소리 느낌과 표본화율이 달라졌다. 모든 구간에 같은 처리를 한다:
    # 목표 음량까지 한 번에 올리고, 목표 최대치를 넘는 순간 피크만 리미터로 누른다.
    profile = AUDIO_POSTPROCESS
    gain = max(-20.0, min(20.0, profile['target_lufs'] - float(stats['input_i'])))
    ceiling = 10 ** (profile['true_peak_db'] / 20)
    second_pass = f'{base},volume={gain:.2f}dB,alimiter=limit={ceiling:.4f}:level=0'
    runner(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(wav), '-af', second_pass,
            '-ar', str(profile['sample_rate']), '-codec:a', 'libmp3lame', '-b:a', '96k', str(mp3)],
           check=True, timeout=180, capture_output=True)


class QwenTTS:
    def __init__(self, *, device='auto', instructions=None):
        if device not in {'auto', 'cpu', 'cuda:0'}:
            raise ValueError('tts.device는 auto, cpu, cuda:0 중 하나여야 합니다.')
        self.device = device
        # Base 모델은 말투 지시문을 받지 않는다. 호출하는 쪽과의 호환을 위해 인자만 받는다.
        self.instructions = instructions or {}
        self.runtime_device = None
        self.model = None
        self.loaded_id = None
        self.prompts = {}

    def verify(self, voice, role, model):
        if model != MODEL or VOICES.get(role) != voice or role not in REFERENCES:
            raise ValueError('Qwen3-TTS 1.7B Base와 참고 음성이 있는 목소리(female)를 사용하세요.')
        if not REFERENCES[role][0].is_file():
            raise RuntimeError('참고 음성 파일이 없습니다: ' + str(REFERENCES[role][0]))
        if not shutil.which('ffmpeg'):
            raise RuntimeError('MP3 변환용 ffmpeg가 필요합니다. START-HERE.md를 확인하세요.')

    def _load(self, model):
        if self.model is not None:
            if self.loaded_id != model:
                raise ValueError('한 실행에서 TTS 모델을 혼용할 수 없습니다.')
            return
        cache_root = Path(__file__).resolve().parents[1] / '.cache'
        cache_root.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault('HF_HOME', str(cache_root / 'huggingface'))
        # Numba-backed librosa helpers in qwen-tts require a writable cache path
        # on some Python/macOS environments; keep it with the model cache.
        os.environ.setdefault('NUMBA_CACHE_DIR', str(cache_root / 'numba'))
        Path(os.environ['NUMBA_CACHE_DIR']).mkdir(parents=True, exist_ok=True)
        try:
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:
            raise RuntimeError('Qwen3-TTS 환경이 필요합니다. START-HERE.md대로 새 환경에 requirements-tts.txt를 설치하세요.') from exc
        device = self.device
        if device == 'auto':
            # CPU is the portable fallback, including macOS. CUDA uses GPU if present.
            device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        if device == 'cuda:0' and not torch.cuda.is_available():
            raise RuntimeError('CUDA GPU가 없습니다. tts.device를 auto 또는 cpu로 설정하세요.')
        print(f'Qwen3-TTS 모델 준비: {model} ({device})', flush=True)
        self.model = Qwen3TTSModel.from_pretrained(
            cached_model_source(model, cache_root / 'huggingface'), device_map=device,
            dtype=torch.bfloat16 if device.startswith('cuda') and torch.cuda.is_bf16_supported()
            else torch.float16 if device.startswith('cuda') else torch.float32,
            attn_implementation='eager',
        )
        self.runtime_device = device
        self.loaded_id = model
        languages = {s.lower() for s in self.model.get_supported_languages() or []}
        if 'korean' not in languages:
            self.model = None
            self.loaded_id = None
            raise RuntimeError('설치된 모델이 한국어를 지원하지 않습니다.')

    def _prompt(self, role):
        """참고 음성은 한 번만 분석해 두고 모든 구간에 같은 목소리로 쓴다."""
        if role not in self.prompts:
            import soundfile as sf
            path, text = REFERENCES[role]
            audio, rate = sf.read(str(path), dtype='float32')
            self.prompts[role] = self.model.create_voice_clone_prompt(ref_audio=(audio, rate), ref_text=text)
        return self.prompts[role]

    def synthesize(self, text, voice, model, tempo):
        role = next((name for name, speaker in VOICES.items() if speaker == voice), None)
        if role not in REFERENCES or model != MODEL:
            raise ValueError('지원하지 않는 Qwen3-TTS 모델/화자입니다.')
        if not isinstance(tempo, (int, float)) or not math.isfinite(tempo) or not .5 <= tempo <= 2:
            raise ValueError('합성 속도는 0.5~2 사이여야 합니다.')
        self._load(model)
        import numpy as np
        import soundfile as sf
        import torch
        # Re-seed every segment inside a forked RNG scope: identical inputs remain
        # reproducible, and model sampling cannot perturb the build's other RNG use.
        with seeded_rng(torch, self.runtime_device):
            with torch.inference_mode():
                wavs, sr = self.model.generate_voice_clone(
                    text=qwen_spoken_text(text), language='Korean', voice_clone_prompt=self._prompt(role), **GENERATION)
        if len(wavs) != 1 or sr <= 0:
            raise RuntimeError('Qwen3-TTS가 유효한 음성을 반환하지 않았습니다.')
        wave = np.asarray(wavs[0])
        if wave.ndim != 1 or wave.size == 0 or not np.isfinite(wave).all() or np.max(np.abs(wave)) == 0:
            raise RuntimeError('빈 음성 또는 잘못된 음성 데이터입니다.')
        # 12 Hz codec: hitting the generation cap may silently cut the script.
        # Refuse to publish an output near the cap instead of accepting a clipped notice.
        if wave.size / sr >= (GENERATION['max_new_tokens'] - 4) / 12.5:
            raise RuntimeError('음성이 생성 길이 상한에 도달했습니다. 대본을 더 짧은 구간으로 나눠 확인하세요.')
        with tempfile.TemporaryDirectory() as td:
            wav, mp3 = Path(td)/'voice.wav', Path(td)/'voice.mp3'
            sf.write(wav, wave, sr, subtype='PCM_16')
            normalize_audio(wav, mp3, tempo)
            return mp3.read_bytes()
