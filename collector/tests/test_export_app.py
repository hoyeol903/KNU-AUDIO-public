import json
from datetime import date, datetime

from collector import export_app, preview
from collector.store import collection_state_path, save_collection_state, upsert_notices


def test_export_preserves_snapshot_and_exports_channel_recent_union(tmp_path, monkeypatch):
    db = tmp_path / 'notices.json'
    checked = '2026-10-01T08:00:00+09:00'
    now = datetime.fromisoformat(checked)
    rows = []
    for n in range(55):
        post_id = 'selected-zzz' if n == 54 else f'post-{n:02}'
        channels = ['channel-a'] if n < 35 else ['channel-b']
        if 20 <= n < 35:
            channels = ['channel-a', 'channel-b']
        rows.append(dict(source_board_id='shared-board', source_post_id=post_id, channel_ids=channels,
                         title=f'제목 {n}', url=f'https://example.com/{n}',
                         posted_at='2026-09-30' if n == 54 else '2026-10-01', deadline=None,
                         body=f'원문 {n}', body_status='text'))
    upsert_notices(rows[:-1], checked_at='2026-09-30T08:00:00+09:00', path=db)
    upsert_notices(rows[-1:], checked_at=checked, path=db)
    save_collection_state({'boards': {'shared-board': {
        'initialized_at': '2026-09-30T06:00:00+09:00', 'last_full_scan_at': None}}}, db)
    before = db.read_bytes()
    state_path = collection_state_path(db)
    state_before = state_path.read_bytes()
    channels = [dict(id='channel-a', name='A', type='notice'), dict(id='channel-b', name='B', type='notice')]
    monkeypatch.setattr(export_app, 'catalog', lambda: (channels, []))
    monkeypatch.setattr(preview, 'catalog', lambda: (channels, []))
    monkeypatch.setattr(preview, 'latest_reports', lambda day=None: [])
    monkeypatch.setattr(preview, 'load_context', lambda: None)
    monkeypatch.setattr(export_app, 'datetime', type('FixedDateTime', (datetime,), {
        'now': classmethod(lambda cls, tz: now)}))
    output = tmp_path / 'nested' / 'site'
    export_app.export(output, db_path=db)

    payload = json.loads((output / 'data.json').read_text())
    assert payload['snapshot']['db_count'] == 55
    assert payload['snapshot']['items']['date'] == '2026-10-01'
    assert all(not channel['notices'] for channel in payload['snapshot']['items']['channels'])
    detail = json.loads((output / 'details/shared-board.json').read_text())
    assert len(detail) == 51  # Each channel contributes its own latest 30, plus the selected older notice.
    assert 'shared-board:selected-zzz' in detail
    assert set(detail['shared-board:selected-zzz']) == {'title', 'body', 'url', 'posted_at', 'deadline'}
    assert sum(row['status'] == 'selected' for row in payload['snapshot']['checks']) == 1
    assert db.read_bytes() == before
    assert state_path.read_bytes() == state_before
    assert (output / 'index.html').exists()


