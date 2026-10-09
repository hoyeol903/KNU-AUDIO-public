from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
import pytest
np = pytest.importorskip('numpy', reason='음성 테스트는 requirements-tts.txt 설치가 필요합니다')
from briefing.qwen_tts import (QwenTTS, MODEL, VOICES, CACHE_PROFILE, CACHE_VERSION,
                               cached_model_source, normalize_audio, seeded_rng)
from briefing import build as b


def test_roles_and_model_are_checked_before_generation(monkeypatch):
    monkeypatch.setattr('briefing.qwen_tts.shutil.which', lambda name: '/bin/ffmpeg')
    tts=QwenTTS()
    for role, speaker in VOICES.items(): tts.verify(speaker, role, MODEL)
    with pytest.raises(ValueError): tts.verify('Sohee', 'male', MODEL)
    with pytest.raises(ValueError): tts.verify('Aiden', 'male', 'old-model')
    with pytest.raises(ValueError): QwenTTS(device='invented')


def test_cpu_loads_once_and_checks_korean_speakers(monkeypatch):
    factory=Mock()
    factory.from_pretrained.return_value=SimpleNamespace(
        get_supported_speakers=lambda:['sohee','aiden'], get_supported_languages=lambda:['Korean'])
    torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:False), float32='float32')
    monkeypatch.setitem(sys.modules,'torch',torch)
    monkeypatch.setitem(sys.modules,'qwen_tts',SimpleNamespace(Qwen3TTSModel=factory))
    monkeypatch.setattr('briefing.qwen_tts.cached_model_source', lambda model, cache_root: model)
    tts=QwenTTS()
    tts._load(MODEL);tts._load(MODEL)
    factory.from_pretrained.assert_called_once_with(MODEL, device_map='cpu',dtype='float32',attn_implementation='eager')
    with pytest.raises(ValueError):tts._load('different')


def test_cached_huggingface_snapshot_is_used_without_network(tmp_path):
    repo = tmp_path / 'hub' / ('models--' + MODEL.replace('/', '--'))
    revision = 'a' * 40
    snapshot = repo / 'snapshots' / revision
    snapshot.mkdir(parents=True)
    (repo / 'refs').mkdir()
    (repo / 'refs' / 'main').write_text(revision + '\n')
    for name in ('config.json', 'model.safetensors', 'tokenizer_config.json', 'vocab.json', 'merges.txt',
                 'speech_tokenizer/config.json', 'speech_tokenizer/model.safetensors'):
        path = snapshot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'test')
    assert cached_model_source(MODEL, tmp_path) == str(snapshot)
    assert cached_model_source('Qwen/Not-Cached', tmp_path) == 'Qwen/Not-Cached'


def test_missing_korean_support_is_an_error(monkeypatch):
    factory=Mock();factory.from_pretrained.return_value=SimpleNamespace(
        get_supported_speakers=lambda:['sohee','aiden'],get_supported_languages=lambda:['English'])
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:False),float32='float32'))
    monkeypatch.setitem(sys.modules,'qwen_tts',SimpleNamespace(Qwen3TTSModel=factory))
    with pytest.raises(RuntimeError,match='한국어'):QwenTTS()._load(MODEL)


def test_new_provider_cannot_reuse_old_melo_audio():
    config=b.read_yaml(b.ROOT/'config/briefing.yaml')
    assert b.audio_key('좋은 아침이에요','Sohee',config) != b.audio_key('좋은 아침이에요','Aiden',config)
    config2=dict(config,model='other-revision')
    assert b.audio_key('좋은 아침이에요','Sohee',config) != b.audio_key('좋은 아침이에요','Sohee',config2)
    config3={**config,'tts':{**config['tts'],'instructions':{
        **config['tts']['instructions'],'female':'다른 지시 문장'}}}
    assert b.audio_key('좋은 아침이에요','Sohee',config) != b.audio_key('좋은 아침이에요','Sohee',config3)
    assert '1.7b' in CACHE_VERSION


