from datetime import datetime
import json
from pathlib import Path
import sys

import pytest
import yaml

from collector import preview, run, store
from collector.store import SEOUL


def test_failed_shared_board_selects_one_physical_channel():
    channels = yaml.safe_load((run.ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    ids = ['notice-b34ee1a00417', 'notice-fefffa32e24c']
    row = dict(source_board_id='knu-computer-sub6_1_a', channel_ids=ids,
               errors=[dict(source=ids[0], message='fixture timeout')], truncated=True)
    selected = run.select_failed_channels(channels, dict(channels=[row]))
    assert len(selected) == 1
    assert run.board_id_for(selected[0]) == 'knu-computer-sub6_1_a'
    assert selected[0]['channel_ids'] == ids


def test_no_failed_boards_returns_without_client_or_output(monkeypatch, tmp_path):
    from collector import preview
    today = datetime.now(SEOUL).date()
    data = tmp_path / 'data'
    (data / 'runs').mkdir(parents=True)
    channels = yaml.safe_load((run.ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    (data / 'channels.yaml').write_text(yaml.safe_dump(channels[:1], allow_unicode=True), encoding='utf-8')
    report_path = data / 'runs' / 'today.json'
    store.save_collection_report(dict(channels=[dict(
        source_board_id='knu-computer-sub6_1_a', channel_id='notice-b34ee1a00417',
        channel_ids=['notice-b34ee1a00417'], started_at=datetime.now(SEOUL).isoformat(),
        errors=[], truncated=False)]), report_path)
    monkeypatch.setattr(run, 'ROOT', tmp_path)
    monkeypatch.setattr(preview, 'ROOT', tmp_path)

    class NoNetwork:
        def __init__(self):
            raise AssertionError('실패 게시판이 없으므로 Client를 만들면 안 됩니다')

    monkeypatch.setattr(run, 'Client', NoNetwork)
    output_report = data / 'runs' / 'result.json'
    monkeypatch.setattr(sys, 'argv', ['collector.run', '--retry-failed', '--write-items',
                                      '--report-path', str(output_report), '--db-path', str(tmp_path / 'notices.json')])
    assert run.main() == 0
    assert report_path.exists() and not output_report.exists()


def test_retry_merges_successful_boards_and_replaces_only_failed_board(monkeypatch, tmp_path):
    from collector import preview
    today = datetime.now(SEOUL).date()
    data = tmp_path / 'data'
    (data / 'runs').mkdir(parents=True)
    original_channels = yaml.safe_load((run.ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    ids = {'school': 'knu-academic', 'chinese': 'notice-6b04da14aae1'}
    channels = [next(c for c in original_channels if c['id'] == channel_id) for channel_id in ids.values()]
    (data / 'channels.yaml').write_text(yaml.safe_dump(channels, allow_unicode=True), encoding='utf-8')
    school = dict(source_board_id=run.board_id_for(channels[0]), channel_id=ids['school'],
                  channel_ids=[ids['school']], started_at=datetime.now(SEOUL).isoformat(),
                  finished_at=datetime.now(SEOUL).isoformat(), errors=[], truncated=False, request_count=4)
    chinese = dict(source_board_id=run.board_id_for(channels[1]), channel_id=ids['chinese'],
                   channel_ids=[ids['chinese']], started_at=datetime.now(SEOUL).isoformat(),
                   finished_at=datetime.now(SEOUL).isoformat(),
                   errors=[dict(source=ids['chinese'], url='https://old/failure', message='old failure')],
                   truncated=True, request_count=3)
    original_report = dict(channels=[school, chinese], request_count=7)
    source_path = data / 'runs' / 'today.json'
    store.save_collection_report(original_report, source_path)
    original_bytes = source_path.read_bytes()
    context_path = data / 'raw' / today.isoformat() / 'context.json'
    context = dict(date=today.isoformat(), collected_at=datetime.now(SEOUL).isoformat(),
                   weather=dict(summary='흐림'), channels=[], schedule=[dict(title='예정')], errors=[],
                   sources=[dict(source='weather', url='fixture'), dict(source='schedule', url='fixture')])
    store.save_collection_report(context, context_path)
    monkeypatch.setattr(run, 'ROOT', tmp_path)
    monkeypatch.setattr(preview, 'ROOT', tmp_path)
    monkeypatch.setattr(run, 'all_required_channels', lambda rows, validation:
                        run.select_channels(rows, list(ids.values()), validation=validation))
    calls = []

    class FakeClient:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def collect(client, channel, **kwargs):
        board = run.board_id_for(channel)
        calls.append(board)
        return dict(source_board_id=board, channel_id=channel['id'],
                    channel_ids=channel['channel_ids'], started_at=datetime.now(SEOUL).isoformat(),
                    finished_at=datetime.now(SEOUL).isoformat(), errors=[], truncated=False,
                    window_complete=True, listed=1, successful=1, new=[], updated=[], unchanged=[],
                    skipped=[], request_count=2, duration_sec=0.1, mode='daily')

    captured = {}
    def build(rows, state, logical, **kwargs):
        captured['ids'] = {channel['id'] for channel in logical}
        captured['reports'] = kwargs['reports'][0]['channels']
        captured['context'] = kwargs['context']
        return dict(date=today.isoformat(), channels=[], weather=context['weather'], schedule=context['schedule'], errors=[])

    monkeypatch.setattr(run, 'Client', FakeClient)
    monkeypatch.setattr(run, 'collect', collect)
    monkeypatch.setattr(run, 'build_items', build)
    monkeypatch.setattr(run, 'save_daily_items', lambda items, path: Path(path).write_text(json.dumps(items)))
    output_report = data / 'runs' / 'retry.json'
    monkeypatch.setattr(sys, 'argv', ['collector.run', '--retry-failed', '--write-items',
                                      '--db-path', str(tmp_path / 'notices.json'),
                                      '--report-path', str(output_report), '--items-path', str(tmp_path / 'items.json')])
    assert run.main() == 0
    assert calls == [chinese['source_board_id']]
    assert source_path.read_bytes() == original_bytes
    result = store.load_collection_report(output_report)
    by_board = {row['source_board_id']: row for row in result['channels']}
    assert set(by_board) == {school['source_board_id'], chinese['source_board_id']}
    assert by_board[school['source_board_id']] == school
    assert by_board[chinese['source_board_id']]['errors'] == []
    assert captured['ids'] == set(ids.values())  # Items retain the successful channel too.
    assert {row['source_board_id'] for row in captured['reports']} == set(by_board)
    assert captured['context'] == context


def test_retry_report_path_stays_within_data_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(run, 'ROOT', tmp_path)
    runs = tmp_path / 'data/runs'
    runs.mkdir(parents=True)
    good = runs / 'report.json'
    good.write_text('{}', encoding='utf-8')
    assert run.retry_report_path('data/runs/report.json') == good.resolve()
    outside = tmp_path / 'outside.json'
    outside.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='data/runs'):
        run.retry_report_path(outside)


def test_retry_never_overwrites_its_selection_report(monkeypatch, tmp_path):
    from collector import preview
    data = tmp_path / 'data'
    runs = data / 'runs'
    runs.mkdir(parents=True)
    channels = yaml.safe_load((run.ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    board_channel = next(c for c in channels if c['id'] == 'knu-academic')
    (data / 'channels.yaml').write_text(yaml.safe_dump([board_channel], allow_unicode=True), encoding='utf-8')
    source = runs / 'input.json'
    store.save_collection_report(dict(channels=[dict(
        source_board_id=run.board_id_for(board_channel), channel_id=board_channel['id'],
        channel_ids=[board_channel['id']], errors=[dict(message='fixture')], truncated=False)]), source)
    monkeypatch.setattr(run, 'ROOT', tmp_path)
    monkeypatch.setattr(preview, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['collector.run', '--retry-failed', '--write-items',
                                      '--retry-report', str(source), '--report-path', str(source)])
    with pytest.raises(SystemExit):
        run.main()


def test_workflow_retry_input_is_quoted_and_full_mode_stays_default():
    workflow = yaml.safe_load((run.ROOT / '.github/workflows/collect.yml').read_text(encoding='utf-8'))
    triggers = workflow.get('on', workflow.get(True))
    dispatch = triggers['workflow_dispatch']['inputs']
    assert dispatch['collection_mode']['default'] == 'full'
    assert dispatch['collection_mode']['options'] == ['full', 'retry_failed']
    steps = workflow['jobs']['collect']['steps']
    step = next(row for row in steps if row.get('id') == 'collect')
    assert 'inputs.retry_report' in step['env']['RETRY_REPORT']
    assert '"$RETRY_REPORT"' in step['run']
    assert '--all-required --write-items --collect-extras --skip-meals' in step['run']
    assert '${{ inputs.retry_report }}' not in step['run']
