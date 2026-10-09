"""운영 기준·일일 경계·전체 점검을 인터넷 없이 확인한다."""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from collector import run, store
from collector.http import FetchError
from collector.knu_cms import parse_detail

CMS = Path(__file__).parent / 'fixtures/knu-cms'
META = json.loads((CMS / 'metadata.json').read_text())
CHANNEL = dict(id=run.CHANNEL_ID, source_url=META['files'][0]['url'])
START = datetime.fromisoformat('2026-10-01T05:37:00+09:00')
DETAIL = parse_detail((CMS / '국어국문학과_상세.html').read_text(), META['files'][1]['url'])


def item(post_id, posted='2026-08-01', pinned=False):
    return dict(source_post_id=str(post_id), title=DETAIL['title'], posted_at=posted,
                pinned=pinned, url=f'https://home.knu.ac.kr/post/{post_id}')


@pytest.fixture
def offline(monkeypatch):
    pages, dates, calls, failures, revisions = {}, {}, [], set(), {}
    class Client:
        def get(self, url):
            calls.append(url)
            if url in failures:
                raise FetchError('테스트 실패')
            return url, url
    monkeypatch.setattr(run, 'parse_list', lambda html, url: pages[url])
    monkeypatch.setattr(run, 'next_page', lambda html, url: pages.get(url + '/next') and url + '/next')
    monkeypatch.setattr(run, 'parse_detail', lambda html, url: dict(
        DETAIL, source_post_id=url.rsplit('/', 1)[1], url=url,
        posted_at=dates[url.rsplit('/', 1)[1]], **revisions.get(url, {})))
    def configure(*page_items):
        pages.clear()
        for index, entries in enumerate(page_items):
            pages[CHANNEL['source_url'] + '/next' * index] = entries
            dates.update({entry['source_post_id']: entry['posted_at'] for entry in entries})
        calls.clear()
    return Client(), configure, calls, failures, revisions, dates


def seed(path, rows=()):
    for entry in rows:
        notice = dict(source_board_id=run.BOARD_ID, source_post_id=entry['source_post_id'],
                      channel_ids=[run.CHANNEL_ID], title=entry['title'], url=entry['url'],
                      posted_at=entry['posted_at'], deadline=None, body=DETAIL['body'], body_status='text')
        store.upsert_notices([notice], path=path, checked_at=START.isoformat())
    state = {'boards': {run.BOARD_ID: dict(initialized_at=START.isoformat(), last_full_scan_at=START.isoformat())}}
    store.save_collection_state(state, path)
    return state


def test_bootstrap_then_new_and_late_discovery_retry(tmp_path, offline):
    client, configure, calls, failures, revisions, dates = offline
    path = tmp_path / 'notices.json'
    configure([item(1, '2026-09-30')])
    first = run.collect(client, CHANNEL, db_path=path, now=START)
    assert first['bootstrap'] and first['new_candidates'] == []
    assert store.load_collection_state(path)['boards'][run.BOARD_ID]['initialized_at'] == START.isoformat()
    configure([item(1, '2026-09-30'), item(2, '2026-09-30'), item(3), item(4, None)])
    report = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(hours=1))
    assert report['new_candidates'] == [run.BOARD_ID + ':2']
    assert report['late_discoveries'] == [run.BOARD_ID + ':3', run.BOARD_ID + ':4']
    again = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(hours=2))
    assert again['new'] == [] and again['new_candidates'] == report['new_candidates']
    assert again['late_discoveries'] == report['late_discoveries']
    following = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(days=1))
    assert following['new_candidates'] == following['late_discoveries'] == []


@pytest.mark.parametrize('middle', [item(3, '2026-09-01'), item(3, None)])
def test_daily_boundary_resets_on_recent_or_unknown_date(tmp_path, offline, middle):
    client, configure, calls, *_ = offline
    path = tmp_path / 'notices.json'
    pinned = item(99, '2026-09-30', True)
    rows = [item(1), item(2), middle, item(4), item(5), item(6), pinned]
    seed(path, rows)
    configure([item(1), pinned], [middle, pinned], [item(4), pinned], [item(5), pinned], [item(6)])
    report = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(hours=1))
    assert report['mode'] == 'daily' and report['pages'] == 4
    assert report['window_complete'] and not report['truncated']
    assert CHANNEL['source_url'] + '/next' * 4 not in calls
    assert pinned['url'] in calls  # 고정글은 경계를 방해하지 않고 상세는 확인한다.


def test_daily_window_and_explicit_full_modes(tmp_path, offline):
    client, configure, calls, *_ = offline
    path = tmp_path / 'notices.json'
    rows = [item(i) for i in range(1, 5)]
    seed(path, rows)
    configure(*[[row] for row in rows])
    daily = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(days=6))
    assert daily['pages'] == 2 and daily['mode'] == 'daily'
    configure(*[[row] for row in rows])
    daily = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(days=7))
    assert daily['pages'] == 2 and daily['mode'] == 'daily'
    configure(*[[row] for row in rows])
    daily = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(days=14))
    assert daily['pages'] == 2 and daily['mode'] == 'daily'
    explicit = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(days=14, hours=1), mode='full')
    assert explicit['pages'] == 4 and explicit['mode'] == 'full'
    initial = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(days=7, hours=2), mode='init')
    assert initial['bootstrap'] and initial['new_candidates'] == []


