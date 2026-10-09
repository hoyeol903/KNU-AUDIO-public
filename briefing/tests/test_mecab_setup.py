import sys
from types import SimpleNamespace
import pytest
from briefing.open_tts import prepare_mecab_dictionary


def make_dictionary(path):
    path.mkdir()
    for name in ('mecabrc', 'dicrc', 'sys.dic', 'unk.dic', 'matrix.bin', 'char.bin'):
        (path / name).write_bytes(b'test')


def test_missing_full_dictionary_uses_installed_lite(tmp_path, monkeypatch):
    lite = tmp_path / 'lite'; make_dictionary(lite)
    full = SimpleNamespace(DICDIR=str(tmp_path / 'missing'))
    monkeypatch.setitem(sys.modules, 'unidic', full)
    monkeypatch.setitem(sys.modules, 'unidic_lite', SimpleNamespace(DICDIR=str(lite)))
    assert prepare_mecab_dictionary() == str(lite)
    assert full.DICDIR == str(lite)


def test_complete_full_dictionary_is_preserved(tmp_path, monkeypatch):
    full = tmp_path / 'full'; make_dictionary(full)
    monkeypatch.setitem(sys.modules, 'unidic', SimpleNamespace(DICDIR=str(full)))
    monkeypatch.setitem(sys.modules, 'unidic_lite', None)
    assert prepare_mecab_dictionary() == str(full)


def test_incomplete_dictionaries_fail_with_action(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'unidic', SimpleNamespace(DICDIR=str(tmp_path/'full')))
    monkeypatch.setitem(sys.modules, 'unidic_lite', SimpleNamespace(DICDIR=str(tmp_path/'lite')))
    with pytest.raises(RuntimeError, match='python -m unidic download'):
        prepare_mecab_dictionary()


def test_tls_uses_ca_bundle_without_disabling_verification(monkeypatch):
    from briefing import open_tts as t
    monkeypatch.setattr(t.importlib.util, 'find_spec', lambda name: object())
    fake_nltk = SimpleNamespace(data=SimpleNamespace(path=[], find=lambda path: path))
    monkeypatch.setitem(sys.modules, 'nltk', fake_nltk)
    monkeypatch.setitem(sys.modules, 'certifi', SimpleNamespace(where=lambda: '/test/trusted-ca.pem'))
    monkeypatch.delenv('SSL_CERT_FILE', raising=False)
    monkeypatch.setattr(t.ssl, 'get_default_verify_paths', lambda: SimpleNamespace(cafile=None))
    original = t.ssl._create_default_https_context
    t.prepare_language_resources()
    assert t.os.environ['SSL_CERT_FILE'] == '/test/trusted-ca.pem'
    assert t.ssl._create_default_https_context is original
    monkeypatch.setenv('SSL_CERT_FILE', '/custom/ca.pem')
    t.prepare_language_resources()
    assert t.os.environ['SSL_CERT_FILE'] == '/custom/ca.pem'


def test_spoken_addresses_and_decimal_temperature():
    from briefing.open_tts import spoken_text
    original='11.1도, 22.7도. aicoss@knu.ac.kr (https://pf.kakao.com/_xiacMn)'
    result=spoken_text(original)
    assert '11점1도' in result and '22점7도' in result
    assert '@' not in result and 'https://' not in result
    assert '골뱅이' in result and '화면의 원문 링크' in result
    assert spoken_text(result) == result
    assert spoken_text('2026. 10. 6. 마감') == '2026. 10. 6. 마감'


def test_spoken_dates_times_and_known_acronyms_are_stable():
    from briefing.open_tts import qwen_spoken_text, spoken_text
    assert qwen_spoken_text('2026-10-06 09:05, 19:00 KNU AI PDF') == \
        '2026년 10월 6일 9시 5분, 19시 케이엔유 에이아이 피디에프'
    normalized = qwen_spoken_text('2026. 10. 6. 09:00 WFK')
    assert normalized == '2026년 10월 6일. 9시 더블유에프케이'
    assert qwen_spoken_text(normalized) == normalized
    assert spoken_text('2026. 10. 6. 09:00 KNU') == '2026. 10. 6. 09:00 KNU'
