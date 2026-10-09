import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from briefing import build as b, checkpoint, kaggle, kaggle_batch, kaggle_worker


def test_batch_saves_thirty_and_restored_cache_only_generates_remaining(tmp_path, monkeypatch):
    data = json.loads((b.ROOT / 'data/raw/2026-10-03/items.json').read_text())
    segments = [dict(id=str(n), kind='outro', title=str(n), script=f'audio {n}', channel_ids=[], audio={}) for n in range(65)]
    monkeypatch.setattr(b, 'create_segments', lambda *a: (deepcopy(segments), []))
    monkeypatch.setattr(b, 'generate_segments', lambda s,*a,**kw:s)
    monkeypatch.setattr(b, 'prepare_bgm', lambda *a:None)
    monkeypatch.setattr(b, 'audio_info', lambda raw:1)
    provider=Mock(); provider.synthesize.side_effect=lambda script,*a:script.encode()
    path=tmp_path/'items.json'; path.write_text(json.dumps(data))
    ctx=dict(checkpoint_signature='same',day=data['date'],kernel_id='muyahoyeol/test')
    failures={}
    assert kaggle_worker.AUDIO_BATCH_SIZE == 30
    for batch in range(3):
        cache=tmp_path/f'cache-{batch}'
        if batch:
            failures=checkpoint.restore(tmp_path/f'saved-{batch-1}',cache,'same')
        kwargs=dict(output=tmp_path/'dist',cache=cache,allow_archive=True,client=provider,
                    audio_batch_size=kaggle_worker.AUDIO_BATCH_SIZE,failed_audio=failures)
        if batch<2:
            with pytest.raises(b.AudioBatchComplete): b.build(path,**kwargs)
            assert not (tmp_path/'dist/manifest.json').exists()
        else:
            report=b.build(path,**kwargs)
            assert report['new_requests']==5 and report['cached']==60
        checkpoint.save(cache,tmp_path/f'saved-{batch}',ctx,failures,'pending' if batch<2 else 'complete')
    assert provider.synthesize.call_count==65
    assert len(json.loads((tmp_path/'dist/manifest.json').read_text())['segments'])==65


def test_checkpoint_rejects_changed_input_tampered_file_and_path(tmp_path):
    cache=tmp_path/'cache'; cache.mkdir(); (cache/'ok.mp3').write_bytes(b'valid')
    ctx=dict(checkpoint_signature='same',day='2026-10-08',kernel_id='owner/run')
    saved=tmp_path/'saved'; checkpoint.save(cache,saved,ctx,{},'pending')
    with pytest.raises(ValueError,match='설정'): checkpoint.restore(saved,tmp_path/'new','different')
    (saved/'cache/ok.mp3').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='해시'): checkpoint.restore(saved,tmp_path/'new','same')
    assert not (tmp_path/'new').exists()
    state=json.loads((saved/'state.json').read_text()); state['files']={'../escape.mp3':'hash'}
    (saved/'state.json').write_text(json.dumps(state))
    with pytest.raises(ValueError,match='경로'): checkpoint.restore(saved,tmp_path/'new','same')


def test_failed_audio_is_not_retried_in_the_next_batch(tmp_path, monkeypatch):
    data=json.loads((b.ROOT/'data/raw/2026-10-03/items.json').read_text())
    segments=[dict(id=str(i),kind='outro',title=str(i),script=str(i),channel_ids=[],audio={}) for i in range(12)]
    monkeypatch.setattr(b,'create_segments',lambda *a:(deepcopy(segments),[]))
    monkeypatch.setattr(b,'generate_segments',lambda s,*a,**kw:s)
    monkeypatch.setattr(b,'prepare_bgm',lambda *a:None)
    monkeypatch.setattr(b,'audio_info',lambda raw:1)
    provider=Mock()
    def synthesize(script,*a):
        if script=='2': raise RuntimeError('음성 길이 상한')
        return script.encode()
    provider.synthesize.side_effect=synthesize
    path=tmp_path/'input.json';path.write_text(json.dumps(data)); failures={}
    kwargs=dict(cache=tmp_path/'cache',output=tmp_path/'dist',client=provider,allow_archive=True,failed_audio=failures,audio_batch_size=10)
    with pytest.raises(b.AudioBatchComplete): b.build(path,**kwargs)
    ctx=dict(checkpoint_signature='sig',day=data['date'],kernel_id='o/k')
    checkpoint.save(kwargs['cache'],tmp_path/'saved',ctx,failures,'pending')
    kwargs['cache']=tmp_path/'restored';kwargs['failed_audio']=checkpoint.restore(tmp_path/'saved',kwargs['cache'],'sig')
    report=b.build(path,**kwargs)
    assert provider.synthesize.call_count==12
    assert report['status']=='partial' and len(report['audio_failures'])==1
    assert len(json.loads((tmp_path/'dist/manifest.json').read_text())['segments'])==11


