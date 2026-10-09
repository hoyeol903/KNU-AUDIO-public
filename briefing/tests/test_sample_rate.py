from types import SimpleNamespace

from briefing import app_export
from briefing.qwen_tts import AUDIO_POSTPROCESS, CACHE_PROFILE, normalize_audio


def test_every_clip_is_encoded_at_the_same_sample_rate(tmp_path):
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stderr='{"input_i": "-20", "input_tp": "-3", "input_lra": "4", "input_thresh": "-30", "target_offset": "0.1"}')
    normalize_audio(tmp_path / 'in.wav', tmp_path / 'out.mp3', 1.0, runner=runner)
    encode = calls[-1]
    assert encode[encode.index('-ar') + 1] == '24000' == str(AUDIO_POSTPROCESS['sample_rate'])
    assert CACHE_PROFILE['postprocess']['sample_rate'] == 24000  # 설정이 바뀌면 음성 캐시 키도 바뀐다


def test_concat_reencodes_only_when_sample_rates_differ(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(app_export.shutil, 'which', lambda name: '/usr/bin/ffmpeg')
    monkeypatch.setattr(app_export.subprocess, 'run', lambda command, check: commands.append(command))
    rates = {'a.mp3': 24000, 'b.mp3': 24000, 'c.mp3': 48000}
    monkeypatch.setattr(app_export, 'MP3', lambda path: SimpleNamespace(info=SimpleNamespace(sample_rate=rates[path.rsplit('/', 1)[-1]])))
    app_export.ffmpeg_concat([tmp_path / 'a.mp3', tmp_path / 'b.mp3'], tmp_path / 'same.mp3')
    app_export.ffmpeg_concat([tmp_path / 'a.mp3', tmp_path / 'c.mp3'], tmp_path / 'mixed.mp3')
    assert commands[0][-3:-1] == ['-c', 'copy']
    assert 'libmp3lame' in commands[1] and commands[1][commands[1].index('-ar') + 1] == '24000'