def _export_app_data(tmp_path, monkeypatch, context, raw=None):
    db = tmp_path / 'notices.json'
    checked = '2026-10-01T08:00:00+09:00'
    now = datetime.fromisoformat(checked)
    title = '★[공통] 【장학】 신청 안내 (~10/14)'
    base = dict(source_board_id='board-a', channel_ids=['channel-a'], url='https://example.com/a')
    upsert_notices([dict(base, source_post_id='old', title='지난 글', posted_at='2026-09-01', deadline=None,
                         body=None, body_status='image-only')], checked_at='2026-09-30T08:00:00+09:00', path=db)
    upsert_notices([dict(base, source_post_id='new', title=title, posted_at='2026-10-01', deadline='2026-10-14',
                         body='원문 그대로', body_status='text')], checked_at=checked, path=db)
    save_collection_state({'boards': {'board-a': {
        'initialized_at': '2026-09-30T06:00:00+09:00', 'last_full_scan_at': None}}}, db)
    channels = [dict(id='channel-a', name='A', type='notice', classification='required', required='all',
                     required_department_ids=[], source_url='https://example.com/list')]
    channels += [dict(id=id, name=id, type='meal', collection_enabled=True, source_url='https://example.com/' + id)
                 for id in ('meal-46', 'meal-35', 'meal-85')]
    departments = [dict(id='dept-a', name='가학과', college='나대학')]
    monkeypatch.setattr(export_app, 'catalog', lambda: (channels, departments))
    monkeypatch.setattr(preview, 'catalog', lambda: (channels, departments))
    monkeypatch.setattr(preview, 'latest_reports', lambda day=None: [])
    monkeypatch.setattr(preview, 'load_context', lambda: context)
    monkeypatch.setattr(export_app, 'datetime', type('FixedDateTime', (datetime,), {
        'now': classmethod(lambda cls, tz: now)}))
    output = tmp_path / 'site'
    export_app.export(output, db_path=db, raw_dir=raw or tmp_path / 'raw')
    text = (output / 'data/meta.json').read_text()
    return json.loads(text), text, json.loads((output / 'data/boards/channel-a.json').read_text()), title


def test_app_data_separates_ok_empty_failed_and_keeps_source_text(tmp_path, monkeypatch):
    context = dict(
        date='2026-10-01', collected_at='2026-10-01T07:00:00+09:00',
        weather=dict(summary='맑음', temp_min=11.1, temp_max=22.7, rain_prob=1), schedule=[],
        channels=[dict(channel_id='meal-46', notices=[], meals=[dict(place='식당', time='11:15~13:30', menu=['대패삼겹야채찜★'])]),
                  dict(channel_id='meal-35', notices=[], meals=[]), dict(channel_id='meal-85', notices=[], meals=[])],
        meal_week={'meal-46': [dict(date='2026-10-02', status='ok', meals=[dict(place='식당', time=None, menu=['홍국밥'])]),
                               dict(date='2026-10-03', status='empty', meals=[])]},
        errors=[dict(source='meal-35', message='중식: 오늘 메뉴 미게시, 휴무 여부 미확인'),
                dict(source='meal-85', message='요청 실패')])
    meta, text, posts, title = _export_app_data(tmp_path, monkeypatch, context)

    assert meta['asOf'] == '2026-10-01' and meta['checkedAt'] == '08:00'
    assert meta['weather'] == dict(status='ok', summary='맑음', min=11.1, max=22.7, rain=1)
    assert meta['schedule'] == dict(status='empty', items=[])
    assert {c['id']: c['status'] for c in meta['cafes']} == {'meal-46': 'ok', 'meal-35': 'empty', 'meal-85': 'failed'}
    assert meta['cafes'][0]['hours'] == '11:15~13:30' and meta['cafes'][0]['groups'][0]['menu'] == ['대패삼겹야채찜★']
    assert meta['cafes'][0]['days'] == [
        dict(date='2026-10-02', status='ok', hours=None, groups=[dict(label=None, hours=None, menu=['홍국밥'], price=None, head=0)]),
        dict(date='2026-10-03', status='empty', hours=None, groups=[])]
    assert meta['cafes'][1]['days'] == []
    assert meta['departments'] == [dict(id='dept-a', dept='가학과', college='나대학', avatar=None, requiredBoards=['channel-a'])]
    assert dict(source='meal-85', text='요청 실패') in meta['issues']
    board = meta['boards'][0]
    assert board['saved'] == 2 and board['collected'] and board['url'] == 'https://example.com/list'
    assert board['today'] == [dict(postId='board-a:new', kind='new', title=title, date='2026-10-01', deadline='2026-10-14')]
    assert 'dday' not in text  # D-day는 화면에서 계산한다.
    assert [row['id'] for row in posts] == ['board-a:new', 'board-a:old']  # 최신순
    assert posts[0] == dict(id='board-a:new', title=title, date='2026-10-01', deadline='2026-10-14',
                            url='https://example.com/a', body='원문 그대로', bodyStatus='ok')
    assert posts[1]['body'] is None and posts[1]['bodyStatus'] == 'unreadable'
    table = (tmp_path / 'site/data/new-notices.csv').read_text(encoding='utf-8-sig').splitlines()
    assert table[0] == '기준일,게시판,구분,제목,게시일,마감일,링크'
    assert table[1:] == ['2026-10-01,A,신규,' + title + ',2026-10-01,2026-10-14,https://example.com/a']


