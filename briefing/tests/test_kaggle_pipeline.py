import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from briefing import kaggle


DAY = '2026-10-05'
STARTED = '2026-10-05T07:00:00+09:00'


def _collection(root, *, meta_day=DAY, item_day=DAY, collected_at='2026-10-05T07:00:01+09:00'):
    (root / 'output/app/data').mkdir(parents=True)
    (root / 'output/app/data/meta.json').write_text(json.dumps({'asOf': meta_day}))
    items = dict(date=item_day, collected_at=collected_at, errors=['one board failed'], weather={}, channels=[], schedule=[])
    path = root / 'data/raw' / meta_day / 'items.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(items))
    return path


def test_collection_input_accepts_fresh_snapshot_with_partial_errors(tmp_path):
    _collection(tmp_path)
    assert kaggle.collection_input(tmp_path, STARTED) == DAY


def test_collection_input_skips_same_briefing_material_despite_timestamp_and_errors(tmp_path):
    path = _collection(tmp_path)
    current = json.loads(path.read_text())
    current['channels'] = [{'channel_id': 'ch', 'notices': [], 'meals': []}]
    current['weather'] = {'summary': '맑음'}
    path.write_text(json.dumps(current))
    previous = dict(current, collected_at='2026-10-05T06:00:00+09:00', errors=[])
    previous_path = tmp_path / 'previous-items.json'
    previous_path.write_text(json.dumps(previous))
    assert kaggle.collection_input(tmp_path, STARTED, previous_path) is None


@pytest.mark.parametrize('field,value', [
    ('date', '2026-10-04'),
    ('weather', {'summary': '맑음'}),
    ('channels', [{'channel_id': 'ch', 'notices': [{'title': '새 공지'}], 'meals': []}]),
    ('channels', [{'channel_id': 'meal', 'notices': [], 'meals': [{'menu': ['새 메뉴']}]}]),
    ('schedule', [{'title': '시험', 'start': '2026-10-06'}]),
])
def test_collection_input_starts_for_new_or_changed_material(tmp_path, field, value):
    path = _collection(tmp_path)
    current = json.loads(path.read_text())
    current.update(weather={}, channels=[], schedule=[])
    if field != 'date':
        current[field] = value
    path.write_text(json.dumps(current))
    previous = dict(current)
    previous[field] = value if field == 'date' else {} if field == 'weather' else []
    previous_path = tmp_path / 'previous-items.json'
    previous_path.write_text(json.dumps(previous))
    assert kaggle.collection_input(tmp_path, STARTED, previous_path) == DAY


def test_collection_input_missing_previous_triggers(tmp_path):
    _collection(tmp_path)
    previous_path = tmp_path / 'previous-items.json'
    assert kaggle.collection_input(tmp_path, STARTED, previous_path) == DAY


def test_collection_input_malformed_previous_fails_clearly(tmp_path):
    _collection(tmp_path)
    previous_path = tmp_path / 'previous-items.json'
    previous_path.write_text('{broken json')
    with pytest.raises(ValueError, match='이전 수집 스냅샷을 읽을 수 없습니다'):
        kaggle.collection_input(tmp_path, STARTED, previous_path)


def test_collection_input_rejects_old_or_mismatched_snapshot(tmp_path):
    input_path = _collection(tmp_path, collected_at='2026-10-05T06:59:59+09:00')
    assert kaggle.collection_input(tmp_path, STARTED) is None
    input_path.unlink()
    assert kaggle.collection_input(tmp_path, STARTED) is None

    other = tmp_path / 'other'
    _collection(other, item_day='2026-10-04')
    with pytest.raises(ValueError, match='날짜가 다릅니다'):
        kaggle.collection_input(other, STARTED)


