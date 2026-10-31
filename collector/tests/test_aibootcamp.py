"""비교과: AI부트캠프사업단 알림(정적 사이트) 목록·상세·수집 확인. 인터넷 없이 저장한 페이지로 시험한다."""
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from collector import other_notices as parser, run
from collector.http import FetchError
from collector.knu_cms import ParseError, to_notice
from collector.store import SEOUL, load_notices

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'collector/tests/fixtures/aibootcamp'
LIST_URL = 'https://aibootcamp.knu.ac.kr/notices/'
SJSU = '2026-10-21-global-bootcamp-recruitment'
LAUNCH = '2026-08-09-site-launch'


def read(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


def detail_url(slug):
    return f'https://aibootcamp.knu.ac.kr/notices/{slug}/'


def test_list_reads_all_notices_with_dates_and_pins():
    rows = parser.parse_aiboot_list(read('notices.html'), LIST_URL)
    assert len(rows) == 10 and len({r['source_post_id'] for r in rows}) == 10
    first = rows[0]
    assert first['source_post_id'] == '2026-10-22-winter-immersive-briefing' and first['posted_at'] == '2026-10-22'
    assert first['url'] == detail_url(first['source_post_id']) and first['pinned']
    assert [r['pinned'] for r in rows].count(True) == 2
    assert all(r['source_post_id'].startswith(r['posted_at']) for r in rows)
    assert parser.aiboot_next_page(read('notices.html'), LIST_URL) is None
    with pytest.raises(ParseError):
        parser.parse_aiboot_list(read('notices.html'), 'https://example.com/notices/')
    with pytest.raises(ParseError):
        parser.parse_aiboot_list('<html><main><ul></ul></main></html>', LIST_URL)


def test_detail_matches_list_and_uses_site_deadline():
    item = next(r for r in parser.parse_aiboot_list(read('notices.html'), LIST_URL) if r['source_post_id'] == SJSU)
    detail = parser.parse_aiboot_detail(read(f'detail-{SJSU}.html'), detail_url(SJSU))
    assert detail['title'] == item['title'] and detail['posted_at'] == '2026-10-21'
    assert detail['body_status'] == 'text' and '산호세주립대' in detail['body']
    assert detail['deadline'] == '2026-11-12'  # '마감일 2026-11-12 24:00'
    assert [a['name'] for a in detail['attachments']] == ['참가자 모집 공고(PDF)', '참가자 모집 공고(한글)', '참가 서식(서식1~5, 한글)']
    notice = to_notice(item, detail, board_id='knu-aibootcamp-notices', channel_ids=['notice-aibootcamp'])
    assert notice['deadline'] == '2026-11-12' and 'attachments' not in notice
    launch = parser.parse_aiboot_detail(read(f'detail-{LAUNCH}.html'), detail_url(LAUNCH))
    assert launch['deadline'] is None and launch['body_status'] == 'text'
    with pytest.raises(ParseError):
        parser.parse_aiboot_detail(read(f'detail-{SJSU}.html'), 'https://aibootcamp.knu.ac.kr/programs/x/')


def test_channel_is_extracurricular_and_selected_only_with_matching_url():
    channels = yaml.safe_load((ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    channel = next(c for c in channels if c['id'] == 'notice-aibootcamp')
    assert channel['category'] == 'extracurricular' and channel['required'] == 'none'
    [selected] = run.select_channels(channels, ['notice-aibootcamp'])
    assert run.board_id_for(selected) == 'knu-aibootcamp-notices'
    wrong = dict(channel, source_url='https://aibootcamp.knu.ac.kr/programs/')
    with pytest.raises(ValueError):
        run.select_channels([wrong], [wrong['id']])


class FixtureClient:
    request_count = 0

    def get(self, url):
        self.request_count += 1
        if url == LIST_URL:
            return read('notices.html'), url
        for slug in (SJSU, LAUNCH):
            if url == detail_url(slug):
                return read(f'detail-{slug}.html'), url
        raise FetchError('시험용 저장 페이지 없음')


def test_collect_stores_notices_with_site_deadline(tmp_path):
    channels = yaml.safe_load((ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    [channel] = run.select_channels(channels, ['notice-aibootcamp'])
    db = tmp_path / 'notices.json'
    report = run.collect(FixtureClient(), channel, db_path=db, now=datetime(2026, 10, 30, 9, tzinfo=SEOUL))
    assert report['listed'] == 10 and report['successful'] == 2 and len(report['errors']) == 8
    stored = {row['source_post_id']: row for row in load_notices(db)}
    assert stored[SJSU]['deadline'] == '2026-11-12' and stored[SJSU]['channel_ids'] == ['notice-aibootcamp']
    assert stored[LAUNCH]['deadline'] is None


class TwoPostClient(FixtureClient):
    """저장해 둔 상세 두 건만 목록에 남겨 오류 없이 끝나는 수집을 만든다."""

    def get(self, url):
        html, actual = super().get(url)
        if url == LIST_URL:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            for row in soup.select('main li'):
                link = row.select_one('a[href^="/notices/"]')
                if link and link['href'].strip('/').split('/')[-1] not in (SJSU, LAUNCH):
                    row.decompose()
            html = str(soup)
        return html, actual


def test_first_collection_recent_uses_start_window_only_for_marked_channels(tmp_path):
    channels = yaml.safe_load((ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    for channel_id in ('notice-423ad5624dbc', 'notice-5a80fc96a24d', 'notice-d365c7a64837'):
        marked = next(c for c in channels if c['id'] == channel_id)
        assert marked['category'] == 'extracurricular' and marked['first_collection'] == 'recent'
    [channel] = run.select_channels(channels, ['notice-aibootcamp'])
    now = datetime(2026, 10, 30, 9, tzinfo=SEOUL)
    # 표시한 채널: 정기(daily) 첫 실행이 최근 구간만 적재하는 start로 바뀌고 전체 점검 시각은 남기지 않는다.
    recent = run.collect(TwoPostClient(), dict(channel, first_collection='recent'), db_path=tmp_path / 'a.json', now=now)
    assert recent['mode'] == 'start' and recent['bootstrap'] and not recent['errors']
    state = run.load_collection_state(tmp_path / 'a.json')['boards']['knu-aibootcamp-notices']
    assert state['initialized_at'] and state['last_full_scan_at'] is None
    # 표시하지 않은 채널은 기존처럼 첫 실행을 과거 전체 적재(init)로 한다.
    plain = run.collect(TwoPostClient(), channel, db_path=tmp_path / 'b.json', now=now)
    assert plain['mode'] == 'init'
    assert run.load_collection_state(tmp_path / 'b.json')['boards']['knu-aibootcamp-notices']['last_full_scan_at']
