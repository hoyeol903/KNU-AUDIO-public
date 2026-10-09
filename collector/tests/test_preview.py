from copy import deepcopy
from datetime import datetime
from pathlib import Path
import hashlib

import pytest
from collector import preview
from collector.daily_items import build_items,decide_notice
from collector.store import DEFAULT_PATH, SEOUL


def example():
    return dict(date='2026-10-01',time='08:00',title='신입생 행사',body='대상: 학부 신입생',body_status='text',
                posted_at='2026-09-30',deadline='',first_seen_at='2026-10-01T05:37:00+09:00',
                last_checked_at='2026-10-01T05:38:00+09:00',baseline='2026-09-30T06:00:00+09:00')


@pytest.mark.parametrize('changes,code,status',[
    ({},'new','selected'),
    ({'deadline':'2026-10-04','first_seen_at':'2026-09-30T05:00:00+09:00'},'reminder','selected'),
    ({'deadline':'2026-09-30'},'expired','skipped'),
    ({'title':'[대학원] 논문 제출','body':'대학원 학위논문 제출 절차 안내'},'new','selected'),
    ({'body_status':'image-only','body':''},'new','selected'),
    ({'baseline':'2026-10-01T06:00:00+09:00'},'no-trigger','skipped'),
    ({'first_seen_at':'2026-09-30T05:00:00+09:00','last_checked_at':'2026-09-30T05:38:00+09:00','deadline':'2026-10-02'},'stale','skipped'),
])
def test_simulator_uses_actual_selection_and_never_changes_db(changes,code,status):
    before=hashlib.sha256(DEFAULT_PATH.read_bytes()).hexdigest()
    value=example();value.update(changes);result=preview.simulate(value)
    assert result['decision']['code']==code and result['decision']['status']==status
    assert bool(result['items']['channels'][0]['notices'])==(status=='selected')
    assert hashlib.sha256(DEFAULT_PATH.read_bytes()).hexdigest()==before


def test_snapshot_filters_channels_and_reports_missing_without_writing():
    before=DEFAULT_PATH.read_bytes()
    result=preview.snapshot(['knu-academic','meal-46'])
    assert all('knu-academic' in r['channel_ids'] for r in result['checks'])
    assert {c['channel_id'] for c in result['items']['channels']} <= {'knu-academic','meal-46'}
    assert DEFAULT_PATH.read_bytes()==before
    assert preview.snapshot(['notice-ddb70636c525'])['items']['errors']
    with pytest.raises(ValueError):preview.snapshot(['does-not-exist'])


@pytest.mark.parametrize('url_field', [None, {'url': None}, {'url': ''}])
def test_snapshot_tolerates_report_errors_without_url(monkeypatch,url_field):
    now=datetime.fromisoformat('2026-10-01T08:00:00+09:00')
    row=dict(id='knu-test:1',source_board_id='knu-test',source_post_id='1',channel_ids=['notice-a'],
             title='원문 제목',url='https://example.com/post/1',posted_at='2026-09-30',deadline=None,
             body='원문 본문',body_status='text',first_seen_at='2026-10-01T05:37:00+09:00',
             last_checked_at='2026-10-01T05:37:00+09:00')
    error=dict(source='notice-a',message='목록 확인 실패')
    if isinstance(url_field,dict):error.update(url_field)
    report={'channels':[dict(source_board_id='knu-test',channel_id='notice-a',started_at=now.isoformat(),
                            window_complete=False,truncated=False,errors=[error]) ]}
    monkeypatch.setattr(preview,'catalog',lambda:([dict(id='notice-a',name='학과 공지',type='notice')],[]))
    monkeypatch.setattr(preview,'load_notices',lambda:[row])
    monkeypatch.setattr(preview,'load_collection_state',lambda:{'boards':{'knu-test':{'initialized_at':'2026-09-30T06:00:00+09:00'}}})
    monkeypatch.setattr(preview,'load_context',lambda:None)
    monkeypatch.setattr(preview,'latest_reports',lambda day=None:[report])
    monkeypatch.setattr(preview,'datetime',type('FixedDateTime',(datetime,),{'now':classmethod(lambda cls,tz:now)}))
    result=preview.snapshot(['notice-a'])
    assert [n['id'] for n in result['items']['channels'][0]['notices']]==[row['id']]
    assert dict(source='notice-a',message='목록 확인 실패') in result['items']['errors']
    assert result['checks'][0]['status']=='selected'


@pytest.mark.parametrize('changes',[{'date':'bad'},{'body_status':'bad'},{'title':''},{'last_checked_at':'2026-09-29T06:00:00+09:00'},{'baseline':'2026-09-30T06:00:00+00:00'}])
def test_invalid_simulation_is_rejected(changes):
    value=example();value.update(changes)
    with pytest.raises(ValueError):preview.simulate(value)
