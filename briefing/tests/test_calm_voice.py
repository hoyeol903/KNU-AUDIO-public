from briefing.build import read_yaml, ROOT
from briefing.open_tts import qwen_spoken_text
from briefing.qwen_tts import AUDIO_POSTPROCESS, GENERATION, _audio_filters


def test_sampling_is_narrower_than_library_defaults_for_both_token_stages():
    # 라이브러리 기본값: temperature 0.9, top_k 50, top_p 1.0
    for prefix in ('', 'subtalker_'):
        assert GENERATION[prefix + 'temperature'] < 0.9
        assert GENERATION[prefix + 'top_k'] < 50 and GENERATION[prefix + 'top_p'] < 1.0
    assert GENERATION['do_sample'] is True  # 완전히 끄면 반복·단조로움 위험이 있어 범위만 좁힌다


def test_exclamation_marks_are_softened_only_in_the_spoken_text():
    assert qwen_spoken_text('안녕하세요, 좋은 아침이에요! 오늘도 좋은 하루 보내세요!!') == '안녕하세요, 좋은 아침이에요. 오늘도 좋은 하루 보내세요.'
    assert qwen_spoken_text('신청하셨나요?') == '신청하셨나요?'


def test_loud_peaks_are_compressed_after_trimming_and_before_the_tail_pad():
    filters = _audio_filters(1.0).split(',')
    compressor = next(i for i, part in enumerate(filters) if part.startswith('acompressor='))
    assert f"threshold={AUDIO_POSTPROCESS['compress_threshold_db']}dB" in filters[compressor]
    assert filters[0] == 'atempo=1.0' and filters[-1].startswith('apad=') and compressor == len(filters) - 2


def test_voice_instruction_asks_for_a_steady_calm_delivery():
    instruction = read_yaml(ROOT / 'config/briefing.yaml')['tts']['instructions']['female']
    assert '같은 속도' in instruction and '생기' not in instruction