def test_app_data_marks_uncollected_sources_failed_not_empty(tmp_path, monkeypatch):
    meta, _, _, _ = _export_app_data(tmp_path, monkeypatch, None)

    assert meta['weather'] == dict(status='failed', summary=None, min=None, max=None, rain=None)
    assert meta['schedule']['status'] == 'failed'
    assert {c['status'] for c in meta['cafes']} == {'failed'}


def test_cafes_use_latest_saved_week_when_meals_were_not_collected_today(tmp_path, monkeypatch):
    raw = tmp_path / 'raw'
    week = lambda status, meals: [dict(date='2026-09-30', status='ok', meals=[]), dict(date='2026-10-01', status=status, meals=meals)]
    menu = [dict(place='식당', time='11:00~13:30', menu=['육개장'], label='중식', price=6000, head=0)]
    for day, value in (('2026-09-28', {'meal-46': week('ok', [dict(menu[0], menu=['옛 메뉴'])])}),
                       ('2026-09-29', {'meal-46': week('ok', menu), 'meal-35': week('empty', [])}),
                       ('2026-09-20', {'meal-85': week('ok', menu)})):  # 일주일보다 오래된 표는 쓰지 않는다.
        (raw / day).mkdir(parents=True)
        (raw / day / 'context.json').write_text(json.dumps(dict(meal_week=value)), encoding='utf-8')
    meta, _, _, _ = _export_app_data(tmp_path, monkeypatch, None, raw)

    cafes = {c['id']: c for c in meta['cafes']}
    assert cafes['meal-46']['status'] == 'ok' and cafes['meal-46']['menuFrom'] == '2026-09-29'
    assert cafes['meal-46']['groups'] == [dict(label='중식', hours='11:00~13:30', menu=['육개장'], price=6000, head=0)]
    assert len(cafes['meal-46']['days']) == 2
    assert cafes['meal-35']['status'] == 'empty' and cafes['meal-35']['groups'] == []
    assert cafes['meal-85']['status'] == 'failed' and cafes['meal-85']['menuFrom'] is None


def test_every_college_avatar_file_exists():
    files = {path.name for path in (export_app.ROOT / 'tools/avatars').glob('*.webp')}
    assert {value.split('/')[1] for value in export_app.COLLEGE_AVATARS.values()} == files
    assert export_app.COLLEGE_AVATARS['IT대학'] == 'avatars/04.webp'


def test_year_schedule_uses_latest_context_with_full_year_list(tmp_path):
    raw = tmp_path / 'raw'
    for day, rows in (('2026-10-04', [dict(title='개강', start='2026-09-01', end=None)]),
                      ('2026-10-05', [dict(title='중간고사', start='2026-10-20', end='2026-10-26')]),
                      ('2026-10-06', [])):
        (raw / day).mkdir(parents=True)
        (raw / day / 'context.json').write_text(json.dumps(dict(date=day, schedule_year=rows), ensure_ascii=False))
    data = export_app.year_schedule(raw)
    assert data == {'status': 'ok', 'from': '2026-10-05',
                    'items': [dict(title='중간고사', start='2026-10-20', end='2026-10-26')]}
    assert export_app.year_schedule(tmp_path / 'none') == {'status': 'empty', 'from': None, 'items': []}
