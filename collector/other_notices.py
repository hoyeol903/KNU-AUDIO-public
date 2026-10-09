"""검증한 그누보드·의대·치대 공개 공지 HTML. HTTP와 저장은 기존 흐름 사용."""
import base64
import binascii
import copy
import re
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from collector.knu_cms import ParseError, _text, _date, _url, read_body
from collector.public_notices import _query_id, _deduplicate, _detail

GNU_LIST = '#bo_list'
GNU_ROWS = 'tbody tr'
GNU_LINK = '.bo_tit > a[href*="wr_id="]'
GNU_DATE = '.td_datetime'
GNU_CARD_LIST = 'ol.brd_lst'
GNU_CARD_ROWS = ':scope > li'
GNU_CARD_TITLE = 'h2'
GNU_CARD_DATE = '.date'
GNU_VIEW = '#bo_v, #brd_view'
GNU_TITLE = '.bo_v_tit, header h1'
GNU_POSTED = '.if_date, .brd_info .date'
GNU_BODY = '#bo_v_con'
GNU_ATTACH = '#bo_v_file a[href], .brd_down a.view_file_download[href]'
GNU_PAGING = '.pg_wrap'
MED_LIST = '.board-list'
MED_VIEW = '.board-view'
MED_TITLE = '.board-view-title .subject'
MED_POSTED = '.board-view-title .date'
MED_BODY = '.board-view-cont .text'
MED_ATTACH = 'a[href*="bbs_download.php"]'
MED_PAGING = '.board-paging'
DENT_LIST = 'table.boardtable'
DENT_TITLE = '.view_top_tit'
DENT_POSTED = '.view_writer_info dl:last-child dd'
DENT_BODY = '.view_board_inner'
DENT_ATTACH = '.add_file a[href]'
DENT_PAGING = '.paging'
EMPTY_TEXTS = {'게시물이 없습니다.', '등록된 게시물이 없습니다.', '등록된 내용이 없습니다.'}


def _same_board(base, href, key):
    result = _url(base, href)
    a, b = urlsplit(base), urlsplit(result)
    if a.hostname != b.hostname or a.path != b.path or parse_qs(a.query).get(key) != parse_qs(b.query).get(key):
        raise ParseError('다른 게시판으로 이동하는 링크')
    return result


def parse_gnu_list(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one(GNU_LIST)
    cards = False
    if root is None:
        root = soup.select_one(GNU_CARD_LIST)
        cards = True
    if root is None:
        raise ParseError('그누보드 목록 구조가 없습니다')
    rows = root.select(GNU_CARD_ROWS if cards else GNU_ROWS)
    if not rows:
        raise ParseError('그누보드 목록 행이 없습니다')
    items = []
    for row in rows:
        link = row.select_one('a[href*="wr_id="]' if cards else GNU_LINK)
        posted = row.select_one(GNU_CARD_DATE if cards else GNU_DATE)
        title = copy.copy(row.select_one(GNU_CARD_TITLE)) if cards else copy.copy(link)
        if link is None or posted is None or title is None:
            if _text(row) in EMPTY_TEXTS:
                continue
            raise ParseError('그누보드 제목·게시일 구조가 없습니다')
        for node in title.select('.category, .sound_only, .new_icon'):
            node.decompose()
        detail_url = _same_board(url, link['href'], 'bo_table')
        if not _text(title):
            raise ParseError('그누보드 제목이 비었습니다')
        items.append(dict(source_post_id=_query_id(detail_url, 'wr_id'), title=_text(title),
                          posted_at=_date(_text(posted)), url=detail_url,
                          pinned=row.select_one('.notice_icon, .bo_notice, .td_num2 strong') is not None
                          or 'bo_notice' in row.get('class', [])))
    return _deduplicate(items)


def parse_gnu_detail(html, url, *, posted_at=None):
    root = BeautifulSoup(html, 'html.parser').select_one(GNU_VIEW)
    posted = root.select(GNU_POSTED) if root else []
    if len(posted) != 1:
        raise ParseError('그누보드 상세 게시일 구조가 없습니다')
    text = copy.copy(posted[0])
    for node in text.select('.sound_only, i'):
        node.decompose()
    value = _text(text)
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{2})(?: \d{2}:\d{2}(?::\d{2})?)?', value)
    if not match:
        raise ParseError('그누보드 상세 게시일 형식을 읽을 수 없습니다')
    stamp = match[1]
    if len(stamp) == 8:
        # 목록의 4자리 연도를 사용한다. 2자리 연도의 세기를 추측하지 않는다.
        if posted_at is None or _date(posted_at)[2:] != stamp:
            raise ParseError('상세의 2자리 연도를 목록 게시일과 대조할 수 없습니다')
        stamp = posted_at
    content = root.select_one(GNU_BODY)
    if content is not None:
        for img in root.select('#bo_v_img img'):
            content.append(copy.copy(img))
    return _detail(root, GNU_TITLE, GNU_BODY, _date(stamp), url, _query_id(url, 'wr_id'), GNU_ATTACH)


