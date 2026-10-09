import json
from pathlib import Path

import pytest
import requests

from collector import http
from collector.knu_cms import post_id
from collector.run import BOARD_ID, CHANNEL_ID, collect
from collector.store import load_notices, load_collection_report, save_collection_report

CMS = Path(__file__).parent / 'fixtures/knu-cms'
META = json.loads((CMS / 'metadata.json').read_text(encoding='utf-8'))
CHANNEL = dict(id=CHANNEL_ID, source_url=META['files'][0]['url'])


class FixtureClient:
    def get(self, url):
        if url == CHANNEL['source_url']:
            return (CMS / '국어국문학과_목록.html').read_text(encoding='utf-8'), url
        if post_id(url) == '1283':
            return (CMS / '국어국문학과_상세.html').read_text(encoding='utf-8'), url
        raise http.FetchError('오프라인 테스트용 상세 실패')


def test_partial_failure_and_second_run(tmp_path):
    path = tmp_path / 'notices.json'
    report = collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    assert report['initial_import'] is True
    assert report['listed'] == 19 and report['successful'] == 1
    assert len(report['errors']) == 18
    assert report['new'] == [BOARD_ID + ':1283']
    assert load_notices(path)[0]['channel_ids'] == [CHANNEL_ID]
    second = collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    assert second['initial_import'] is False and second['new'] == []
    assert second['unchanged'] == []
    assert second['skipped'] == [BOARD_ID + ':1283']
    report_path = tmp_path / 'report.json'
    save_collection_report(report, report_path)
    assert load_collection_report(report_path)['errors'] == report['errors']


def test_list_failure_preserves_db(tmp_path):
    path = tmp_path / 'notices.json'
    collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    before = path.read_bytes()
    class Blocked:
        def get(self, url):
            return '<html>접근 차단</html>', url
    report = collect(Blocked(), CHANNEL, db_path=path, max_pages=1)
    assert len(report['errors']) == 1 and report['successful'] == 0
    assert path.read_bytes() == before


