"""KNU CMS의 저장된 HTML 파싱. 네트워크 요청과 JSON 쓰기는 하지 않는다."""
import base64
import binascii
import re
from datetime import date
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

LIST = '.board_list'
ROWS = 'tbody tr'
TITLE_LINK = 'td.subject a[href]'
POSTED = 'td.date'
HEADER_CELLS = 'thead tr th'
PINNED = 'td.notice'
EMPTY = '.list_nodata'
VIEW = '.board_view'
TITLE = '.title'
LEGACY_TITLE = ':scope > h2'
LEGACY_LABELS = 'table th[scope="row"]'
DESCRIPTION = ':scope > .desc dl'
BODY = '.cont'
ATTACHMENTS = '.attach a[href]'
BLOCKS = 'p, div, li, tr, h1, h2, h3, h4, blockquote'
PAGING = '.paging'
PAGE_LINKS = 'a[href]'
CURRENT_PAGE = 'strong'
NEXT_GROUP = 'a.next[href]'


class ParseError(ValueError):
    """접근 성공과 파싱 성공을 구분하기 위한 오류."""


def _text(node):
    return re.sub(r'\s+', ' ', node.get_text()).strip()


def _url(base, href):
    result = urljoin(base, href)
    parsed = urlsplit(result)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or re.search(r'\s', result):
        raise ParseError('HTTP(S) 원문 링크가 아닙니다')
    return result


def post_id(url):
    """화면 순번 listNo가 아닌 mv_data 안의 idx를 사용한다."""
    try:
        encoded, = parse_qs(urlsplit(url).query)['mv_data']
        decoded = base64.b64decode(encoded + '=' * (-len(encoded) % 4), validate=True).decode('utf-8')
        value, = parse_qs(decoded)['idx']
        if not re.fullmatch(r'[0-9]+', value):
            raise ValueError('숫자가 아닌 idx')
        return value
    except (KeyError, ValueError, UnicodeError, binascii.Error) as exc:
        raise ParseError('원문 글 ID를 읽을 수 없습니다') from exc


def _date(value):
    if not value:
        return None
    if re.fullmatch(r'\d{4}/\d{2}/\d{2}', value):
        value = value.replace('/', '-')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ParseError('게시일 형식을 읽을 수 없습니다')
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ParseError('잘못된 게시일') from exc
    return value


def title_matches(list_title, full_title):
    """CMS 목록의 '..' 표시를 제거한 제목이 상세 제목의 접두부인지 확인한다."""
    return list_title == full_title or (list_title.endswith('..') and
        bool(list_title[:-2]) and full_title.startswith(list_title[:-2]))