def test_batch_metadata_connects_previous_output_and_signature_is_stable(tmp_path):
    first=kaggle.prepare_kernel(kaggle.ROOT,'2026-10-05','123','1','a'*40,'muyahoyeol',tmp_path/'one',tmp_path/'expected',batch=1)
    second=kaggle.prepare_kernel(kaggle.ROOT,'2026-10-05','123','1','a'*40,'muyahoyeol',tmp_path/'two',tmp_path/'expected',batch=2,resume_kernel=first['kernel_id'])
    assert first['checkpoint_signature']==second['checkpoint_signature']
    assert second['kernel_id'].endswith('-b2')
    assert json.loads((tmp_path/'two/kernel-metadata.json').read_text())['kernel_sources']==[first['kernel_id']]


def test_batch_driver_links_checkpoints_and_only_returns_after_final_output(tmp_path, monkeypatch):
    expected=tmp_path/'expected.json'; folder=tmp_path/'kernel';output=tmp_path/'output'
    kaggle.prepare_kernel(kaggle.ROOT,'2026-10-05','123','1','a'*40,'muyahoyeol',folder,expected)
    pushes=[]
    def cli(args,**kwargs):
        if args[:2]==['kernels','push']:
            pushes.append(json.loads((folder/'kernel-metadata.json').read_text()))
            return SimpleNamespace(returncode=0,stdout='Kernel version 1 successfully pushed.',stderr='')
        assert args[:2]==['kernels','output']
        current=json.loads(expected.read_text())
        state=dict(signature=current['checkpoint_signature'],kernel_id=current['kernel_id'],
                   status='complete' if len(pushes)==3 else 'pending',files={},failed_audio={})
        target=output/'briefing-artifacts/checkpoint';target.mkdir(parents=True,exist_ok=True)
        (target/'state.json').write_text(json.dumps(state))
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(kaggle_batch,'cli',cli)
    monkeypatch.setattr(kaggle,'wait_for_kernel',Mock())
    kaggle_batch.run_batches(kaggle.ROOT,expected,folder,output,tmp_path/'logs')
    assert len(pushes)==3
    assert pushes[0]['kernel_sources']==[]
    assert pushes[1]['kernel_sources']==[pushes[0]['id']]
    assert pushes[2]['kernel_sources']==[pushes[1]['id']]
    assert json.loads(expected.read_text())['kernel_id']==pushes[-1]['id']
    assert json.loads(expected.read_text())['kernel_version']==1


def test_retry_finds_last_saved_batch_instead_of_interrupted_one(tmp_path,monkeypatch):
    context=dict(username='muyahoyeol',run_id='123',run_attempt='2',checkpoint_signature='sig')
    def cli(args,**kwargs):
        if args[:2]==['kernels','status']:
            status='ERROR' if args[2].endswith('-b3') else 'COMPLETE'
            return SimpleNamespace(returncode=0,stdout='KernelWorkerStatus.'+status,stderr='')
        destination=Path(args[args.index('--path')+1])/'briefing-artifacts/checkpoint'
        destination.mkdir(parents=True)
        (destination/'state.json').write_text(json.dumps(dict(signature='sig')))
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    from pathlib import Path
    monkeypatch.setattr(kaggle_batch,'cli',cli)
    assert kaggle_batch.previous_checkpoint(context,tmp_path).endswith('-1-b2')


def test_failure_mail_tells_how_to_resume_saved_kernel(tmp_path):
    from briefing.failure_notice import render
    (tmp_path/'resume.json').write_text(json.dumps(dict(kernel_id='muyahoyeol/knu-audio-briefing-123-1-b2')))
    text=render(tmp_path,'failure','skipped',True,'owner','run')
    assert 'Re-run failed jobs' in text and 'resume_kernel' in text
    assert '123-1-b2' in text
