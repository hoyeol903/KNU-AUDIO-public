from datetime import date
import json
from pathlib import Path
import base64

from tools import briefing_notice as n


def run(id=1, path='briefing-kaggle.yml', title='브리핑 생성 | 수집=없음 | 게시=예', result='success'):
    return dict(id=id, path='.github/workflows/'+path, display_title=title, conclusion=result,
                status='completed', head_branch='main', created_at='2026-10-13T16:38:00Z')


def setup(monkeypatch, rows):
    notices, dispatched, waits = [], [], []
    monkeypatch.setenv('DEFAULT_BRANCH', 'main')
    monkeypatch.setattr(n, 'run_info', lambda id: rows[int(id)])
    monkeypatch.setattr(n, 'notify', lambda *args: notices.append(args))
    monkeypatch.setattr(n, 'dispatch', lambda *args, **kw: dispatched.append((args, kw)))
    return notices, dispatched, waits


def test_korean_date_and_messages():
    assert n.sentence(date(2026,10,14)) == '10/14 (수) 오늘 브리핑이 정상적으로 업로드되었습니다.'
    assert n.sentence(date(2026,10,14), '자료 수집 실패').endswith('실패했습니다. 자료 수집 실패')


def test_generation_success_does_not_send_early(monkeypatch):
    notices, dispatched, waits = setup(monkeypatch, {1: run()})
    n.main({'workflow_run': {'id': 1}}, waits.append)
    assert not notices and not dispatched and not waits


def test_generation_failure_waits_30_minutes_then_recovers_without_regeneration(monkeypatch):
    notices, dispatched, waits = setup(monkeypatch, {1: run(result='failure')})
    n.main({'workflow_run': {'id': 1}}, waits.append)
    assert waits == [1800]
    assert dispatched == [(('briefing-kaggle-recover.yml',), {'run_id':'1'})]
    assert notices == []


def test_deploy_failure_retries_only_once(monkeypatch):
    rows={1:run(),2:run(2,'deploy.yml','브리핑 배포 | 원본=1 | 재시도=아니오','failure')}
    notices, dispatched, waits = setup(monkeypatch,rows)
    n.main({'workflow_run': {'id':2}}, waits.append)
    assert waits == [1800] and dispatched[0][1]['final_retry']=='true' and not notices
    rows[2]['display_title']='브리핑 배포 | 원본=1 | 재시도=예'
    n.main({'workflow_run': {'id':2}}, waits.append)
    assert len(waits)==1 and len(dispatched)==1 and '실패' in notices[0][1]


def test_failed_recovery_sends_failure_without_more_retries(monkeypatch):
    rows={1:run(),2:run(2,'briefing-kaggle-recover.yml','브리핑 복구 | 원본=1 | 재시도=예','failure')}
    notices, dispatched, waits = setup(monkeypatch,rows)
    n.main({'workflow_run': {'id':2}}, waits.append)
    assert len(notices)==1 and not dispatched and not waits


def test_site_verification_precedes_success_and_partial_failures_are_reported(monkeypatch):
    rows={1:run(),2:run(2,'deploy.yml','브리핑 배포 | 원본=1 | 재시도=아니오')}
    notices, dispatched, waits = setup(monkeypatch,rows)
    checked=[]
    monkeypatch.setattr(n,'verify_site',lambda day:checked.append(day))
    record={'run_id':'1','audio_failures':0,'skipped_notices':0}
    monkeypatch.setattr(n,'api',lambda path,**fields:dict(content=base64.b64encode(json.dumps(record).encode()).decode()))
    n.main({'workflow_run': {'id':2}}, waits.append)
    assert checked==[date(2026,10,14)] and notices==[(date(2026,10,14),None)]
    record['audio_failures']=1
    n.main({'workflow_run': {'id':2}}, waits.append)
    assert '일부 대본' in notices[-1][1]


def test_collection_delegates_to_corresponding_generation(monkeypatch):
    rows={3:run(3,'collect.yml','자료 수집','failure')}
    notices,dispatched,waits=setup(monkeypatch,rows)
    monkeypatch.setattr(n,'api',lambda path,**fields:{'workflow_runs':[run(title='브리핑 생성 | 수집=3 | 게시=예')]})
    n.main({'workflow_run':{'id':3}},waits.append)
    assert not notices
    monkeypatch.setattr(n,'api',lambda path,**fields:{'workflow_runs':[]})
    n.main({'workflow_run':{'id':3}},waits.append)
    assert len(notices)==1


def test_one_notification_per_day_including_first_issue(monkeypatch):
    monkeypatch.setenv('GH_OWNER','owner')
    calls=[]
    marker='<!-- briefing-final:2026-10-14 -->'
    def api(path,**fields):
        calls.append((path,fields))
        if path.startswith('issues?'):return [{'number':8,'title':'오늘 브리핑 결과','body':marker}]
        raise AssertionError('중복 알림 전송')
    monkeypatch.setattr(n,'api',api)
    n.notify(date(2026,10,14))
    assert len(calls)==1


def test_workflows_are_connected_and_only_final_notifier_remains():
    root=Path(__file__).resolve().parents[2]
    import yaml
    workflows={p.name:yaml.safe_load(p.read_text()) for p in (root/'.github/workflows').glob('*.yml')}
    assert 'meal-reminder.yml' not in workflows
    assert 'notify' not in workflows['briefing-kaggle.yml']['jobs']
    assert 'workflow_run' not in workflows['briefing-kaggle-recover.yml']['on']
    assert workflows['briefing-notice.yml']['jobs']['final']['timeout-minutes']>30
    for name in ['briefing-kaggle.yml','briefing-kaggle-recover.yml']:
        steps=workflows[name]['jobs']['publish']['steps']
        assert '-f briefing_run_id=' in steps[-1]['run']
    assert '공지 목록 알림' not in (root/'.github/workflows/collect.yml').read_text()


def test_site_rejects_yesterday_or_missing_files_without_sending_success(monkeypatch):
    rows={1:run(),2:run(2,'deploy.yml','브리핑 배포 | 원본=1 | 재시도=아니오')}
    notices,dispatched,waits=setup(monkeypatch,rows)
    def broken(day):raise ValueError('어제 자료')
    monkeypatch.setattr(n,'verify_site',broken)
    n.main({'workflow_run':{'id':2}},waits.append)
    assert waits==[1800] and len(dispatched)==1 and not notices


def test_read_only_api_retries_but_notification_writes_do_not(monkeypatch):
    import subprocess
    monkeypatch.setenv('GH_REPO','owner/repo')
    calls=[];waits=[]
    def command(*args):
        calls.append(args)
        if len(calls)<3:raise subprocess.CalledProcessError(1,args)
        return '[]'
    monkeypatch.setattr(n,'command',command);monkeypatch.setattr(n.time,'sleep',waits.append)
    assert n.api('actions/runs/1')==[] and waits==[5,5]


def test_cancelled_generation_is_not_restarted(monkeypatch):
    notices,dispatched,waits=setup(monkeypatch,{1:run(result='cancelled')})
    n.main({'workflow_run':{'id':1}},waits.append)
    assert len(notices)==1 and not dispatched and not waits
