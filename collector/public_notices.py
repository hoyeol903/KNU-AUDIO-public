"""학교 학사공지와 전자공학부 공개 HTML. 저장·HTTP는 기존 수집 흐름 사용."""
import copy
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit, urlencode

from bs4 import BeautifulSoup

from collector.knu_cms import ParseError, _text, _date, _url, read_body, next_page

SCHOOL_LIST = 'table[title="학사 공지사항"]'
SCHOOL_LINK = 'td.subject a[href]'
SCHOOL_DATE = 'td.date'
SCHOOL_VIEW = '.board_view'
SCHOOL_TITLE = 'h2'
SCHOOL_POSTED = '.board_info dd.date'
SCHOOL_BODY = '.board_cont'
SEE_LIST = 'table[summary="게시판 목록 입니다."]'
SEE_LINK = 'td.left a[href]'
SEE_VIEW = 'table[summary="게시판 보기입니다."]'
SEE_TITLE = 'td.subject'
SEE_BODY = 'td.contentview'
PAGING = '.paging'
EMPTY_TEXTS = {'등록된 게시물이 없습니다.', '등록된 내용이 없습니다.', '게시물이 없습니다.'}


def _query_id(url, key):
    values = parse_qs(urlsplit(url).query).get(key, [])
    if len(values) != 1 or not values[0].isdigit():
        raise ParseError('원문 글 ID를 읽을 수 없습니다')
    return values[0]


def _deduplicate(items):
    result = {}
    for item in items:
        old = result.get(item['source_post_id'])
        if old and (old['title'], old['posted_at']) != (item['title'], item['posted_at']):
            raise ParseError('같은 글 ID의 목록 내용이 다릅니다')
        if old:
            old['pinned'] |= item['pinned']
        else:
            result[item['source_post_id']] = item
    return list(result.values())


def parse_school_list(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(SCHOOL_LIST)
    if root is None or not root.select('tbody tr'):
        raise ParseError('학교 학사공지 목록 구조가 없습니다')
    items = []
    for row in root.select('tbody tr'):
        link, posted = row.select_one(SCHOOL_LINK), row.select_one(SCHOOL_DATE)
        if not link or posted is None:
            if _text(row) in EMPTY_TEXTS:
                continue
            raise ParseError('학교 공지의 제목·날짜 구조가 없습니다')
        match = re.fullmatch(r"javascript:doRead\('([a-z0-9_]+)',\s*'(top|row)',\s*'([0-9]+)'\);?", link['href'])
        if not match or match[1] != 'stu_812' or not _text(link):
            raise ParseError('학교 학사공지 상세 링크를 읽을 수 없습니다')
        query = urlencode(dict(menu_idx='42', bbs_cde=match[1], note_div=match[2], bltn_no=match[3]))
        detail = _url(url, 'stdViewBtin.action?' + query)
        items.append(dict(source_post_id=match[3], title=_text(link), posted_at=_date(_text(posted)),
                          url=detail, pinned=row.select_one('td.notice') is not None))
    return _deduplicate(items)


def school_next_page(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(PAGING)
    current = root.select_one('strong') if root else None
    if current is None or not _text(current).isdigit():
        raise ParseError('학교 공지 페이지 번호가 없습니다')
    number = int(_text(current))
    targets = []
    for link in root.select('a[href]'):
        value = parse_qs(urlsplit(link['href']).query).get('pageIndex', [])
        if len(value) == 1 and value[0].isdigit():
            targets.append(int(value[0]))
    if number + 1 not in targets:
        if any(t > number for t in targets):
            raise ParseError('학교 공지 다음 페이지를 읽을 수 없습니다')
        return None
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    query.update(menu_idx=['42'], page=[str(number + 1)], pageIndex=[str(number + 1)])
    return urlunsplit(parts._replace(query=urlencode(query, doseq=True)))


def parse_see_list(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(SEE_LIST)
    if root is None or not root.select('tbody tr'):
        raise ParseError('전자공학부 목록 구조가 없습니다')
    items = []
    for row in root.select('tbody tr'):
        link = row.select_one(SEE_LINK)
        cells = row.find_all('td', recursive=False)
        if link is None or len(cells) != 5:
            if _text(row) in EMPTY_TEXTS:
                continue
            raise ParseError('전자공학부 제목·날짜 구조가 없습니다')
        title = copy.copy(link)
        for tag in title.find_all('span', recursive=False):
            tag.decompose()  # 카테고리와 NEW 표시를 제목에 붙이지 않는다.
        # BeautifulSoup 4.15 may decode the legacy `&gtid` text into `>id`.
        href = link['href'].replace('>id=notice', '&gtid=notice')
        detail = _url(url, href)
        if urlsplit(detail).hostname != 'see.knu.ac.kr' or urlsplit(detail).path != '/content/board/notice.html' or not _text(title):
            raise ParseError('전자공학부 상세 주소가 다릅니다')
        items.append(dict(source_post_id=_query_id(detail, 'fidx'), title=_text(title),
                          posted_at=_date(_text(cells[3])), url=detail,
                          pinned=cells[0].select_one('.notice') is not None))
    return _deduplicate(items)


def _detail(root, title_selector, body_selector, posted, url, post_id, attachment_selector):
    title = root.select_one(title_selector) if root else None
    content = root.select_one(body_selector) if root else None
    if title is None or not _text(title) or content is None:
        raise ParseError('상세 제목·본문 구조가 없습니다')
    attachments = [dict(name=_text(a), url=_url(url, a['href'])) for a in root.select(attachment_selector)]
    body, status = read_body(content, attachments)
    return dict(source_post_id=post_id, title=_text(title), posted_at=posted, url=_url(url, url),
                deadline=None, body=body, body_status=status, attachments=attachments)


def parse_school_detail(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(SCHOOL_VIEW)
    posted = root.select(SCHOOL_POSTED) if root else []
    if len(posted) != 1 or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}(?::\d{2})?)?', _text(posted[0])):
        raise ParseError('학교 공지 상세 게시일 구조가 없습니다')
    return _detail(root, SCHOOL_TITLE, SCHOOL_BODY, _date(_text(posted[0]).split()[0]), url,
                   _query_id(url, 'bltn_no'), '.attach a[href]')


def parse_see_detail(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(SEE_VIEW)
    posted = []
    if root:
        for label in root.select('th[scope="row"]'):
            if _text(label) == '작성일':
                value = label.find_next_sibling('td')
                if value is not None:
                    posted.append(_date(_text(value)))
    if len(posted) != 1:
        raise ParseError('전자공학부 상세 게시일 구조가 없습니다')
    return _detail(root, SEE_TITLE, SEE_BODY, posted[0], url, _query_id(url, 'fidx'), 'td.addfile a[href]')


see_next_page = next_page
