from datetime import datetime
import json

from collector import export_app, preview


NOW = datetime.fromisoformat('2026-10-05T08:00:00+09:00')


def test_collection_status_counts_physical_boards_and_today_outcomes():
    channels = [dict(id='a', name='학사', type='notice'), dict(id='b', name='학생', type='notice'),
                dict(id='c', name='전자', type='notice'), dict(id='d', name='인문', type='notice')]
    expected = [dict(source_board_id='board-a', channel_ids=['a', 'b']),
                dict(source_board_id='board-c', channel_ids=['c']),
                dict(source_board_id='board-d', channel_ids=['d'])]
    reports = [
        dict(source_board_id='board-a', channel_ids=['a', 'b'], started_at='2026-10-05T07:00:00+09:00',
             finished_at='2026-10-05T07:01:00+09:00', window_complete=True, errors=[], truncated=False),
        dict(source_board_id='board-c', channel_ids=['c'], started_at='2026-10-05T07:02:00+09:00',
             finished_at='2026-10-05T07:03:00+09:00', window_complete=False,
             errors=[dict(message='학교 응답 오류')], truncated=True),
        dict(source_board_id='board-d', channel_ids=['d'], started_at='2026-10-04T07:00:00+09:00',
             finished_at='2026-10-04T07:01:00+09:00', window_complete=True, errors=[], truncated=False),
    ]
    result = export_app.collection_status(channels, expected, reports, None, NOW)
    assert (result['physicalBoards'], result['todaySuccess'], result['todayFailed'], result['todayNotCollected']) == (3, 1, 1, 1)
    assert result['failedBoards'] == [dict(source_board_id='board-c', name='전자',
                                           reasons=['학교 응답 오류', '페이지 제한으로 전체 범위를 확인하지 못했습니다'])]
    assert result['lastCollectedAt'] == '2026-10-05T07:03:00+09:00'


def test_meal_status_requires_today_source_check_not_cached_week_data():
    channels = [dict(id='meal-46', type='meal', collection_enabled=True),
                dict(id='meal-35', type='meal', collection_enabled=True),
                dict(id='meal-85', type='meal', collection_enabled=True)]
    context = dict(date='2026-10-05', collected_at='2026-10-05T07:00:00+09:00',
                   sources=[dict(source='meal-46', checked_at='2026-10-05T06:59:00+09:00'),
                            dict(source='meal-85', checked_at='2026-10-06T06:59:00+09:00')],
                   errors=[dict(source='meal-35', message='미게시')],
                   meal_week={'meal-46': [{'date': '2026-10-05', 'menu': ['주간표 메뉴']}]})
    result = export_app.collection_status(channels, [], [], context, NOW)
    assert result['meals'] == dict(total=3, todaySuccess=1, todayFailed=1, todayNotCollected=1)
    assert result['lastCollectedAt'] == '2026-10-05T06:59:00+09:00'


def test_latest_reports_can_select_latest_per_board_across_dates(tmp_path, monkeypatch):
    runs = tmp_path / 'data/runs'
    runs.mkdir(parents=True)
    rows = [
        dict(source_board_id='board-a', started_at='2026-10-04T08:00:00+09:00',
             finished_at='2026-10-04T08:01:00+09:00', errors=[dict(message='old failure')], truncated=False),
        dict(source_board_id='board-a', started_at='2026-10-05T07:00:00+09:00',
             finished_at='2026-10-05T07:01:00+09:00', errors=[], truncated=False, window_complete=True),
    ]
    (runs / 'first.json').write_text(json.dumps({'channels': rows[:1]}))
    (runs / 'second.json').write_text(json.dumps({'channels': rows[1:]}))
    monkeypatch.setattr(preview, 'ROOT', tmp_path)
    all_latest = preview.latest_reports()
    today_latest = preview.latest_reports(datetime.fromisoformat('2026-10-05').date())
    assert all_latest[0]['channels'][0]['errors'] == []
    assert today_latest[0]['channels'][0]['started_at'].startswith('2026-10-05')
