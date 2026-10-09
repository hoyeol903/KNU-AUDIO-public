import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from briefing import daily
from collector.store import save_json


@pytest.fixture
def data():
    return json.loads((daily.ROOT/'data/raw/2026-10-03/items.json').read_text())


def test_retry_reuses_input_without_losing_notices(tmp_path, data):
    path=tmp_path/'data/raw/2026-10-03/items.json'
    save_json(data,path)
    runner=Mock()
    assert daily.collect_day(root=tmp_path,day=data['date'],runner=runner)==path
    runner.assert_not_called()
    assert json.loads(path.read_text()) == data


def test_missing_today_collects_meals_and_all_departments(tmp_path, data):
    def run(command, **kwargs):
        assert '--all-supported' in command and '--skip-meals' not in command
        save_json(data,tmp_path/'data/raw'/data['date']/'items.json')
        return SimpleNamespace(returncode=1) # explicit partial errors remain visible
    result=daily.collect_day(root=tmp_path,day=data['date'],runner=run)
    assert result.exists()
    report=json.loads((tmp_path/'output/daily-collection.json').read_text())
    assert report['errors'] == data['errors'] and not report['reused']


def test_stale_input_is_never_published(tmp_path, data):
    path=tmp_path/'items.json';save_json(data,path)
    with pytest.raises(ValueError,match='날짜'):
        daily.validate_input(path,'2026-10-04')


def test_missing_output_stops_pipeline(tmp_path):
    with pytest.raises(RuntimeError,match='결과 파일'):
        daily.collect_day(root=tmp_path,day='2026-10-04',runner=lambda *a,**kw:SimpleNamespace(returncode=1))


def test_publication_rejects_preview_and_missing_audio(tmp_path):
    manifest=dict(date='2026-10-04',mode='text-only',segments=[],voices={'kr':{} })
    save_json(manifest,tmp_path/'manifest.json')
    with pytest.raises(ValueError,match='완료본'):
        daily.verify_publication(tmp_path,'2026-10-04')
    manifest.update(mode='slm-qwen3-tts',voices={'female':{}, 'male':{}},
                    segments=[dict(generation='fixed',audio={'female':{'url':'audio/missing.mp3'}})])
    save_json(manifest,tmp_path/'manifest.json')
    with pytest.raises(ValueError,match='음성 파일'):
        daily.verify_publication(tmp_path,'2026-10-04')


def test_total_collection_failure_keeps_previous_site(tmp_path, data):
    data['weather'] = dict(summary=None, temp_min=None, temp_max=None, rain_prob=None)
    data['schedule'] = []
    for channel in data['channels']:
        channel['notices'] = []
        channel['meals'] = []
    data['errors'] = [dict(source='weather', message='unavailable')]
    path = tmp_path/'items.json'
    save_json(data, path)
    with pytest.raises(ValueError, match='기존 배포'):
        daily.validate_input(path, data['date'])


def test_publication_accepts_unchecked_revision(tmp_path, monkeypatch):
    import mutagen.mp3
    monkeypatch.setattr(mutagen.mp3, 'MP3', lambda path: SimpleNamespace(info=SimpleNamespace(length=1)))
    (tmp_path/'audio').mkdir()
    (tmp_path/'audio/one.mp3').write_bytes(b'audio')
    for name in ('index.html', 'app.mjs', 'continuous-audio.mjs', 'playlist.mjs', 'playback-speed.mjs', 'style.css'):
        (tmp_path/name).write_text('test')
    row = dict(generation='slm', review=dict(passed=None, status='revision-unchecked'),
               audio={'female': {'url': 'audio/one.mp3'}})
    manifest = dict(date='2026-10-08', mode='slm-qwen3-tts', voices={'female': {}}, segments=[row])
    save_json(manifest, tmp_path/'manifest.json')
    daily.verify_publication(tmp_path, '2026-10-08')
    row['review'] = dict(passed=False)
    save_json(manifest, tmp_path/'manifest.json')
    with pytest.raises(ValueError, match='검수'):
        daily.verify_publication(tmp_path, '2026-10-08')
