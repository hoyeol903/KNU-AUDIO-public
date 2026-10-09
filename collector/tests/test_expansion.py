"""확대 채널의 선택·중복 연결·구형 목록 스킨 회귀 확인."""
from pathlib import Path
import pytest

from collector import run, store
from collector.knu_cms import parse_list, next_page, ParseError

CMS = Path(__file__).parent / 'fixtures/knu-cms'
BASE = dict(id=run.CHANNEL_ID, name='국문', source_url='https://home.knu.ac.kr/HOME/korean/sub.htm?nav_code=kor1657071357',
            template='knu-cms', classification='required', collection_enabled=True)


def test_verified_selection_groups_aliases_and_blocks_changed_sources():
    alias = dict(BASE, id='notice-alias', source_url=BASE['source_url'].replace('home.knu', 'korean.knu'))
    validation = dict(channels=[dict(channel_id=alias['id'], source_url=alias['source_url'],
                                    source_board_id=run.BOARD_ID, status='verified')])
    grouped = run.select_channels([BASE, alias], required_all=True, validation=validation)
    assert len(grouped) == 1 and grouped[0]['channel_ids'] == [BASE['id'], alias['id']]
    with pytest.raises(ValueError):
        run.select_channels([BASE, dict(alias, source_url=alias['source_url'] + '2')], [alias['id']], validation=validation)
    validation['channels'][0]['status'] = 'failed'
    with pytest.raises(ValueError):
        run.select_channels([BASE, alias], [alias['id']], validation=validation)


def test_board_ids_accept_official_alias_and_uppercase_only():
    assert run.board_id_for(dict(source_url='https://home.knu.ac.kr/HOME/CEBA/sub.htm?nav_code=CEB1748499674')) == 'knu-ceba-ceb1748499674'
    assert run.board_id_for(dict(source_url='https://cns.knu.ac.kr/HOME/cns/sub.htm?nav_code=cns1623199799')) == 'knu-cns-cns1623199799'
    with pytest.raises(ValueError):
        run.board_id_for(dict(source_url=BASE['source_url'].replace('home.knu.ac.kr', 'home.knu.ac.kr.evil.example')))


def test_channel_link_keeps_content_and_check_times(tmp_path):
    path = tmp_path / 'notices.json'
    notice = dict(source_board_id=run.BOARD_ID, source_post_id='1', channel_ids=[BASE['id']],
                  title='제목', url='https://home.knu.ac.kr/post/1', posted_at='2026-08-01', deadline=None,
                  body='원문', body_status='text')
    store.upsert_notices([notice], path=path)
    before = store.load_notices(path)[0]
    assert store.link_board_channels(run.BOARD_ID, [BASE['id'], 'notice-alias'], path) == 1
    after = store.load_notices(path)[0]
    assert after == dict(before, channel_ids=sorted([BASE['id'], 'notice-alias']))
    assert store.link_board_channels(run.BOARD_ID, ['notice-alias'], path) == 0
    with pytest.raises(ValueError):
        store.link_board_channels(run.BOARD_ID, ['bad channel'], path)


def test_legacy_list_reads_labelled_date_without_guessing():
    html = (CMS.parent / 'channels/e1ec1bf0eb87c2a2.html').read_text(encoding='utf-8')
    url = 'https://home.knu.ac.kr/HOME/bcst2/sub.htm?nav_code=bcs1611061294'
    rows = parse_list(html, url)
    assert len(rows) == 29 and rows[0]['posted_at'] == '2026-09-23'
    assert next_page(html, url)
    with pytest.raises(ParseError):
        parse_list(html.replace('>등록일<', '>미확인 열<'), url)


def test_collect_group_fetches_each_detail_once_and_links_skipped_records(tmp_path, monkeypatch):
    from collector.tests.test_run import FixtureClient, CHANNEL
    path = tmp_path / 'notices.json'
    client = FixtureClient()
    first = run.collect(client, dict(CHANNEL, channel_ids=[CHANNEL['id'], 'notice-alias']), db_path=path, max_pages=1)
    assert first['successful'] == 1
    assert store.load_notices(path)[0]['channel_ids'] == sorted([CHANNEL['id'], 'notice-alias'])
    # 기존 공지는 상세를 생략해도 새 논리 채널과 연결돼야 한다.
    monkeypatch.setattr(run, 'needs_detail', lambda *args: False)
    second = run.collect(client, dict(CHANNEL, channel_ids=[CHANNEL['id'], 'notice-third']), db_path=path, max_pages=1)
    assert second['linked'] == 1 and second['successful'] == 0
    assert store.load_notices(path)[0]['last_checked_at'] == store.load_notices(path)[0]['first_seen_at']
    assert 'notice-third' in store.load_notices(path)[0]['channel_ids']


def test_all_supported_live_fixtures_without_network():
    from collector.knu_cms import parse_detail, to_notice
    metadata = store.load_collection_report(CMS / 'expansion/metadata.json')
    root = CMS.parents[3]
    for entry in metadata['channels']:
        if entry['status'] not in {'verified', 'empty'}:
            continue
        files = entry['files']
        rows = parse_list((root / files['list']['path']).read_text(encoding='utf-8'), files['list']['url'])
        assert len(rows) == entry['listed'], entry['name']
        if entry['status'] == 'empty':
            assert rows == [] and 'detail' not in files
            continue
        assert next_page((root / files['list']['path']).read_text(encoding='utf-8'), files['list']['url']) == entry['next_url']
        detail = parse_detail((root / files['detail']['path']).read_text(encoding='utf-8'), files['detail']['url'])
        row = next(r for r in rows if r['source_post_id'] == entry['sample_post_id'])
        notice = to_notice(row, detail, board_id=entry['source_board_id'], channel_ids=[entry['channel_id']])
        assert notice['body_status'] == entry['body_status'], entry['name']
        if 'next' in files:
            assert len(parse_list((root / files['next']['path']).read_text(encoding='utf-8'), files['next']['url'])) == entry['next_listed']


def test_cms_alias_hosts_share_request_spacing(monkeypatch):
    import requests
    from collector import http
    clock, calls = [0.0], []
    monkeypatch.setattr(http.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(http.time, 'sleep', lambda sec: clock.__setitem__(0, clock[0] + sec))
    def get(url, **kwargs):
        calls.append(clock[0])
        response = requests.Response()
        response._content_consumed = True
        response.status_code, response.url = 200, url
        response._content = b'<p>hello</p>'
        response.headers['Content-Type'] = 'text/html'
        return response
    with http.Client() as client:
        monkeypatch.setattr(client.session, 'get', get)
        for host in ['home', 'cns', 'foodbio']:
            client.get(f'https://{host}.knu.ac.kr/HOME/cns/sub.htm')
    assert calls == [0.0, 1.0, 2.0]
