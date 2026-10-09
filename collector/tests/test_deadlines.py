from pathlib import Path
from datetime import datetime
import pytest

from collector.deadlines import extract_deadline, backfill
from collector import store,run
from collector.knu_cms import parse_detail
from collector.public_notices import parse_school_detail


@pytest.mark.parametrize('text,deadline,status', [
 ('신청마감: 2026. 10. 8.(목)까지','2026-10-08','found'),
 ('제출기한: 2027년 1월 8일','2027-01-08','found'),
 ('신청기간: 2026-09-30 09:00 ~ 2026-10-07 17:00','2026-10-07','found'),
 ('신청기간: 2026. 10. 7.(수) 17시까지','2026-10-07','found'),
 ('신청기간: ~2026/10/07','2026-10-07','found'),
 ('이수증 제출: 2026. 10. 6.(화)까지, 학과 사무실로 제출','2026-10-06','found'),
 ('2026년 10월 6일까지 제출 바랍니다.','2026-10-06','found'),
 ('제출기한:\n2026. 10. 7.(수)','2026-10-07','found'),
 ('신청마감: 2026-10-07\n제출기한: 2026-10-07','2026-10-07','found'),
 ('신청기간: 2026. 9. 30. ~ 10. 7.',None,'needs-review'),
 ('신청기한: 10월 7일까지',None,'needs-review'),
 ('신청기간: 2026-09-30',None,'needs-review'),
 ('신청기간: 2026-09-30 ~ 모집인원 마감까지',None,'needs-review'),
 ('신청기한: 2026-10-07\n선착순 마감입니다.',None,'needs-review'),
 ('신청마감: 2026-10-07\n제출기한: 2026-10-08',None,'needs-review'),
 ('신청기한: 2026-02-30',None,'needs-review'),
 ('신청기간: 2027-01-02 ~ 2026-12-31',None,'needs-review'),
 ('신청기간: 2026-10-01 ~ 2026-10-07, 10.8. ~ 10.9.',None,'needs-review'),
 ('신청마감: 2026-10-07, 행사일 2026-10-10',None,'needs-review'),
 ('신청기간: 2026-09-30 ~ 2027-01-07','2027-01-07','found'),
 ('행사기간: 2026-10-01 ~ 2026-10-07',None,'not-found'),
 ('2026-10-07 강의 안내. 신청은 홈페이지에서 합니다.',None,'not-found'),
 ('제출기한: 추후 안내',None,'needs-review'),
 ('제출기한: 26.10.07.',None,'needs-review'),
 ('제출기한: 2026-10-01부터 2주 후',None,'needs-review'),
 ('제출기한: 2026-10-01 이후',None,'needs-review'),
 ('제출기한: 2026-10-01 익일',None,'needs-review'),
 ('신청기한: 2026-10-01로부터 7일 이내',None,'needs-review'),
])
def test_explicit_end_dates_and_ambiguous_cases(text,deadline,status):
    result=extract_deadline('2026학년도 안내',text)
    assert result['deadline']==deadline and result['status']==status
    if status=='found': assert result['evidence'] and result['reason'] is None
    if status=='needs-review': assert result['deadline'] is None and result['reason']


def notice(id='1',deadline=None):
    return dict(source_board_id='knu-test-notice',source_post_id=id,channel_ids=['notice-test'],
                title='신청 안내',url='https://example.com/post/'+id,posted_at='2026-09-30',
                deadline=deadline,body='신청마감: 2026. 10. 8.(목)까지',body_status='text')


def test_backfill_is_idempotent_preserves_timestamps_and_existing_deadlines(tmp_path):
    path=tmp_path/'notices.json'
    store.upsert_notices([notice(),notice('2','2026-10-09')],path=path,checked_at='2026-10-01T05:37:00+09:00')
    before=store.load_notices(path)
    preview=backfill(db_path=path)
    assert preview['proposed']==1 and preview['updated']==[] and store.load_notices(path)==before
    result=backfill(db_path=path,apply=True,report_path=tmp_path/'report.json')
    after=store.load_notices(path)
    assert result['updated']==['knu-test-notice:1'] and after[0]['deadline']=='2026-10-08'
    assert after[0]['content_hash']!=before[0]['content_hash']
    for key in store.STORED_FIELDS-{'deadline','content_hash'}: assert after[0][key]==before[0][key]
    assert after[1]==before[1]
    assert backfill(db_path=path,apply=True)['updated']==[]
    original=path.read_bytes()
    with pytest.raises(ValueError): store.update_deadlines({'knu-test-notice:1':'2026-10-10','knu-test-notice:2':'2026-02-30'},path=path)
    assert path.read_bytes()==original
    with pytest.raises(ValueError): store.update_deadlines({'unknown:1':'2026-10-10'},path=path)


def test_real_school_fixture_and_collector_integration(tmp_path,monkeypatch):
    root=Path(__file__).parent/'fixtures'
    detail_html=(root/'학교공지_상세.html').read_text()
    from collector.public_notices import parse_school_list
    url=run.PUBLIC_SOURCES['knu-academic'][1]
    rows=parse_school_list((root/'학교공지_목록.html').read_text(),url)
    item=next(r for r in rows if r['source_post_id']=='11790744244900')
    detail=parse_school_detail(detail_html,item['url'])
    assert extract_deadline(detail['title'],detail['body'])['deadline']=='2026-10-06'
    class Client:
        def get(self,u): return detail_html,u
    from collector import public_notices
    monkeypatch.setattr(public_notices,'parse_school_list',lambda *a:[item])
    monkeypatch.setattr(public_notices,'school_next_page',lambda *a:None)
    path=tmp_path/'notices.json'
    report=run.collect(Client(),dict(id='knu-academic',source_url=url),db_path=path,mode='start',now=datetime.fromisoformat('2026-10-01T05:37:00+09:00'))
    assert not report['errors'] and store.load_notices(path)[0]['deadline']=='2026-10-06'
    assert report['deadline_checks'][0]['evidence'] and report['deadline_checks'][0]['status']=='found'