def _publish_fixture(root):
    input_path = _collection(root)
    expected = dict(day=DAY, input_sha256=kaggle.sha256_file(input_path), run_id='123',
                    run_attempt='1', github_sha='a' * 40, bundle_sha256='b' * 64,
                    kernel_id='muyahoyeol/knu-audio-briefing-123-1', kernel_version=1)
    expected_path = root / 'expected.json'
    expected_path.write_text(json.dumps(expected))
    artifact = root / 'artifact'
    (artifact / 'app').mkdir(parents=True)
    (artifact / 'app/segments.json').write_text(json.dumps(
        {'date': DAY, 'segments': [{'audio': 'clip.mp3'}]}))
    (artifact / 'app/clip.mp3').write_bytes(b'verified audio')
    manifest = dict(**expected, gpu_name='Tesla T4')
    return expected, expected_path, artifact, manifest


def test_publish_checks_freshness_before_replacing_and_records_copied_hashes(tmp_path, monkeypatch):
    expected, expected_path, artifact, manifest = _publish_fixture(tmp_path)
    monkeypatch.setattr(kaggle, 'verify_output', Mock(return_value=manifest))
    target = tmp_path / 'output/app/data/briefing'
    target.mkdir()
    (target / 'stale.mp3').write_bytes(b'old file')

    record = kaggle.publish_output(tmp_path, artifact, expected_path)

    assert sorted(path.name for path in target.iterdir()) == ['clip.mp3', 'segments.json', 'stale.mp3']
    assert record['verified'] and record['kernel_version'] == 1
    assert record['app_file_sha256'] == {
        'clip.mp3': hashlib.sha256(b'verified audio').hexdigest(),
        'segments.json': kaggle.sha256_file(target / 'segments.json'),
    }
    saved = json.loads((tmp_path / f'data/runs/briefing-kaggle-{DAY}.json').read_text())
    assert saved == record and saved['input_sha256'] == expected['input_sha256']


@pytest.mark.parametrize('failure', ['input', 'artifact'])
def test_publish_failure_leaves_existing_result_untouched(tmp_path, monkeypatch, failure):
    expected, expected_path, artifact, manifest = _publish_fixture(tmp_path)
    target = tmp_path / 'output/app/data/briefing'
    target.mkdir()
    (target / 'old.mp3').write_bytes(b'keep')
    (target / 'segments.json').write_text('{"date":"2026-10-04"}')
    if failure == 'input':
        (tmp_path / 'data/raw' / DAY / 'items.json').write_text('{"date":"2026-10-05","changed":true}')
    else:
        monkeypatch.setattr(kaggle, 'verify_output', Mock(side_effect=ValueError('tampered artifact')))
    if failure != 'artifact':
        monkeypatch.setattr(kaggle, 'verify_output', Mock(return_value=manifest))

    with pytest.raises(ValueError):
        kaggle.publish_output(tmp_path, artifact, expected_path)
    assert (target / 'old.mp3').read_bytes() == b'keep'
    assert (target / 'segments.json').read_text() == '{"date":"2026-10-04"}'
    assert not (tmp_path / f'data/runs/briefing-kaggle-{DAY}.json').exists()


def test_publish_copy_failure_preserves_current_manifest(tmp_path, monkeypatch):
    _, expected_path, artifact, manifest = _publish_fixture(tmp_path)
    monkeypatch.setattr(kaggle, 'verify_output', Mock(return_value=manifest))
    target = tmp_path / 'output/app/data/briefing'
    target.mkdir()
    (target / 'segments.json').write_text('{"date":"2026-10-04"}')
    monkeypatch.setattr(kaggle.shutil, 'copy2', Mock(side_effect=OSError('disk full')))

    with pytest.raises(OSError, match='disk full'):
        kaggle.publish_output(tmp_path, artifact, expected_path)
    assert (target / 'segments.json').read_text() == '{"date":"2026-10-04"}'
    assert not (tmp_path / f'data/runs/briefing-kaggle-{DAY}.json').exists()


