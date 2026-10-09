import json
from unittest.mock import Mock

import pytest

from briefing import build as b, app_export
from briefing.failure_notice import render


def test_failed_shared_notice_is_excluded_but_later_audio_and_export_continue(tmp_path, monkeypatch):
    data = json.loads((b.ROOT / 'data/raw/2026-10-03/items.json').read_text())
    rows = []
    for c in data['channels']:
        c['meals'] = []
        c['notices'] = c['notices'][:1]
        if c['notices']:
            rows.append((c, c['notices'][0]))
    rows = rows[:2]
    for c in data['channels']:
        if not any(c is r[0] for r in rows):
            c['notices'] = []
    refs = [dict(channel_id=c['channel_id'], postId=n['id'], title=n['title'], url=n['url']) for c,n in rows]
    def segment(sid, kind, channels=(), **extra):
        return dict(id=sid, kind=kind, title=sid, script=sid, channel_ids=list(channels), audio={}, **extra)
    segments = [segment('failed', 'notice', [r['channel_id'] for r in refs], notice_refs=refs),
                segment('after', 'outro'), segment('weather', 'weather')]
    monkeypatch.setattr(b, 'create_segments', lambda *a: (segments, []))
    monkeypatch.setattr(b, 'generate_segments', lambda s, *a, **k: s)
    monkeypatch.setattr(b, 'audio_info', lambda raw: 1)
    monkeypatch.setattr(b, 'prepare_bgm', lambda *a: None)
    provider = Mock()
    provider.synthesize.side_effect = lambda script, *a: (_ for _ in ()).throw(RuntimeError('음성 길이 상한')) if script == 'failed' else script.encode()
    path=tmp_path/'items.json'; path.write_text(json.dumps(data))
    report=b.build(path, output=tmp_path/'dist', cache=tmp_path/'cache', allow_archive=True, client=provider)
    assert report['status']=='partial'
    assert [c.args[0] for c in provider.synthesize.call_args_list]==['failed','after','weather']
    assert len(report['skipped_notices'])==len(refs)
    manifest=json.loads((tmp_path/'dist/manifest.json').read_text())
    assert [s['id'] for s in manifest['segments']]==['after','weather']
    exported=app_export.export(tmp_path/'dist', tmp_path/'app', items_path=path)
    assert {s['id'] for s in exported}=={'intro','outro'}
    assert 'failed' not in {s['id'] for s in exported}
    (tmp_path/'briefing-report.json').write_text(json.dumps(report))
    email=render(tmp_path, 'success', 'success', True, 'owner', 'https://example/run')
    assert 'failed' in email and '길이 상한' in email and '재실행' in email
    assert refs[0]['channel_id'] in email


def test_failure_mail_and_success_silence(tmp_path):
    assert render(tmp_path,'success','success',True,'owner','run')==''
    assert 'KAGGLE_API_TOKEN' in render(tmp_path,'failure','skipped',True,'owner','run')
    assert '게시 단계부터' in render(tmp_path,'success','failure',True,'owner','run')


def test_failed_meal_and_common_audio_can_be_omitted(tmp_path):
    from briefing.tests.test_app_export import sample
    _, _, manifest, items = sample(tmp_path)
    meal = next(s for s in manifest['segments'] if s['kind']=='meal')
    meal['id']='meal-failed'
    manifest['audio_failures']=[dict(segment_id=meal['id'],kind='meal',channel_ids=meal['channel_ids'])]
    manifest['segments']=[s for s in manifest['segments'] if s['kind'] not in {'meal','outro','weather','greeting','empty_notices'}]
    rows=app_export.app_segments(manifest,items,'female')
    assert [s['id'] for s in rows]==['ch-a']


def test_mail_masks_token_values(tmp_path):
    from briefing.failure_notice import cell
    assert 'secret' not in cell('Bearer secret')
    assert 'secret' not in cell('KGAT_secret')