@pytest.mark.parametrize('mode', ['timeout', '503'])
def test_retries_spacing_and_user_agent(monkeypatch, mode):
    clock = [0.0]
    monkeypatch.setattr(http.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(http.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    calls = []
    def get(url, **kwargs):
        calls.append(clock[0])
        assert kwargs['timeout'] == (10, 30) and kwargs['allow_redirects'] is False
        if mode == 'timeout':
            raise requests.Timeout('timeout')
        response = requests.Response()
        response._content_consumed = True
        response.status_code = 503
        response.url = url
        response._content = b'error'
        return response
    with http.Client() as client:
        assert client.session.headers['User-Agent'] == http.USER_AGENT
        monkeypatch.setattr(client.session, 'get', get)
        with pytest.raises(http.FetchError):
            client.get('https://example.com/list')
    assert calls == [0.0, 1.0, 2.0]
    assert client.request_count == 3


def test_redirect_is_paced_and_html_decoded(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(http.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(http.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    calls = []
    def get(url, **kwargs):
        calls.append(clock[0])
        response = requests.Response()
        response._content_consumed = True
        response.url = url
        response._content = '<meta charset="utf-8"><p>새 공지</p>'.encode()
        response.encoding = 'ISO-8859-1'
        response.status_code = 302 if len(calls) == 1 else 200
        response.headers = {'Location': '/final', 'Content-Type': 'text/html'}
        return response
    with http.Client() as client:
        monkeypatch.setattr(client.session, 'get', get)
        html, url = client.get('https://example.com/list')
    assert '새 공지' in html and url == 'https://example.com/final'
    assert calls == [0.0, 1.0]
    assert client.request_count == 2


def test_two_pages_and_cross_page_deduplication(tmp_path):
    from bs4 import BeautifulSoup
    from collector.knu_cms import next_page
    original = (CMS / '국어국문학과_목록.html').read_text(encoding='utf-8')
    following = next_page(original, CHANNEL['source_url'])
    assert following and following != CHANNEL['source_url']
    second = BeautifulSoup(original, 'html.parser')
    second.select_one('.paging').clear()
    second.select_one('.paging').append(BeautifulSoup('<strong>2</strong>', 'html.parser'))
    class TwoPages(FixtureClient):
        def get(self, url):
            if url == following:
                return str(second), url
            return super().get(url)
    report = collect(TwoPages(), CHANNEL, db_path=tmp_path / 'notices.json')
    assert report['pages'] == 2 and report['listed'] == 19
    assert report['successful'] == 1 and len(report['errors']) == 18
    assert report['truncated'] is False
    limited = collect(TwoPages(), CHANNEL, db_path=tmp_path / 'limited.json', max_pages=1)
    assert limited['pages'] == 1 and limited['truncated'] is True


def test_page_group_boundary_and_cycle(tmp_path):
    from bs4 import BeautifulSoup
    from collector.knu_cms import next_page, ParseError
    original = (CMS / '국어국문학과_목록.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(original, 'html.parser')
    paging = soup.select_one('.paging')
    paging.clear()
    paging.append(BeautifulSoup('<strong>10</strong><a class="next" href="?page=11">다음</a>', 'html.parser'))
    assert next_page(str(soup), CHANNEL['source_url']).endswith('?page=11')
    paging.clear()
    paging.append(BeautifulSoup('<strong>1</strong><a href="?nav_code=kor1657071357">2</a>', 'html.parser'))
    class Cycle(FixtureClient):
        def get(self, url):
            if url == CHANNEL['source_url']:
                return str(soup), url
            return super().get(url)
    report = collect(Cycle(), CHANNEL, db_path=tmp_path / 'notices.json')
    assert any('순환' in error['message'] for error in report['errors'])
    with pytest.raises(ParseError):
        next_page('<html></html>', CHANNEL['source_url'])


@pytest.mark.parametrize('posted,pinned,deadline,checked,changed,expected', [
    ('2026-09-24', True, None, '2026-09-30T10:00:00+09:00', False, True),
    ('2026-09-23', False, None, '2026-09-30T10:00:00+09:00', False, False),
    ('2026-09-01', False, None, '2026-09-30T10:00:00+09:00', False, False),
    ('2026-08-31', False, None, '2026-09-30T10:00:00+09:00', False, False),
    # A pin alone does not justify fetching an old, unchanged detail again.
    ('2026-08-01', True, None, '2026-09-30T10:00:00+09:00', False, False),
    ('2026-08-01', True, None, '2026-09-25T10:00:00+09:00', False, False),
    ('2026-08-01', True, None, '2026-09-24T10:00:00+09:00', False, True),
    ('2026-08-01', True, '2026-10-01', '2026-09-30T10:00:00+09:00', False, True),
    ('2026-08-01', False, '2026-09-30', '2026-09-30T10:00:00+09:00', False, False),
    ('2026-08-01', False, None, '2026-09-24T10:00:00+09:00', False, True),
    ('2026-08-01', False, None, '2026-09-24T10:00:01+09:00', False, False),
    (None, False, None, '2026-09-30T10:00:00+09:00', False, True),
    ('2026-08-01', True, None, '2026-09-30T10:00:00+09:00', True, True),
])
def test_detail_policy_boundaries(posted, pinned, deadline, checked, changed, expected):
    from datetime import datetime
    from collector.run import needs_detail
    item = dict(title='수정 제목' if changed else '제목', posted_at=posted, pinned=pinned)
    previous = dict(title='제목', posted_at=posted, deadline=deadline,
                    last_checked_at=checked, body_status='text')
    now = datetime.fromisoformat('2026-10-01T10:00:00+09:00')
    assert needs_detail(item, previous, now) is expected
    assert needs_detail(item, None, now) is True


def test_changed_posted_date_and_needs_review_still_fetch_old_detail():
    from datetime import datetime
    from collector.run import needs_detail
    now = datetime.fromisoformat('2026-10-01T10:00:00+09:00')
    previous = dict(title='제목', posted_at='2026-08-01', deadline=None,
                    last_checked_at='2026-09-30T10:00:00+09:00', body_status='text')
    assert needs_detail(dict(title='제목', posted_at='2026-08-02', pinned=True), previous, now)
    previous['body_status'] = 'needs-review'
    assert needs_detail(dict(title='제목', posted_at='2026-08-01', pinned=True), previous, now)


@pytest.mark.parametrize('age', [8, 20, 30])
def test_older_recent_details_wait_seven_days_since_last_success(age):
    from datetime import datetime, timedelta
    from collector.run import needs_detail
    now = datetime.fromisoformat('2026-10-01T10:00:00+09:00')
    item = dict(title='제목', posted_at=(now.date()-timedelta(days=age)).isoformat(), pinned=False)
    previous = dict(item, deadline=None, body_status='text',
                    last_checked_at=(now-timedelta(days=7)).isoformat())
    assert not needs_detail(item, previous, now-timedelta(seconds=1))
    assert needs_detail(item, previous, now)
    previous['last_checked_at'] = now.isoformat()
    assert not needs_detail(item, previous, now+timedelta(days=6, hours=23, minutes=59))
    assert needs_detail(item, previous, now+timedelta(days=7))


@pytest.mark.parametrize('age,days_left', [(20, 3), (30, 1), (40, 0)])
def test_pending_deadline_is_fetched_and_reminder_is_not_stale(tmp_path, monkeypatch, age, days_left):
    from datetime import datetime, timedelta
    from collector import run, store
    from collector.daily_items import build_items
    now = datetime.fromisoformat('2026-10-01T10:00:00+09:00')
    monkeypatch.setattr(run, 'datetime', type('FixedDateTime', (datetime,),
                                               {'now': classmethod(lambda cls, tz: now)}))
    yesterday = now-timedelta(days=1)
    posted = (now.date()-timedelta(days=age)).isoformat()
    deadline = (now.date()+timedelta(days=days_left)).isoformat()
    url = 'https://home.knu.ac.kr/post/1'
    item = dict(source_post_id='1', title='제출 안내', posted_at=posted, url=url, pinned=False)
    detail = dict(source_post_id='1', title=item['title'], posted_at=posted, url=url,
                  body=f'제출 마감: {deadline}.', body_status='text')
    path = tmp_path/'notices.json'
    notice = dict(detail, source_board_id=BOARD_ID, channel_ids=[CHANNEL_ID], deadline=deadline)
    store.upsert_notices([notice], path=path, checked_at=yesterday.isoformat())
    store.save_collection_state({'boards':{BOARD_ID:dict(initialized_at=yesterday.isoformat(),
                                                         last_full_scan_at=yesterday.isoformat())}}, path)
    # 깊은 과거 글은 목록 밖에서도 직접 확인한다.
    monkeypatch.setattr(run, 'parse_list', lambda *args: [item] if age <= 30 else [])
    monkeypatch.setattr(run, 'next_page', lambda *args: None)
    monkeypatch.setattr(run, 'parse_detail', lambda *args: detail)
    calls = []
    class OfflineClient:
        def get(self, requested):
            calls.append(requested)
            return '', requested
    report = collect(OfflineClient(), CHANNEL, db_path=path, now=now, mode='daily')
    assert url in calls and report['successful'] == 1 and not report['errors']
    assert report['direct_checks'] == (1 if age > 30 else 0)
    rows = store.load_notices(path)
    assert rows[0]['last_checked_at'] == now.isoformat()
    items = build_items(rows, store.load_collection_state(path),
                        [dict(id=CHANNEL_ID, name='학과 공지', source_board_id=BOARD_ID)], now=now,
                        reports=[dict(channels=[report])])
    assert items['channels'][0]['notices'][0]['reason'] == 'reminder'
    assert items['channels'][0]['notices'][0]['dday'] == days_left
    assert not any('오늘 상세 확인' in e['message'] for e in items['errors'])


def test_skip_does_not_advance_detail_check_time(tmp_path):
    from bs4 import BeautifulSoup
    from datetime import datetime
    path = tmp_path / 'notices.json'
    collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    before = load_notices(path)[0]
    original = (CMS / '국어국문학과_목록.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(original, 'html.parser')
    for row in soup.select('.board_list tbody tr'):
        link = row.select_one('td.subject a')
        if post_id(link['href']) != '1283':
            row.decompose()
        else:
            row.select_one('td').attrs['class'] = ['number']
    soup.select_one('.paging').clear()
    soup.select_one('.paging').append(BeautifulSoup('<strong>1</strong>', 'html.parser'))
    class ListOnly:
        def get(self, url):
            assert url == CHANNEL['source_url'], '오래된 글의 상세를 요청하면 안 됩니다'
            return str(soup), url
    now = datetime.fromisoformat(before['last_checked_at'])
    report = collect(ListOnly(), CHANNEL, db_path=path, now=now)
    assert report['skipped'] == [BOARD_ID + ':1283']
    assert report['unchanged'] == [] and report['successful'] == 0
    assert load_notices(path)[0] == before


def test_known_deadline_preserved_or_flagged_after_body_change(tmp_path):
    from collector.store import INPUT_FIELDS, upsert_notices
    path = tmp_path / 'notices.json'
    collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    row = {k: v for k, v in load_notices(path)[0].items() if k in INPUT_FIELDS}
    row['deadline'] = '2026-12-01'
    upsert_notices([row], path=path)
    collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    assert load_notices(path)[0]['deadline'] == '2026-12-01'
    row['body'] = '이전에 확인한 다른 원문'
    upsert_notices([row], path=path)
    report = collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    assert load_notices(path)[0]['deadline'] is None
    assert BOARD_ID + ':1283' in report['needs_review']


def test_board_identity_is_separate_for_same_post_id(tmp_path):
    from collector.run import board_id_for
    english = dict(id='notice-1abc9573202c', source_url='https://home.knu.ac.kr/HOME/english/sub.htm?nav_code=eng1621852173')
    path = tmp_path / 'notices.json'
    collect(FixtureClient(), CHANNEL, db_path=path, max_pages=1)
    class SamePostInAnotherBoard(FixtureClient):
        def get(self, url):
            if url == english['source_url']:
                return super().get(CHANNEL['source_url'])
            return super().get(url)
    report = collect(SamePostInAnotherBoard(), english, db_path=path, max_pages=1)
    assert report['source_board_id'] == 'knu-english-eng1621852173'
    assert report['initial_import'] is True
    rows = load_notices(path)
    assert len(rows) == 2
    assert {r['id'] for r in rows} == {BOARD_ID + ':1283', board_id_for(english) + ':1283'}
    assert all(len(r['channel_ids']) == 1 for r in rows)


def test_batch_continues_after_one_channel_failure(monkeypatch, tmp_path):
    from collector import run
    seen = []
    def fake_collect(client, channel, **kwargs):
        seen.append(channel['id'])
        return dict(channel_id=channel['id'], listed=0, successful=0, new=[], updated=[], skipped=[],
                    errors=[dict(message='테스트 실패')] if len(seen) == 1 else [],
                    request_count=1, duration_sec=0.1, truncated=False)
    path = tmp_path / 'report.json'
    monkeypatch.setattr(run, 'collect', fake_collect)
    monkeypatch.setattr('sys.argv', ['collector.run', '--report-path', str(path)])
    assert run.main() == 1
    assert seen == run.DEFAULT_CHANNEL_IDS
    report = json.loads(path.read_text())
    assert len(report['channels']) == 5 and report['request_count'] == 5
    assert seen[:2] == ['knu-academic', 'notice-df44dd8507c1']


def test_ingestion_checkpoint_survives_interruption(monkeypatch, tmp_path):
    from collector import run
    from collector.knu_cms import parse_detail
    detail = parse_detail((CMS / '국어국문학과_상세.html').read_text(encoding='utf-8'), META['files'][1]['url'])
    items = [dict(source_post_id=str(i), title=detail['title'], posted_at=detail['posted_at'],
                  url=f'https://home.knu.ac.kr/post/{i}', pinned=False) for i in range(30)]
    monkeypatch.setattr(run, 'parse_list', lambda *args: items)
    monkeypatch.setattr(run, 'next_page', lambda *args: None)
    monkeypatch.setattr(run, 'parse_detail', lambda html, url: dict(detail, source_post_id=url.rsplit('/', 1)[1], url=url))
    class Interrupted:
        def get(self, url):
            if url.endswith('/25'):
                raise RuntimeError('프로세스 중단 상황')
            return '', url
    path = tmp_path / 'notices.json'
    with pytest.raises(RuntimeError):
        collect(Interrupted(), CHANNEL, db_path=path)
    assert len(load_notices(path)) == 25
    class Complete:
        def get(self, url):
            return '', url
    report = collect(Complete(), CHANNEL, db_path=path)
    assert report['successful'] == 5 and len(report['skipped']) == 25
    assert len(report['new']) == 5 and len(load_notices(path)) == 30
