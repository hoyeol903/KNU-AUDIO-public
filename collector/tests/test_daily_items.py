from copy import deepcopy
from datetime import datetime
from pathlib import Path
import pytest

from collector.daily_items import build_items,discovery_reason
from collector import store

NOW=datetime.fromisoformat('2026-10-01T06:00:00+09:00')
BASE='2026-09-30T06:00:00+09:00'
CHANNELS=[dict(id='notice-a',name='학과 공지',source_board_id='knu-test')]
STATE={'boards':{'knu-test':dict(initialized_at=BASE,last_full_scan_at=BASE)}}


def row(id='1',**changes):
    return dict(id='knu-test:'+id,source_board_id='knu-test',source_post_id=id,
                channel_ids=['notice-a'],title='원문 제목',url='https://example.com/post/'+id,
                posted_at='2026-09-30',deadline=None,body='원문 본문',body_status='text',
                first_seen_at='2026-10-01T05:37:00+09:00',last_checked_at='2026-10-01T05:37:00+09:00',**changes)


def changed(**changes):
    r=row();r.update(changes);return r


@pytest.mark.parametrize('changes,reason',[
 ({},'new'),
 ({'deadline':'2026-10-04','first_seen_at':BASE},'reminder'),
 ({'deadline':'2026-10-02','first_seen_at':BASE},'reminder'),
 ({'deadline':'2026-10-01','first_seen_at':BASE},'reminder'),
 ({'deadline':'2026-10-03','first_seen_at':BASE},None),
 ({'deadline':'2026-10-04'},'new'),
 ({'deadline':'2026-09-30'},None),
 ({'first_seen_at':BASE},None),
 ({'posted_at':None},None),
 ({'posted_at':'2026-08-01'},None),
 ({'posted_at':'2026-10-02'},None),
 ({'posted_at':'2026-09-01'},'new'),
 ({'last_checked_at':'2026-09-30T23:59:00+09:00'},None),
 ({'last_checked_at':'2026-10-01T07:00:00+09:00'},None),
])
def test_new_reminder_boundaries_and_stale_data(changes,reason):
    output=build_items([changed(**changes)],STATE,CHANNELS,now=NOW)
    notices=output['channels'][0]['notices']
    assert [n['reason'] for n in notices]==([] if reason is None else [reason])
    if notices: assert notices[0]['dday']==((datetime.fromisoformat(changes['deadline']).date()-NOW.date()).days if changes.get('deadline') else None)


def test_bootstrap_and_changes_are_not_today_new():
    output=build_items([row()],{'boards':{}},CHANNELS,now=NOW)
    assert not output['channels'][0]['notices']
    assert any('운영 시작' in e['message'] for e in output['errors'])
    # 운영 시작 시각 이전에 저장된 초기 적재는 신규가 아니다.
    later={'boards':{'knu-test':dict(initialized_at='2026-10-01T05:40:00+09:00',last_full_scan_at=None)}}
    assert not build_items([row()],later,CHANNELS,now=NOW)['channels'][0]['notices']
    assert discovery_reason(changed(first_seen_at=BASE),BASE,NOW.date()) is None


@pytest.mark.parametrize('reason', ['new', 'reminder'])
def test_selected_notices_and_schedule_are_kept_regardless_of_recipient(reason):
    rows = [row(str(i)) for i in range(3)]
    for r, title, body in zip(rows,
            ['[대학원] 논문 제출', '졸업예정자 졸업시험', '행사 안내'],
            ['대상: 대학원생', '대상: 졸업예정자', '본문 일반 안내']):
        r.update(title=title, body=body)
        if reason == 'reminder':
            r.update(first_seen_at=BASE, deadline='2026-10-04')
    original = deepcopy(rows)
    context = dict(date=NOW.date().isoformat(), collected_at=NOW.isoformat(),
                   weather=dict(summary=None, temp_min=None, temp_max=None, rain_prob=None),
                   channels=[], errors=[], schedule=[
                       dict(title='[대학원] 논문 접수', start='2026-09-30', end='2026-10-02', dday=-1),
                       dict(title='중간고사', start='2026-10-02', end=None, dday=1)])
    output = build_items(rows, STATE, CHANNELS, now=NOW, context=context)
    notices = output['channels'][0]['notices']
    assert [n['id'] for n in notices] == [r['id'] for r in rows]
    assert all(n['reason'] == reason for n in notices)
    assert set(notices[0]) == {'id', 'channel_id', 'source', 'title', 'url',
                              'posted_at', 'deadline', 'dday', 'body', 'reason'}
    assert output['schedule'] == context['schedule']
    assert output['errors'] == [dict(source='meals', message='오늘 식단은 로컬에서 아직 수집하지 않았습니다')]
    assert rows == original