def test_custom_voice_receives_per_speaker_instruction(monkeypatch, tmp_path):
    torch = pytest.importorskip('torch')
    instruction='차분하고 또렷한 아침 라디오 진행자처럼 말해 주세요.'
    model=Mock()
    model.generate_custom_voice.return_value=([np.full(2400,.05,dtype=np.float32)],24000)
    tts=QwenTTS(instructions={'female':instruction})
    tts.model=model; tts.loaded_id=MODEL; tts.runtime_device='cpu'
    monkeypatch.setattr('briefing.qwen_tts.normalize_audio',
                        lambda wav, mp3, tempo: Path(mp3).write_bytes(b'mp3'))
    assert tts.synthesize('좋은 아침이에요','Sohee',MODEL,1.0)==b'mp3'
    assert model.generate_custom_voice.call_args.kwargs['instruct']==instruction
    assert model.generate_custom_voice.call_args.kwargs['speaker']=='Sohee'
    assert tts.synthesize('좋은 아침이에요','Aiden',MODEL,1.0)==b'mp3'
    assert model.generate_custom_voice.call_args.kwargs['instruct'] is None


def test_config_selects_17b_and_requires_female_instruction():
    config=b.read_yaml(b.ROOT/'config/briefing.yaml')
    b.validate_config(config,[])
    config['tts']['instructions']['female']=' '
    with pytest.raises(ValueError,match='instructions.female'):
        b.validate_config(config,[])


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='FFmpeg is needed to measure audio normalization')
def test_postprocess_normalizes_quiet_and_loud_segments_and_adds_same_pause(tmp_path):
    sample_rate = 24000
    durations = []
    measured_loudness = []
    for name, amplitude in [('quiet', .025), ('loud', .25)]:
        source = tmp_path / f'{name}.wav'
        target = tmp_path / f'{name}.mp3'
        samples = (amplitude * np.sin(2 * np.pi * 220 * np.arange(sample_rate * 2) / sample_rate)).astype(np.float32)
        import soundfile as sf
        sf.write(source, samples, sample_rate, subtype='PCM_16')
        normalize_audio(source, target, 1.0)
        probe = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(target),
                                '-af', 'loudnorm=I=-19:TP=-2:LRA=7:print_format=json',
                                '-f', 'null', '-'], check=True, capture_output=True, text=True)
        stats = json.loads(re.findall(r'\{\s*"input_i".*?\}', probe.stderr, flags=re.S)[-1])
        measured_loudness.append(float(stats['input_i']))
        probe_duration = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                         '-of', 'default=noprint_wrappers=1:nokey=1', str(target)],
                                        check=True, capture_output=True, text=True)
        durations.append(float(probe_duration.stdout))
    assert max(measured_loudness) - min(measured_loudness) <= .8
    assert all(2.15 <= duration <= 2.4 for duration in durations)
    assert abs(durations[0] - durations[1]) <= .03


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='FFmpeg is needed to inspect silence handling')
def test_postprocess_trims_only_edge_silence_and_keeps_phrase_pause(tmp_path):
    import soundfile as sf
    rate = 24000
    tone = .08 * np.sin(2 * np.pi * 220 * np.arange(rate * 8 // 10) / rate)
    silence = np.zeros(rate // 5)
    source = tmp_path / 'phrase.wav'
    target = tmp_path / 'phrase.mp3'
    sf.write(source, np.concatenate([tone, silence, tone, np.zeros(rate * 3 // 10)]), rate, subtype='PCM_16')
    normalize_audio(source, target, 1.0)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'default=noprint_wrappers=1:nokey=1', str(target)],
                           check=True, capture_output=True, text=True)
    duration = float(probe.stdout)
    silence_probe = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(target),
                                    '-af', 'silencedetect=noise=-50dB:d=0.08', '-f', 'null', '-'],
                                   check=True, capture_output=True, text=True)
    silence_durations = [float(value) for value in re.findall(r'silence_duration: ([0-9.]+)', silence_probe.stderr)]
    assert 1.9 <= duration <= 2.05
    assert any(.17 <= length <= .23 for length in silence_durations)


def test_audio_profile_includes_seed_and_quality_settings():
    assert CACHE_PROFILE['seed'] == 20261007
    assert CACHE_PROFILE['sampling']['do_sample'] is True
    assert CACHE_PROFILE['sampling']['subtalker_dosample'] is True
    assert CACHE_PROFILE['postprocess']['target_lufs'] == -19
    assert CACHE_PROFILE['postprocess']['added_tail_silence_sec'] == .18


def test_each_generation_uses_repeatable_seed_without_changing_host_rng():
    torch = pytest.importorskip('torch')
    torch.manual_seed(123)
    expected_next = torch.rand(1)
    torch.manual_seed(123)
    with seeded_rng(torch, 'cpu'):
        first = torch.rand(8)
    actual_next = torch.rand(1)
    with seeded_rng(torch, 'cpu'):
        second = torch.rand(8)
    assert torch.equal(first, second)
    assert torch.equal(actual_next, expected_next)
