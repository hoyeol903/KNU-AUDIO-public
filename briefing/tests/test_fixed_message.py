import json

import pytest
import requests
import yaml

from briefing.fixed_message import sync_config, validate_message


class Response:
    def __init__(self, payload):
        self.raw = json.dumps(payload, ensure_ascii=False).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, size): yield self.raw


def fixture(tmp_path):
    (tmp_path / 'config').mkdir()
    path = tmp_path / 'config/briefing.yaml'
    path.write_text('fixed_message: 기본 멘트\ngreeting: 기존 인사\n', encoding='utf-8')
    published = tmp_path / 'output/app/data/briefing'
    published.mkdir(parents=True)
    (published / 'segments.json').write_text(json.dumps({'segments': [{'id': 'message', 'script': '마지막 적용 멘트'}]}))
    return path


def test_saved_message_overrides_only_fixed_text(tmp_path):
    path = fixture(tmp_path)
    def get(url, **kwargs):
        assert kwargs == {'timeout': (5, 15), 'stream': True}
        return Response({'text': ' 새로운 응원 멘트 ', 'updatedAt': 10})
    assert sync_config(tmp_path, get=get, report=lambda _: None) == '새로운 응원 멘트'
    assert yaml.safe_load(path.read_text()) == {'fixed_message': '새로운 응원 멘트', 'greeting': '기존 인사'}


@pytest.mark.parametrize('payload', [{}, {'text': ''}, {'text': 1}, {'text': '가' * 501}, {'text': '가' * 9000}])
def test_invalid_response_preserves_last_broadcast_and_reports(tmp_path, payload):
    fixture(tmp_path)
    reports = []
    assert sync_config(tmp_path, get=lambda *a, **k: Response(payload), report=reports.append) == '마지막 적용 멘트'
    assert reports and '::warning::' in reports[-1]


def test_network_failure_uses_previous_broadcast_not_old_default(tmp_path):
    fixture(tmp_path)
    def unavailable(*args, **kwargs): raise requests.Timeout('서버 지연')
    assert sync_config(tmp_path, get=unavailable, report=lambda _: None) == '마지막 적용 멘트'


def test_first_run_keeps_default_if_server_unavailable(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'output/app/data/briefing/segments.json').unlink()
    def unavailable(*args, **kwargs): raise requests.HTTPError('404')
    assert sync_config(tmp_path, get=unavailable, report=lambda _: None) == '기본 멘트'


@pytest.mark.parametrize('value', [None, '', ' ', 123, '가' * 501, 'a\x00b'])
def test_invalid_fixed_text(value):
    with pytest.raises(ValueError): validate_message(value)
