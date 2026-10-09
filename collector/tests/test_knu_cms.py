import json
from pathlib import Path

import pytest

from collector.knu_cms import ParseError, parse_detail, parse_list, to_notice
from collector.store import load_notices, upsert_notices

FIXTURES = Path(__file__).parent / 'fixtures'
CMS = FIXTURES / 'knu-cms'
META = json.loads((CMS / 'metadata.json').read_text(encoding='utf-8'))
LIST_URL = META['files'][0]['url']
DETAIL_URL = META['files'][1]['url']


def sample():
    rows = parse_list((CMS / '국어국문학과_목록.html').read_text(encoding='utf-8'), LIST_URL)
    detail = parse_detail((CMS / '국어국문학과_상세.html').read_text(encoding='utf-8'), DETAIL_URL)
    return rows, detail


def test_real_detail_and_store(tmp_path):
    rows, detail = sample()
    assert len(rows) == 19
    assert detail['source_post_id'] == '1283'
    assert detail['posted_at'] == '2026-08-24'
    assert '졸업논문' in detail['title']
    assert '2026. 9. 29.' in detail['body']
    assert '10. 1.' in detail['body']
    assert '아크로뱃' not in detail['body']
    assert detail['body_status'] == 'text' and detail['deadline'] is None
    assert len(detail['attachments']) == 5
    assert detail['attachments'][0]['name'].endswith('.pdf')
    assert all(a['url'].startswith('https://home.knu.ac.kr/HOME/bbs/bbs_download.php?')
               for a in detail['attachments'])
    item = next(r for r in rows if r['source_post_id'] == '1283')
    notice = to_notice(item, detail, board_id='korean-academic', channel_ids=['korean-academic'])
    path = tmp_path / 'notices.json'
    kwargs = dict(path=path, checked_at='2026-09-30T05:37:00+09:00')
    assert upsert_notices([notice], **kwargs)['new'] == ['korean-academic:1283']
    original = path.read_bytes()
    assert upsert_notices([notice], **kwargs)['unchanged'] == ['korean-academic:1283']
    assert path.read_bytes() == original
    assert len(load_notices(path)) == 1


@pytest.mark.parametrize('filename,url,count', [
    ('channels/1abc9573202c0e4c.html', 'https://home.knu.ac.kr/HOME/english/sub.htm?nav_code=eng1621852173', 12),
    ('channels/472ae43783879aaf.html', 'https://home.knu.ac.kr/HOME/math/sub.htm?nav_code=mat1623029308', 16),
])
def test_other_departments(filename, url, count):
    rows = parse_list((FIXTURES / filename).read_text(encoding='utf-8'), url)
    assert len(rows) == count
    assert all(r['title'] and r['source_post_id'].isdigit() and r['posted_at'] for r in rows)


@pytest.mark.parametrize('filename', ['경상대학_빈목록.html', '경상대학 자율학부_빈목록.html'])
def test_confirmed_empty(filename):
    assert parse_list((CMS / filename).read_text(encoding='utf-8'), LIST_URL) == []


@pytest.mark.parametrize('html', [
    '<html>접근 차단</html>', '<div class="board_list"><table><tbody></tbody></table></div>',
    '<div class="board_list"><table><tbody><tr><td class="subject">깨진 행</td></tr></tbody></table></div>',
])
def test_broken_list_is_not_empty(html):
    with pytest.raises(ParseError):
        parse_list(html, LIST_URL)


def test_bad_id_date_and_duplicate():
    html = (CMS / '국어국문학과_목록.html').read_text(encoding='utf-8')
    with pytest.raises(ParseError):
        parse_list(html.replace('mv_data=', 'broken='), LIST_URL)
    with pytest.raises(ParseError):
        parse_list(html.replace('2026-08-24', '2026-02-30'), LIST_URL)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    row = soup.select_one('.board_list tbody tr')
    row.insert_after(BeautifulSoup(str(row), 'html.parser').tr)
    assert len(parse_list(str(soup), LIST_URL)) == 19