def test_shared_channels_body_errors_and_missing_other_sources(tmp_path):
    channels=CHANNELS+[dict(id='notice-b',name='다른 학과',source_board_id='knu-test')]
    r=changed(channel_ids=['notice-a','notice-b'],body=None,body_status='image-only')
    output=build_items([r],STATE,channels,now=NOW)
    assert [len(c['notices']) for c in output['channels']]==[1,1]
    assert all(c['notices'][0]['body'] is None for c in output['channels'])
    assert output['weather']==dict(summary=None,temp_min=None,temp_max=None,rain_prob=None) and output['schedule']==[]
    assert {e['source'] for e in output['errors']}=={'weather','meals','schedule','notice-a','notice-b'}
    path=tmp_path/'items.json';store.save_daily_items(output,path)
    assert store.load_collection_report(path)==output
    original=path.read_bytes()
    for bad in [dict(output,date='2026-09-30'),dict(output,channels=[output['channels'][0]]*2)]:
        with pytest.raises(ValueError):store.save_daily_items(bad,path)
        assert path.read_bytes()==original
    bad=deepcopy(output);bad['channels'][0]['notices'][0].update(reason='reminder',dday=2,deadline='2026-10-03')
    with pytest.raises(ValueError):store.save_daily_items(bad,path)
    assert path.read_bytes()==original


def test_partial_failure_keeps_success_and_reports_limit():
    a,b=row(),row('2')
    a['url'] += '?mv_data=abc%7C%7C'
    reports=[{'channels':[dict(source_board_id='knu-test',channel_id='notice-a',started_at=NOW.isoformat(),window_complete=False,truncated=True,
                              errors=[dict(source='notice-a',url=a['url'].replace('%7C','|'),message='상세 실패')])]}]
    output=build_items([a,b],STATE,CHANNELS,now=NOW,reports=reports)
    assert [n['id'] for n in output['channels'][0]['notices']]==[b['id']]
    assert any('상세 실패' in e['message'] for e in output['errors'])
    assert any('페이지 제한' in e['message'] for e in output['errors'])
    reports[0]['channels'][0]['started_at']=BASE
    with pytest.raises(ValueError):build_items([a],STATE,CHANNELS,now=NOW,reports=reports)


@pytest.mark.parametrize('error', [
    dict(source='notice-a', message='목록 확인 실패'),
    dict(source='notice-a', message='목록 확인 실패', url=None),
    dict(source='notice-a', message='목록 확인 실패', url=''),
])
def test_error_without_url_keeps_notices_and_original_message(error):
    report={'channels':[dict(source_board_id='knu-test',channel_id='notice-a',started_at=NOW.isoformat(),
                            window_complete=False,truncated=False,errors=[error]) ]}
    output=build_items([row()],STATE,CHANNELS,now=NOW,reports=[report])
    assert [n['id'] for n in output['channels'][0]['notices']]==[row()['id']]
    assert dict(source='notice-a',message='목록 확인 실패') in output['errors']


def test_required_recent_records_board_url_when_collector_raises(monkeypatch,tmp_path):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'tools/collect_required_recent.py'
    spec=importlib.util.spec_from_file_location('collect_required_recent',path)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    (tmp_path/'data').mkdir();(tmp_path/'data/channels.yaml').write_text('[]',encoding='utf-8')
    from collector import run
    monkeypatch.setattr(run,'board_id_for',lambda board:board['source_board_id'])
    boards=[dict(id=f'board-{i}',name=f'게시판 {i}',channel_ids=[f'channel-{i}'],
                 source_board_id=f'board-{i}',source_url=f'https://example.com/list/{i}') for i in range(136)]
    boards[0]['channel_ids']=['a','b','c','d']
    monkeypatch.setattr(tool,'ROOT',tmp_path)
    monkeypatch.setattr(tool,'VALIDATION_PATH',tmp_path/'validation.json')
    monkeypatch.setattr(tool,'DEFAULT_PATH',tmp_path/'notices.json')
    monkeypatch.setattr(tool,'load_collection_report',lambda path:{})
    monkeypatch.setattr(tool,'select_channels',lambda channels,**kwargs:boards[:1] if kwargs.get('required_all') else boards)
    monkeypatch.setattr(tool,'board_id_for',lambda board:board['source_board_id'])
    monkeypatch.setattr(tool,'load_collection_state',lambda path:{'boards':{}})
    monkeypatch.setattr(tool,'load_notices',lambda path:[])
    reports=[]
    monkeypatch.setattr(tool,'save_collection_report',lambda report,path:reports.append(deepcopy(report)))
    clients=[]
    class Client:
        def __init__(self):clients.append(self)
        request_count=0
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(tool,'Client',Client)
    def collect(client,board,**kwargs):
        if board is boards[0]:raise RuntimeError('목록 파싱 실패')
        return dict(channel_id=board['id'],channel_ids=board['channel_ids'],source_board_id=board['id'],
                    listed=0,successful=0,window_complete=True,truncated=False,new=[],updated=[],
                    unchanged=[],skipped=[],errors=[],request_count=0,duration_sec=0)
    monkeypatch.setattr(tool,'collect',collect)
    tool.main([])
    assert reports[-1]['channels'][0]['errors']==[
        dict(source='board-0',message='RuntimeError: 목록 파싱 실패',url='https://example.com/list/0')]