@pytest.mark.parametrize('failure', ['detail', 'cap', 'list'])
def test_incomplete_bootstrap_does_not_advance_state(tmp_path, offline, failure):
    client, configure, calls, failures, *_ = offline
    path = tmp_path / 'notices.json'
    configure([item(1)], [item(2)])
    if failure == 'detail':
        failures.add(item(1)['url'])
    elif failure == 'list':
        failures.add(CHANNEL['source_url'])
    report = run.collect(client, CHANNEL, db_path=path, now=START, max_pages=1 if failure == 'cap' else 1000)
    assert report['errors'] or report['truncated']
    assert store.load_collection_state(path) == {'boards': {}}
    failures.clear()
    retry = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(hours=1))
    assert retry['bootstrap'] and retry['new_candidates'] == []
    assert len(store.load_notices(path)) == 2


def test_stored_deadline_outside_window_gets_fresh_metadata(tmp_path, offline):
    client, configure, calls, failures, revisions, dates = offline
    path = tmp_path / 'notices.json'
    rows = [item(i) for i in range(1, 5)]
    seed(path, rows)
    notice = {k: v for k, v in store.load_notices(path)[3].items() if k in store.INPUT_FIELDS}
    notice['deadline'] = '2026-10-05'
    store.upsert_notices([notice], path=path, checked_at=START.isoformat())
    configure([item(1)], [item(2)], [item(3)])
    dates['4'] = '2026-08-01'
    revisions[item(4)['url']] = dict(title='원문에서 바뀐 제목')
    report = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(hours=1))
    assert report['pages'] == 2 and report['direct_checks'] == 1
    assert item(4)['url'] in calls and run.BOARD_ID + ':4' in report['updated']
    assert store.load_notices(path)[3]['title'] == '원문에서 바뀐 제목'
    assert store.load_notices(path)[3]['deadline'] is None


def test_state_validation_prevents_silent_reset(tmp_path):
    path = tmp_path / 'notices.json'
    state = seed(path)
    stored = store.collection_state_path(path)
    before = stored.read_bytes()
    state['boards'][run.BOARD_ID]['initialized_at'] = '2026-10-01'
    with pytest.raises(ValueError):
        store.save_collection_state(state, path)
    assert stored.read_bytes() == before
    stored.write_text('{broken')
    with pytest.raises(json.JSONDecodeError):
        store.load_collection_state(path)


def test_new_candidates_survive_checkpoint_interruption(tmp_path, offline):
    client, configure, calls, failures, *_ = offline
    path = tmp_path / 'notices.json'
    seed(path)
    configure([item(i, '2026-09-30') for i in range(30)])
    class Interrupted:
        def get(self, url):
            if url == item(25)['url']:
                raise RuntimeError('중단')
            return client.get(url)
    with pytest.raises(RuntimeError):
        run.collect(Interrupted(), CHANNEL, db_path=path, now=START + timedelta(hours=1))
    assert len(store.load_notices(path)) == 25
    retry = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(hours=2))
    assert len(retry['new']) == 5 and len(retry['new_candidates']) == 30
    assert not retry['bootstrap']


def test_failed_manual_full_scan_keeps_last_success(tmp_path, offline):
    client, configure, calls, failures, *_ = offline
    path = tmp_path / 'notices.json'
    before = seed(path, [item(1)])
    configure([item(1)])
    failures.add(item(1)['url'])
    report = run.collect(client, CHANNEL, db_path=path, now=START + timedelta(days=7), mode='full')
    assert report['mode'] == 'full' and report['errors']
    assert store.load_collection_state(path) == before


def test_start_initializes_recent_window_without_claiming_full_scan(tmp_path, offline):
    client, configure, *_ = offline
    path=tmp_path/'notices.json'
    configure([item(1,'2026-09-30')],[item(2)],[item(3)],[item(4)])
    started=run.collect(client,CHANNEL,db_path=path,mode='start',now=START)
    assert started['pages']==3 and started['window_complete'] and not started['truncated']
    assert started['bootstrap'] and started['new_candidates']==[]
    markers=store.load_collection_state(path)['boards'][run.BOARD_ID]
    assert markers['initialized_at']==START.isoformat() and markers['last_full_scan_at'] is None
    with pytest.raises(ValueError):
        run.collect(client,CHANNEL,db_path=path,mode='start',now=START)
    daily=run.collect(client,CHANNEL,db_path=path,now=START+timedelta(days=1))
    assert daily['mode']=='daily' and daily['pages']==3 and daily['new_candidates']==[]
    daily=run.collect(client,CHANNEL,db_path=path,now=START+timedelta(days=7))
    assert daily['mode']=='daily' and daily['pages']==3
    assert store.load_collection_state(path)['boards'][run.BOARD_ID]['last_full_scan_at'] is None
    full=run.collect(client,CHANNEL,db_path=path,mode='full',now=START+timedelta(days=7,hours=1))
    assert full['mode']=='full' and full['pages']==4


def test_state_commit_preserves_other_board_added_during_fetch(tmp_path, offline):
    client, configure, *_ = offline
    path = tmp_path / 'notices.json'
    configure([item(1, '2026-09-30')])
    other = dict(initialized_at=START.isoformat(), last_full_scan_at=None)
    class WithStateUpdate:
        def get(self, url):
            state = store.load_collection_state(path)
            state['boards']['knu-other-board'] = other
            store.save_collection_state(state, path)
            return client.get(url)
    report = run.collect(WithStateUpdate(), CHANNEL, db_path=path, now=START, mode='start')
    assert report['window_complete'] and not report['errors']
    boards = store.load_collection_state(path)['boards']
    assert boards['knu-other-board'] == other and boards[run.BOARD_ID]['initialized_at'] == START.isoformat()