@pytest.mark.parametrize('body,attach,status', [
    ('<p>신<span>입</span>생<br>안내</p>', '', 'text'),
    ('<img src="notice.png">', '', 'image-only'),
    ('', '<a href="file.pdf">안내.pdf</a>', 'attachment-only'),
    ('<object data="file.pdf">뷰어 안내</object>', '', 'needs-review'),
    ('', '', 'empty'),
])
def test_body_status(body, attach, status):
    html = f'<div class="board_view"><div class="title">제목</div><div class="desc"><dl><dt>등록일</dt><dd>2026-09-30</dd></dl></div><div class="cont">{body}</div><div class="attach">{attach}</div></div>'
    detail = parse_detail(html, DETAIL_URL)
    assert detail['body_status'] == status
    if status == 'text':
        assert detail['body'] == '신입생\n안내'
    elif status == 'empty':
        assert detail['body'] == ''
    else:
        assert detail['body'] is None


def test_broken_detail_and_mismatch():
    with pytest.raises(ParseError):
        parse_detail('<div class="board_view"><div class="title">제목</div></div>', DETAIL_URL)
    rows, detail = sample()
    with pytest.raises(ParseError):
        to_notice(dict(rows[0], source_post_id='9999'), detail, board_id='korean', channel_ids=['korean'])


def test_nested_board_view_does_not_override_outer_posted_date():
    from bs4 import BeautifulSoup

    folder = CMS / 'gugak-1533-detail.html'
    meta = json.loads((CMS / 'gugak-1533-metadata.json').read_text(encoding='utf-8'))
    html = folder.read_text(encoding='utf-8')
    detail = parse_detail(html, meta['requested_url'])
    assert detail['source_post_id'] == '1533'
    assert detail['posted_at'] == '2026-08-25'
    assert detail['body_status'] == 'text' and '2026-08-06' in detail['body']

    soup = BeautifulSoup(html, 'html.parser')
    view = soup.select_one('.board_view')
    outer_description = view.select_one(':scope > .desc')
    missing = BeautifulSoup(str(soup), 'html.parser')
    missing.select_one('.board_view > .desc').decompose()
    with pytest.raises(ParseError):
        parse_detail(str(missing), meta['requested_url'])

    outer_description.insert_after(BeautifulSoup(str(outer_description), 'html.parser').div)
    with pytest.raises(ParseError):
        parse_detail(str(soup), meta['requested_url'])


@pytest.mark.parametrize('prefix', ['english-3439', 'english-1662', 'math-3320', 'math-2163', 'math-1688', 'math-815'])
def test_real_truncated_titles_match_and_do_not_force_daily_recheck(prefix):
    from datetime import datetime
    from collector.run import needs_detail
    folder = CMS / 'mismatches'
    entry = next(e for e in json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))['entries'] if e['prefix'] == prefix)
    rows = parse_list((folder / (prefix + '-list.html')).read_text(encoding='utf-8'), entry['list_url'])
    item = next(r for r in rows if r['source_post_id'] == entry['post_id'])
    detail = parse_detail((folder / (prefix + '-detail.html')).read_text(encoding='utf-8'), entry['detail_url'])
    notice = to_notice(item, detail, board_id='test-board', channel_ids=['test-channel'])
    assert notice['title'] == entry['detail_title'] and item['title'].endswith('..')
    previous = dict(notice, last_checked_at='2026-10-01T10:00:00+09:00')
    assert not needs_detail(item, previous, datetime.fromisoformat('2026-10-01T10:00:00+09:00'))
    with pytest.raises(ParseError):
        to_notice(dict(item, title='전혀 다른 제목..'), detail, board_id='test-board', channel_ids=['test-channel'])
    with pytest.raises(ParseError):
        to_notice(dict(item, posted_at='2026-10-01'), detail, board_id='test-board', channel_ids=['test-channel'])
