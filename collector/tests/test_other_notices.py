from pathlib import Path
from urllib.parse import parse_qs,urlsplit
import yaml
import pytest
from bs4 import BeautifulSoup
from collector import run,other_notices as parser
from collector.knu_cms import ParseError,to_notice
from collector.http import FetchError
from collector.store import load_collection_report,load_notices,upsert_notices

ROOT=Path(__file__).resolve().parents[2]
SAMPLES=load_collection_report(ROOT/'data/remaining-validation.json')['channels']


def parsers(sample):
    if sample['template']=='gnuboard': return parser.parse_gnu_list,parser.parse_gnu_detail,parser.gnu_next_page
    if sample['template']=='med-cms': return parser.parse_med_list,parser.parse_med_detail,parser.med_next_page
    return parser.parse_dent_list,parser.parse_dent_detail,parser.dent_next_page


def read(path): return (ROOT/path).read_text(encoding='utf-8')


@pytest.mark.parametrize('sample',SAMPLES,ids=[s['channel_id'] for s in SAMPLES])
def test_real_list_detail_paging_and_store(sample,tmp_path):
    listing,detail,next_page=parsers(sample)
    rows=listing(read(sample['list_file']),sample['actual_url'])
    assert len(rows)==sample['listed']
    assert next_page(read(sample['list_file']),sample['actual_url'])==sample['next_url']
    second=listing(read(sample['page2_file']),sample['page2_url'])
    assert second and {r['source_post_id'] for r in rows}!={r['source_post_id'] for r in second}
    item=rows[0]
    parsed=detail(read(sample['detail_file']),sample['detail_url'],posted_at=item['posted_at']) if sample['template']=='gnuboard' else detail(read(sample['detail_file']),sample['detail_url'])
    notice=to_notice(item,parsed,board_id=sample['source_board_id'],channel_ids=[sample['channel_id']])
    assert notice['body_status']=='text' and notice['body'] and notice['deadline'] is None
    path=tmp_path/'notices.json'
    assert upsert_notices([notice],path=path)['new']==[sample['source_board_id']+':'+item['source_post_id']]
    assert upsert_notices([notice],path=path)['unchanged']
    with pytest.raises(ParseError): listing('<html>로그인</html>',sample['actual_url'])
    with pytest.raises(ParseError): detail('<html>구조 변경</html>',sample['detail_url'])
    with pytest.raises(ParseError): to_notice(dict(item,posted_at='2000-01-01'),parsed,board_id=sample['source_board_id'],channel_ids=[sample['channel_id']])


@pytest.mark.parametrize('sample',SAMPLES,ids=[s['channel_id'] for s in SAMPLES])
def test_collect_uses_new_parser_and_preserves_partial_results(sample,tmp_path):
    listing,_,_=parsers(sample)
    first=read(sample['list_file']); rows=listing(first,sample['actual_url'])
    class Client:
        def get(self,url):
            if url==sample['source_url']: return first,sample['actual_url']
            if url==rows[0]['url']: return read(sample['detail_file']),sample['detail_url']
            raise FetchError('일부 상세 실패 테스트')
    channel=dict(id=sample['channel_id'],template=sample['template'],source_url=sample['source_url'])
    path=tmp_path/'notices.json'
    report=run.collect(Client(),channel,db_path=path,max_pages=1,mode='start')
    assert report['truncated'] and report['successful']==1 and len(report['errors'])==len(rows)-1
    assert load_notices(path)[0]['id']==sample['source_board_id']+':'+rows[0]['source_post_id']


def test_short_year_requires_full_list_date_and_image_only_is_preserved():
    sample=next(s for s in SAMPLES if s['channel_id']=='notice-6b04da14aae1')
    html=read(sample['detail_file'])
    with pytest.raises(ParseError): parser.parse_gnu_detail(html,sample['detail_url'])
    with pytest.raises(ParseError): parser.parse_gnu_detail(html,sample['detail_url'],posted_at='2026-07-23')
    soup=BeautifulSoup(html,'html.parser');soup.select_one('#bo_v_con').clear()
    soup.select_one('#bo_v_img').append(BeautifulSoup('<img src="poster.png">','html.parser'))
    parsed=parser.parse_gnu_detail(str(soup),sample['detail_url'],posted_at='2026-07-22')
    assert parsed['body_status']=='image-only' and parsed['body'] is None and parsed['attachments']


def test_page_boundary_terminal_and_wrong_board():
    for sample in SAMPLES:
        if sample['template']=='med-cms': continue
        _,_,next_page=parsers(sample)
        soup=BeautifulSoup(read(sample['list_file']),'html.parser')
        key='page' if sample['template']=='gnuboard' else 'gotoPage'
        container=soup.select_one('.pg_wrap' if key=='page' else '.paging')
        current=container.select_one('strong');current.string='10'
        assert parse_qs(urlsplit(next_page(str(soup),sample['actual_url'])).query)[key]==['11']
        for a in list(container.select('a[href]')):
            if a.select_one('strong'): a.unwrap()
            else:a.decompose()
        assert next_page(str(soup),sample['actual_url']) is None
        container.append(BeautifulSoup('<a href="https://evil.example/board.php?page=11">11</a>','html.parser'))
        with pytest.raises(ParseError): next_page(str(soup),sample['actual_url'])


def test_shared_computer_and_ai_board_and_selection():
    a,b=[next(s for s in SAMPLES if s['channel_id']==id) for id in ['notice-b34ee1a00417','notice-fefffa32e24c']]
    for suffix in ['list','page2']:
        left=parser.parse_gnu_list(read(a[suffix+'_file']),a['actual_url'])
        right=parser.parse_gnu_list(read(b[suffix+'_file']),b['actual_url'])
        assert [(r['source_post_id'],r['title'],r['posted_at'],r['pinned']) for r in left]==[(r['source_post_id'],r['title'],r['posted_at'],r['pinned']) for r in right]
    ad=parser.parse_gnu_detail(read(a['detail_file']),a['detail_url'],posted_at='2026-09-30')
    bd=parser.parse_gnu_detail(read(b['detail_file']),b['detail_url'],posted_at='2026-09-30')
    assert all(ad[k]==bd[k] for k in ('source_post_id','title','posted_at','body','body_status'))
    channels=yaml.safe_load((ROOT/'data/channels.yaml').read_text())
    grouped=run.select_channels(channels,list(run.OTHER_SOURCES))
    assert len(grouped)==5 and sum(len(c['channel_ids']) for c in grouped)==6
    wrong=dict(next(c for c in channels if c['id']==a['channel_id']),source_url='https://aicollege.knu.ac.kr/bbs/board.php?bo_table=other')
    with pytest.raises(ValueError): run.select_channels([wrong],[wrong['id']])


def test_medical_ellipsis_added_to_full_title():
    from collector.knu_cms import title_matches
    sample=next(s for s in SAMPLES if s['template']=='med-cms')
    rows=parser.parse_med_list(read(sample['list_file']),sample['actual_url'])
    fixtures=ROOT/'collector/tests/fixtures/remaining/med-mismatches'
    for file in load_collection_report(fixtures/'metadata.json')['files']:
        detail=parser.parse_med_detail(read(file['file']),file['url'])
        item=next(r for r in rows if r['source_post_id']==detail['source_post_id'])
        assert item['title']==detail['title']+'..'
        to_notice(item,detail,board_id=sample['source_board_id'],channel_ids=[sample['channel_id']])
    assert not title_matches('..','다른 제목')
    assert not title_matches('안내..','다른 안내')
    assert title_matches('안내..','안내') and title_matches('안내..','안내합니다')