def test_workflows_keep_kaggle_opt_in_and_publish_serialized():
    collect = yaml.safe_load(Path('.github/workflows/collect.yml').read_text())
    kaggle_workflow = yaml.safe_load(Path('.github/workflows/briefing-kaggle.yml').read_text())
    collect_steps = collect['jobs']['collect']['steps']
    dispatch = next(step for step in collect_steps if step.get('name') == '최신 수집 자료로 Kaggle 브리핑 시작')
    inputs = kaggle_workflow.get('on', kaggle_workflow.get(True))['workflow_dispatch']['inputs']
    publish = kaggle_workflow['jobs']['publish']
    archive = next(step for step in kaggle_workflow['jobs']['kaggle-briefing']['steps']
                   if step.get('id') == 'archive')['with']

    assert collect['permissions']['actions'] == 'write'
    assert "vars.ENABLE_KAGGLE_BRIEFING == 'true'" in dispatch['if']
    assert "steps.collect.outcome == 'failure'" not in dispatch['if']
    assert inputs['publish']['default'] is True and inputs['publish']['type'] == 'boolean'
    assert 'inputs.publish' in publish['if'] and 'github.ref' in publish['if']
    assert publish['permissions'] == {'contents': 'write', 'actions': 'write'}
    assert publish['concurrency']['group'] == 'knu-collector-writer'
    assert archive['include-hidden-files'] is True
    assert set(archive['path'].splitlines()) == {
        '.cache/kaggle/expected.json', '.cache/kaggle/output/briefing-artifacts/**',
        '.cache/kaggle/kaggle-logs.txt', '.cache/kaggle/resume.json', '.cache/kaggle/publish-requested.txt',
    }


def test_publish_accepts_completed_audio_after_collection_moves_to_next_day(tmp_path, monkeypatch):
    _, expected_path, artifact, manifest = _publish_fixture(tmp_path)
    monkeypatch.setattr(kaggle, 'verify_output', Mock(return_value=manifest))
    (tmp_path / 'output/app/data/meta.json').write_text(json.dumps({'asOf': '2026-10-06'}))
    assert kaggle.publish_output(tmp_path, artifact, expected_path)['input_date'] == DAY


@pytest.mark.parametrize('newer_day,newer_run', [('2026-10-06', '100'), (DAY, '124')])
def test_publish_never_overwrites_newer_audio(tmp_path, monkeypatch, newer_day, newer_run):
    _, expected_path, artifact, manifest = _publish_fixture(tmp_path)
    monkeypatch.setattr(kaggle, 'verify_output', Mock(return_value=manifest))
    target = tmp_path / 'output/app/data/briefing'
    target.mkdir()
    original = json.dumps({'date': newer_day, 'segments': [{'audio': 'newer.mp3'}]})
    (target / 'segments.json').write_text(original)
    records = tmp_path / 'data/runs'
    records.mkdir()
    (records / f'briefing-kaggle-{DAY}.json').write_text(json.dumps({'run_id': newer_run, 'run_attempt': '1'}))
    assert kaggle.publish_output(tmp_path, artifact, expected_path)['skipped']
    assert (target / 'segments.json').read_text() == original
    assert not (target / 'clip.mp3').exists()


def test_publish_verifies_original_commit_when_same_day_collection_is_replaced(tmp_path, monkeypatch):
    import subprocess
    expected, expected_path, artifact, manifest = _publish_fixture(tmp_path)
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, capture_output=True, check=True).stdout
    git('init')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    git('add', 'data/raw')
    git('commit', '-m', 'original snapshot')
    sha = git('rev-parse', 'HEAD').decode().strip()
    expected['github_sha'] = sha
    expected_path.write_text(json.dumps(expected))
    monkeypatch.setattr(kaggle, 'verify_output', Mock(return_value=manifest))
    (tmp_path / 'data/raw' / DAY / 'items.json').write_text('{"date":"2026-10-05","new_collection":true}')
    assert kaggle.publish_output(tmp_path, artifact, expected_path)['input_date'] == DAY
    expected['input_sha256'] = '0' * 64
    expected_path.write_text(json.dumps(expected))
    with pytest.raises(ValueError, match='원래 수집 스냅샷'):
        kaggle.publish_output(tmp_path, artifact, expected_path)
