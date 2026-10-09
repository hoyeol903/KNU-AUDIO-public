from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from bs4 import BeautifulSoup
import pytest

from collector import run, public_notices as parser
from collector.http import FetchError
from collector.knu_cms import ParseError, to_notice
from collector.store import load_notices

FIXTURES = Path(__file__).parent / 'fixtures'
SCHOOL = dict(id='knu-academic', source_url=run.PUBLIC_SOURCES['knu-academic'][1], template='knu-wbbs', collection_enabled=True)
SEE = dict(id='notice-df44dd8507c1', source_url=run.PUBLIC_SOURCES['notice-df44dd8507c1'][1], template='gt-board', collection_enabled=True)


def html(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


def test_school_ids_dedup_dates_and_next_page():
    rows = parser.parse_school_list(html('학교공지_목록.html'), SCHOOL['source_url'])
    assert len(rows) == 16 and len({r['source_post_id'] for r in rows}) == 16
    assert rows[0]['source_post_id'] == '11790744244900' and rows[0]['pinned']
    assert rows[0]['posted_at'] == '2026-09-30'
    next_url = parser.school_next_page(html('학교공지_목록.html'), SCHOOL['source_url'])
    query = parse_qs(urlsplit(next_url).query)
    assert query['menu_idx'] == ['42'] and query['pageIndex'] == query['page'] == ['2']
    page2 = parser.parse_school_list(html('학교공지_목록_2페이지.html'), next_url)
    assert rows[0]['source_post_id'] == page2[0]['source_post_id']
    assert {r['source_post_id'] for r in page2} != {r['source_post_id'] for r in rows}
    with pytest.raises(ParseError):
        parser.parse_school_list(html('학교공지_목록.html').replace('stu_812', 'other'), SCHOOL['source_url'])


@pytest.mark.parametrize('channel,list_file,detail_file,post_id,status', [
    (SCHOOL,'학교공지_목록.html','학교공지_상세.html','11790744244900','text'),
    (SEE,'전자공학부공지_목록.html','전자공학부공지_상세.html','105658','image-only'),
    (SEE,'전자공학부공지_목록.html','전자공학부공지_상세_텍스트.html','105657','text'),
])
def test_saved_detail_matches_list_and_roundtrip_store(tmp_path,channel,list_file,detail_file,post_id,status):
    list_parser = parser.parse_school_list if channel is SCHOOL else parser.parse_see_list
    detail_parser = parser.parse_school_detail if channel is SCHOOL else parser.parse_see_detail
    rows = list_parser(html(list_file),channel['source_url'])
    item = next(r for r in rows if r['source_post_id'] == post_id)
    detail = detail_parser(html(detail_file),item['url'])
    notice = to_notice(item,detail,board_id=run.board_id_for(channel),channel_ids=[channel['id']])
    assert notice['posted_at']=='2026-09-30' and detail['body_status']==status and detail['attachments']
    assert notice['deadline'] is None
    if status=='image-only': assert notice['body'] is None
    if post_id=='105657':
        assert '10월 12일(월) 15시까지' in notice['body']
        assert notice['title']=='2026년도 SW연계 부전공 이수자 설문 조사'
    from collector.store import upsert_notices
    path=tmp_path/'notices.json'
    first=upsert_notices([notice],path=path)
    assert first['new']==[run.board_id_for(channel)+':'+post_id]
    assert upsert_notices([notice],path=path)['unchanged']==first['new']
    with pytest.raises(ParseError):
        to_notice(dict(item,posted_at='2026-09-29'),detail,board_id=run.board_id_for(channel),channel_ids=[channel['id']])


def test_see_paging_and_titles():
    rows=parser.parse_see_list(html('전자공학부공지_목록.html'),SEE['source_url'])
    assert len(rows)==31 and rows[0]['pinned']
    assert rows[0]['title']=='2026학년도 2학기 재학생 등록금 수납 계획 안내'
    next_url=parser.see_next_page(html('전자공학부공지_목록.html'),SEE['source_url'])
    assert parse_qs(urlsplit(next_url).query)['page']==['2']
    page2=parser.parse_see_list(html('전자공학부공지_목록_2페이지.html'),next_url)
    assert len(page2)==31 and page2[0]['source_post_id']==rows[0]['source_post_id']


def test_see_list_recovers_decoded_query_delimiter_but_rejects_bad_id():
    source=html('전자공학부공지_목록.html')
    for listing in (source,source.replace('&gtid=notice','>id=notice')):
        rows=parser.parse_see_list(listing,SEE['source_url'])
        detail=next(row for row in rows if row['source_post_id']=='105426')
        query=parse_qs(urlsplit(detail['url']).query)
        assert query['fidx']==['105426'] and query['gtid']==['notice']
    malformed=source.replace('fidx=105426','fidx=bad-id',1)
    with pytest.raises(ParseError):
        parser.parse_see_list(malformed,SEE['source_url'])


@pytest.mark.parametrize('channel,prefix', [(SCHOOL,'학교공지'),(SEE,'전자공학부공지')])
def test_collect_dispatch_two_pages_and_partial_failure(tmp_path,channel,prefix):
    list_parser=parser.parse_school_list if channel is SCHOOL else parser.parse_see_list
    page_parser=parser.school_next_page if channel is SCHOOL else parser.see_next_page
    first=html(prefix+'_목록.html')
    second=BeautifulSoup(html(prefix+'_목록_2페이지.html'),'html.parser')
    second.select_one('.paging').clear()
    second.select_one('.paging').append(BeautifulSoup('<strong>2</strong>','html.parser'))
    following=page_parser(first,channel['source_url'])
    sample_id='11790744244900' if channel is SCHOOL else '105658'
    detail_file='학교공지_상세.html' if channel is SCHOOL else '전자공학부공지_상세.html'
    class Client:
        def get(self,url):
            if url==channel['source_url']: return first,url
            if url==following: return str(second),url
            key='bltn_no' if channel is SCHOOL else 'fidx'
            if parse_qs(urlsplit(url).query).get(key)==[sample_id]: return html(detail_file),url
            raise FetchError('오프라인 테스트의 일부 상세 실패')
    path=tmp_path/'notices.json'
    report=run.collect(Client(),channel,db_path=path)
    assert report['pages']==2 and not report['truncated'] and report['successful']==1
    expected={r['source_post_id'] for r in list_parser(first,channel['source_url'])+list_parser(str(second),following)}
    assert report['listed']==len(expected) and len(report['errors'])==len(expected)-1
    assert load_notices(path)[0]['id']==run.board_id_for(channel)+':'+sample_id
    assert report['new_candidates']==[]


def test_missing_structure_is_an_error_and_confirmed_empty_is_not():
    for parse,channel in [(parser.parse_school_list,SCHOOL),(parser.parse_see_list,SEE)]:
        with pytest.raises(ParseError): parse('<html>로그인</html>',channel['source_url'])
    empty='<table title="학사 공지사항"><tbody><tr><td>등록된 게시물이 없습니다.</td></tr></tbody></table>'
    assert parser.parse_school_list(empty,SCHOOL['source_url'])==[]
    with pytest.raises(ParseError): parser.parse_school_list(empty.replace('등록된 게시물이 없습니다.','구조 변경'),SCHOOL['source_url'])
    with pytest.raises(ParseError): parser.parse_see_detail('<html></html>',SEE['source_url']+'?fidx=1')


def test_public_selection_does_not_join_cms_only_flag():
    channels=[dict(c,classification='required',name=c['id']) for c in [SCHOOL,SEE]]
    assert len(run.select_channels(channels,[SCHOOL['id'],SEE['id']]))==2
    assert run.select_channels(channels,required_all=True)==[]
    with pytest.raises(ValueError):
        run.select_channels([dict(channels[0],source_url=channels[0]['source_url']+'&page=2')],[SCHOOL['id']])