def _numbered_next(html, url, container, current_selector, key, board_key):
    root = BeautifulSoup(html, 'html.parser').select_one(container)
    current = root.select_one(current_selector) if root else None
    if current is None or not _text(current).isdigit():
        raise ParseError('현재 페이지 번호가 없습니다')
    number = int(_text(current))
    pages = {}
    for link in root.select('a[href]'):
        target = _same_board(url, link['href'], board_key)
        values = parse_qs(urlsplit(target).query).get(key, [])
        if len(values) != 1 or not values[0].isdigit():
            raise ParseError('페이지 링크 번호가 없습니다')
        pages[int(values[0])] = target
    if number + 1 in pages:
        return pages[number + 1]
    if any(n > number for n in pages):
        raise ParseError('바로 다음 페이지 링크가 없습니다')
    return None


def gnu_next_page(html, url):
    return _numbered_next(html, url, GNU_PAGING, '.pg_current', 'page', 'bo_table')


def _med_data(url):
    try:
        encoded, = parse_qs(urlsplit(url).query)['mv_data']
        if not encoded.endswith('||'):
            raise ValueError('의대 링크 구분자 누락')
        data = parse_qs(base64.b64decode(encoded[:-2], validate=True).decode('utf-8'))
        if data.get('nav_code') != ['knu1670583748'] or data.get('code') != ['notice001']:
            raise ValueError('다른 의대 게시판')
        return data
    except (KeyError, ValueError, UnicodeError, binascii.Error) as exc:
        raise ParseError('의대 원문 링크를 읽을 수 없습니다') from exc


def _med_id(url):
    values = _med_data(url).get('idx', [])
    if len(values) != 1 or not values[0].isdigit():
        raise ParseError('의대 원문 글 ID가 없습니다')
    return values[0]


def parse_med_list(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(MED_LIST)
    if root is None or not root.select('tbody tr'):
        raise ParseError('의대 목록 구조가 없습니다')
    items = []
    for row in root.select('tbody tr'):
        link, posted = row.select_one('td.subject a[href]'), row.select_one('td.date')
        if link is None or posted is None:
            if _text(row) in EMPTY_TEXTS:
                continue
            raise ParseError('의대 제목·날짜 구조가 없습니다')
        detail = _url(url, link['href'])
        if urlsplit(detail).hostname != 'med.knu.ac.kr' or urlsplit(detail).path != '/pages/sub.htm' or not _text(link):
            raise ParseError('의대 상세 주소·제목이 다릅니다')
        items.append(dict(source_post_id=_med_id(detail), title=_text(link), posted_at=_date(_text(posted)),
                          url=detail, pinned=row.select_one('.notice') is not None))
    return _deduplicate(items)


def med_next_page(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(MED_PAGING)
    current = root.select_one('a.active') if root else None
    if current is None or not _text(current).isdigit():
        raise ParseError('의대 현재 페이지 번호가 없습니다')
    number = int(_text(current))
    targets = {}
    for a in root.select('a[href]'):
        target = _url(url, a['href'])
        if urlsplit(target).hostname != urlsplit(url).hostname or urlsplit(target).path != '/pages/sub.htm':
            raise ParseError('의대 다른 게시판 페이지 링크')
        values = _med_data(target).get('startPage', [])
        if len(values) != 1 or not values[0].isdigit() or int(values[0]) % 10:
            raise ParseError('의대 페이지 시작 위치가 다릅니다')
        targets[int(values[0]) // 10 + 1] = target
    if number + 1 in targets:
        return targets[number + 1]
    if any(n > number for n in targets):
        raise ParseError('의대 바로 다음 페이지 링크가 없습니다')
    return None


def parse_med_detail(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(MED_VIEW)
    posted = root.select(MED_POSTED) if root else []
    if len(posted) != 1:
        raise ParseError('의대 상세 게시일 구조가 없습니다')
    return _detail(root, MED_TITLE, MED_BODY, _date(_text(posted[0])), url, _med_id(url), MED_ATTACH)


def parse_dent_list(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(DENT_LIST)
    if root is None or not root.select('tbody tr'):
        raise ParseError('치대 목록 구조가 없습니다')
    items = []
    for row in root.select('tbody tr'):
        link = row.select_one('td.tit a[href]')
        cells = row.find_all('td', recursive=False)
        if link is None or len(cells) != 4:
            if _text(row) in EMPTY_TEXTS:
                continue
            raise ParseError('치대 제목·날짜 구조가 없습니다')
        detail = _same_board(url, link['href'], 'bid')
        if not _text(link):
            raise ParseError('치대 제목이 비었습니다')
        items.append(dict(source_post_id=_query_id(detail, 'bno'), title=_text(link),
                          posted_at=_date(_text(cells[2])), url=detail,
                          pinned=cells[0].select_one('img[alt="NOTICE"]') is not None))
    return _deduplicate(items)


def dent_next_page(html, url):
    return _numbered_next(html, url, DENT_PAGING, 'strong', 'gotoPage', 'bid')


def parse_dent_detail(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(DENT_LIST)
    posted = root.select(DENT_POSTED) if root else []
    if len(posted) != 1:
        raise ParseError('치대 상세 게시일 구조가 없습니다')
    stamp = _date(_text(posted[0]))
    info = root.select_one('.view_writer_info')
    if info:
        info.decompose()
    return _detail(root, DENT_TITLE, DENT_BODY, stamp, url, _query_id(url, 'bno'), DENT_ATTACH)