def parse_list(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(LIST)
    if root is None:
        raise ParseError('공지 목록 구조가 없습니다')
    result = {}
    headers = [_text(header) for header in root.select(HEADER_CELLS)]
    rows = root.select(ROWS)
    for row in rows:
        link, posted = row.select_one(TITLE_LINK), row.select_one(POSTED)
        if posted is None and headers.count('등록일') == 1:
            cells = row.find_all('td', recursive=False)
            if len(cells) == len(headers):
                posted = cells[headers.index('등록일')]
        if link is None or posted is None:
            empty = row.select_one(EMPTY)
            if empty is not None and _text(empty) == '등록된 내용이 없습니다.':
                continue
            raise ParseError('공지 행의 제목·게시일 구조가 없습니다')
        title = _text(link)
        if not title:
            raise ParseError('공지 제목이 비었습니다')
        detail_url = _url(url, link['href'])
        item = dict(source_post_id=post_id(detail_url), title=title,
                    posted_at=_date(_text(posted)), url=detail_url,
                    pinned=row.select_one(PINNED) is not None)
        previous = result.get(item['source_post_id'])
        if previous and (previous['posted_at'] != item['posted_at'] or not
                         (title_matches(previous['title'], item['title']) or title_matches(item['title'], previous['title']))):
            raise ParseError('동일 글 ID의 목록 내용이 서로 다릅니다')
        if previous:
            previous['pinned'] = previous['pinned'] or item['pinned']
        else:
            result[item['source_post_id']] = item
    if not result and not (rows and root.select_one(EMPTY) and
                           _text(root.select_one(EMPTY)) == '등록된 내용이 없습니다.'):
        raise ParseError('빈 게시판 표식을 확인할 수 없습니다')
    if result and root.select_one(EMPTY):
        raise ParseError('공지 행과 빈 게시판 표식이 함께 있습니다')
    return list(result.values())


def parse_detail(html, url):
    root = BeautifulSoup(html, 'html.parser').select_one(VIEW)
    if root is None:
        raise ParseError('공지 상세 구조가 없습니다')
    title = root.select_one(TITLE) or root.select_one(LEGACY_TITLE)
    content = root.select_one(BODY)
    if title is None or not _text(title) or content is None:
        raise ParseError('상세 제목·본문 구조가 없습니다')
    posted = []
    for description in root.select(DESCRIPTION):
        label, value = description.find('dt'), description.find('dd')
        if label is not None and _text(label) == '등록일' and value is not None:
            posted.append(_date(_text(value)))
    attachments = [dict(name=_text(a), url=_url(url, a['href'])) for a in root.select(ATTACHMENTS)]
    if not root.select(DESCRIPTION):
        for label in root.select(LEGACY_LABELS):
            value = label.find_next_sibling('td')
            if value is None:
                continue
            if _text(label) in {'작성일', '작성일.'}:
                posted.append(_date(_text(value)))
            elif _text(label) == '첨부파일':
                attachments.extend(dict(name=_text(a), url=_url(url, a['href'])) for a in value.select('a[href]'))
    if len(posted) != 1:
        raise ParseError('상세 게시일을 확인할 수 없습니다')
    body, status = read_body(content, attachments)
    return dict(source_post_id=post_id(url), title=_text(title), url=_url(url, url),
                posted_at=posted[0], deadline=None,
                body=body, body_status=status, attachments=attachments)


def read_body(content, attachments):
    """원문 본문만 읽고 이미지·첨부 전용 상태를 구분한다."""
    has_image = bool(content.select('img, svg, canvas'))
    has_embed = bool(content.select('object, iframe, embed'))
    # PDF 뷰어의 Acrobat 설치 안내는 공지 본문이 아니다.
    for node in content.select('script, style, object, iframe, embed'):
        node.decompose()
    for node in content.select('br'):
        node.replace_with('\n')
    for node in content.select(BLOCKS):
        node.append('\n')
    lines = [re.sub(r'\s+', ' ', line).strip() for line in content.get_text().splitlines()]
    body = '\n'.join(line for line in lines if line)
    status = 'text' if body else ('needs-review' if has_embed else 'image-only' if has_image
                                 else 'attachment-only' if attachments else 'empty')
    return body if status in {'text', 'empty'} else None, status


def to_notice(list_item, detail, *, board_id, channel_ids):
    """동일 글 확인 후 store 입력으로 변환. 첨부 링크는 상세 결과에 유지한다."""
    if list_item['source_post_id'] != detail['source_post_id']:
        raise ParseError('목록과 상세의 글 ID가 다릅니다')
    if list_item['posted_at'] != detail['posted_at'] or not title_matches(list_item['title'], detail['title']):
        raise ParseError('목록과 상세 내용이 달라 재확인이 필요합니다')
    return {key: value for key, value in detail.items() if key != 'attachments'} | {
        'source_board_id': board_id, 'channel_ids': channel_ids,
    }




def next_page(html, url):
    """바로 다음 번호를 우선하며 묶음 경계에서만 next를 따른다."""
    root = BeautifulSoup(html, 'html.parser').select_one(PAGING)
    if root is None:
        raise ParseError('페이지 이동 구조가 없습니다')
    current = root.select_one(CURRENT_PAGE)
    if current is None or not _text(current).isdigit():
        raise ParseError('현재 페이지 번호를 읽을 수 없습니다')
    number = int(_text(current))
    target = str(number + 1)
    for link in root.select(PAGE_LINKS):
        if _text(link) == target:
            result = _url(url, link['href'])
            if urlsplit(result).netloc != urlsplit(url).netloc or urlsplit(result).path != urlsplit(url).path:
                raise ParseError('다른 게시판으로 이동하는 페이지 링크')
            return result
    # 페이지 묶음 경계에서는 next가 바로 다음 묶음의 첫 페이지다.
    link = root.select_one(NEXT_GROUP)
    if link is not None:
        result = _url(url, link['href'])
        if urlsplit(result).netloc != urlsplit(url).netloc or urlsplit(result).path != urlsplit(url).path:
            raise ParseError('다른 게시판으로 이동하는 페이지 링크')
        return result
    if any(_text(a).isdigit() and int(_text(a)) > number for a in root.select(PAGE_LINKS)):
        raise ParseError('바로 다음 페이지 링크가 없습니다')
    return None