def test_required_recent_resume_carries_only_normal_boards(tmp_path):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'tools/collect_required_recent.py'
    spec=importlib.util.spec_from_file_location('collect_required_recent_resume',path)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    tool.load_collection_report=store.load_collection_report
    boards=[dict(source_board_id=f'b{i}',channel_ids=[f'c{i}']) for i in range(3)]
    tool.board_id_for=lambda board:board['source_board_id']
    source=tmp_path/'old.json'
    store.save_collection_report({'channels':[
        dict(source_board_id='b0',channel_ids=['c0'],window_complete=True,truncated=False,errors=[]),
        dict(source_board_id='b1',channel_ids=['c1'],window_complete=True,truncated=False,errors=[{}]),
        dict(source_board_id='b2',channel_ids=['c2'],window_complete=False,truncated=False,errors=[])]},source)
    carried=tool.read_resume_report(source,boards)
    assert list(carried)==['b0'] and carried['b0']['resumed'] is True
    original=store.load_collection_report(source)
    assert 'resumed' not in original['channels'][0]
    original['channels'][0]['channel_ids']=['wrong']
    store.save_collection_report(original,source)
    with pytest.raises(ValueError,match='channel_ids'):
        tool.read_resume_report(source,boards)


def test_required_recent_main_resume_skips_retries_and_accumulates(monkeypatch,tmp_path):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'tools/collect_required_recent.py'
    spec=importlib.util.spec_from_file_location('collect_required_recent_main_resume',path)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    (tmp_path/'data').mkdir();(tmp_path/'data/channels.yaml').write_text('[]',encoding='utf-8')
    from collector import run
    boards=[dict(id=f'b{i}',name=f'게시판 {i}',channel_ids=[f'c{i}'],source_board_id=f'b{i}',
                 source_url=f'https://example.com/{i}') for i in range(136)]
    boards[0]['channel_ids']=['c0','extra-a','extra-b','extra-c']
    monkeypatch.setattr(tool,'ROOT',tmp_path);monkeypatch.setattr(tool,'VALIDATION_PATH',tmp_path/'validation.json')
    monkeypatch.setattr(tool,'DEFAULT_PATH',tmp_path/'notices.json')
    monkeypatch.setattr(tool,'load_collection_report',lambda path: {} if path==tool.VALIDATION_PATH else store.load_collection_report(path))
    monkeypatch.setattr(tool,'select_channels',lambda channels,**kwargs:boards[:1] if kwargs.get('required_all') else boards)
    monkeypatch.setattr(tool,'board_id_for',lambda board:board['source_board_id'])
    monkeypatch.setattr(tool,'load_collection_state',lambda path:{'boards':{
        f'b{i}':{'initialized_at':'already'} for i in range(136) if i != 68}})
    monkeypatch.setattr(tool,'load_notices',lambda path:[])
    reports=[]
    monkeypatch.setattr(tool,'save_collection_report',lambda report,path:reports.append(deepcopy(report)))
    clients=[]
    class Client:
        def __init__(self):clients.append(self)
        request_count=0
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(tool,'Client',Client)
    calls=[]
    def collect(client,board,**kwargs):
        calls.append((board['id'],kwargs['mode']))
        return dict(channel_id=board['id'],channel_ids=board['channel_ids'],source_board_id=board['id'],
                    listed=1,successful=1,window_complete=True,truncated=False,new=[],updated=[],
                    unchanged=[],skipped=[],errors=[],request_count=0,duration_sec=0)
    monkeypatch.setattr(tool,'collect',collect)
    old_path=tmp_path/'old.json'
    old={'channels':[
        dict(source_board_id=f'b{i}',channel_id=f'b{i}',channel_ids=boards[i]['channel_ids'],
             window_complete=True,truncated=False,errors=[],request_count=4,duration_sec=1)
        for i in range(67)] + [dict(source_board_id='b67',channel_id='b67',channel_ids=['c67'],
             window_complete=True,truncated=False,errors=[{'message':'failed'}])]}
    store.save_collection_report(old,old_path);old_bytes=old_path.read_bytes()
    tool.main(['--resume-report',str(old_path)])
    assert len(calls)==69 and calls[0]==('b67','daily') and ('b68','start') in calls
    assert reports[0]['completed_boards']==67 and reports[0]['resumed_boards']==67
    assert len(reports[-1]['channels'])==136 and sum(row.get('resumed',False) for row in reports[-1]['channels'])==67
    first_path=tmp_path/'first.json';store.save_collection_report(reports[-1],first_path)
    calls.clear();reports.clear()
    tool.main(['--resume-report',str(first_path)])
    assert calls==[] and reports[0]['completed_boards']==136
    assert len(reports[-1]['channels'])==136 and all(row.get('resumed') for row in reports[-1]['channels'])
    assert old_path.read_bytes()==old_bytes
    client_count=len(clients)
    malformed=tmp_path/'malformed.json'
    store.save_collection_report({'channels':[dict(source_board_id='unknown',channel_ids=[],
        window_complete=True,truncated=False,errors=[])]},malformed)
    with pytest.raises(ValueError,match='알 수 없는 source_board_id'):
        tool.main(['--resume-report',str(malformed)])
    assert len(clients)==client_count


