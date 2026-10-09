from types import SimpleNamespace

from briefing import app_export
from briefing.qwen_tts import AUDIO_POSTPROCESS, CACHE_PROFILE, _audio_filters, normalize_audio


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


def test_every_clip_gets_the_same_kind_of_loudness_processing(tmp_path):
    def chain(input_i):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(stderr='{"input_i": "%s", "input_tp": "-1.0", "input_lra": "12", "input_thresh": "-30", "target_offset": "0.1"}' % input_i)
        normalize_audio(tmp_path / 'in.wav', tmp_path / 'out.mp3', 1.0, runner=runner)
        return calls[-1][calls[-1].index('-af') + 1]
    quiet, loud = chain('-27.5'), chain('-14.0')
    # 음량 폭(LRA)이 크거나 피크가 높은 구간도 loudnorm 동적 처리로 빠지지 않고 같은 사슬을 탄다.
    for filters in (quiet, loud):
        assert 'loudnorm' not in filters and filters.endswith('alimiter=limit=0.7943:level=0')
    assert 'volume=8.50dB' in quiet and 'volume=-5.00dB' in loud
    assert 'volume=20.00dB' in chain('-70')  # 거의 무음인 구간을 과하게 키우지 않는다


def test_clip_edges_fade_in_and_out_before_the_pause_is_added():
    filters = _audio_filters(1.0).split(',')
    # 끝 페이드는 뒤집힌 상태에서 걸고, 시작 페이드는 다시 뒤집은 뒤에 건다. 쉼(무음)은 맨 마지막에 붙는다.
    assert filters[-5:] == [filters[-5], 'afade=t=in:st=0:d=0.1', 'areverse', 'afade=t=in:st=0:d=0.02', 'apad=pad_dur=0.43']
    assert filters[-5].startswith('silenceremove=')
    assert (AUDIO_POSTPROCESS['fade_in_sec'], AUDIO_POSTPROCESS['fade_out_sec'], AUDIO_POSTPROCESS['added_tail_silence_sec']) == (.02, .10, .43)