def test_empty_board_requires_today_list_check_and_repeat_is_identical():
    missing=build_items([],STATE,CHANNELS,now=NOW)
    assert any('빈 게시판' in e['message'] for e in missing['errors'])
    reports=[{'channels':[dict(source_board_id='knu-test',channel_id='notice-a',started_at=NOW.isoformat(),window_complete=True,truncated=False,errors=[])]}]
    empty=build_items([],STATE,CHANNELS,now=NOW,reports=reports)
    assert len(empty['errors'])==3 and not empty['channels'][0]['notices']
    assert empty==build_items([],STATE,CHANNELS,now=NOW,reports=reports)
    with pytest.raises(ValueError):build_items([],STATE,CHANNELS,now=datetime.fromisoformat('2026-10-01T00:00:00+00:00'))


@pytest.mark.parametrize('extras',[False,True])
def test_collect_command_writes_items_to_chosen_path(tmp_path,monkeypatch,extras):
    from collector import run
    import sys
    project_root=run.ROOT
    config_dir=tmp_path/'data';config_dir.mkdir()
    (config_dir/'channels.yaml').write_bytes((project_root/'data/channels.yaml').read_bytes())
    monkeypatch.setattr(run,'ROOT',tmp_path)
    now=datetime.now(store.SEOUL)
    path=tmp_path/'notices.json';output=tmp_path/'items.json'
    def collect(client,channel,**kwargs):
        board=run.board_id_for(channel)
        notice={key:value for key,value in row().items() if key in store.INPUT_FIELDS}
        notice.update(source_board_id=board,channel_ids=channel['channel_ids'],posted_at=now.date().isoformat())
        store.upsert_notices([notice],path=path,checked_at=now.isoformat())
        store.save_collection_state({'boards':{board:dict(initialized_at=(now.replace(hour=0,minute=0,second=0,microsecond=0)).isoformat(),last_full_scan_at=None)}},path)
        return dict(channel_id=channel['id'],channel_ids=channel['channel_ids'],source_board_id=board,
                    started_at=now.isoformat(),window_complete=True,truncated=False,listed=1,successful=1,
                    new=[board+':1'],updated=[],unchanged=[],skipped=[],errors=[],request_count=0,duration_sec=0)
    class Client:
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(run,'collect',collect);monkeypatch.setattr(run,'Client',Client)
    monkeypatch.setattr(sys,'argv',['collector.run','--channel-id',run.CHANNEL_ID,'--db-path',str(path),'--report-path',str(tmp_path/'run.json'),'--write-items','--items-path',str(output)])
    if extras:
        from collector import daily_sources
        context=dict(date=now.date().isoformat(),collected_at=now.isoformat(),
                     weather=dict(summary='맑음',temp_min=15,temp_max=25,rain_prob=0),
                     channels=[dict(channel_id='meal-46',notices=[],meals=[])],schedule=[],errors=[],
                     sources=[dict(source='meal-46',url='fixture')],request_count=4)
        monkeypatch.setattr(daily_sources,'collect',lambda client,day,**kwargs:context)
        sys.argv.append('--collect-extras')
    assert run.main()==0
    items=store.load_collection_report(output)
    assert len(items['channels'][0]['notices'])==1 and items['channels'][0]['notices'][0]['reason']=='new'
    if extras:
        assert items['weather']['summary']=='맑음' and items['errors']==[]
        assert store.load_collection_report(tmp_path/'data/raw'/now.date().isoformat()/'context.json')==context
        report=store.load_collection_report(tmp_path/'run.json')
        assert report['request_count']==4 and report['extras']['request_count']==4 and report['duration_sec']>=0
