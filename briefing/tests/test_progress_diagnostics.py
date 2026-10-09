import json

import pytest
import yaml
from unittest.mock import Mock

from briefing import app_export
from briefing.build import ROOT, ProgressRecorder, build
from briefing.slm import generate_segments


class FakeSLM:
    def identity(self):
        return 'test-model-digest'

    def generate(self, payload, errors):
        return '공지 안내는 5일이에요.'


def segment():
    return dict(id='notice-test:1', kind='notice', notice_id='n1', channel_ids=['c'], url='https://example.org/n1',
                title='공지', generation='slm', source_text='5일 마감', reference='5일 마감')


def test_script_progress_records_elapsed_and_resource_usage_without_text(tmp_path):
    path = tmp_path / 'progress.json'
    progress = ProgressRecorder(path)
    generate_segments([segment()], FakeSLM(), tmp_path / 'cache', tmp_path / 'review.json', progress=progress)

    saved = json.loads(path.read_text())
    events = saved['events']
    assert [(event['stage'], event['status']) for event in events] == [
        ('script', 'started'), ('script', 'completed')]
    assert events[-1]['unitElapsedSeconds'] is not None
    assert events[-1]['cpuUserSeconds'] >= 0 and events[-1]['peakMemoryBytes'] > 0
    assert '5일 마감' not in path.read_text()


def test_script_failure_is_recorded_without_overwriting_failure_details(tmp_path):
    class BrokenSLM(FakeSLM):
        def generate(self, payload, errors):
            return '내용이 일치하지 않고 999999원입니다.'

    path = tmp_path / 'progress.json'
    progress = ProgressRecorder(path)
    result = generate_segments([segment()], BrokenSLM(), tmp_path / 'cache', tmp_path / 'review.json', progress=progress)

    assert result[0]['_skip_notice']
    assert json.loads(path.read_text())['events'][-1]['status'] == 'skipped'
    report = json.loads((tmp_path / 'review.json').read_text())
    assert report['status'] == 'partial' and report['skipped_notices']
    assert len(report['segments'][0]['attempts']) == 3
    assert report['segments'][0]['attempts'][-1]['attempt'] == 'source_fallback'


def test_non_notice_revision_is_also_unchecked(tmp_path):
    class BrokenSLM(FakeSLM):
        def generate(self, payload, errors):
            return '내용이 일치하지 않고 999999원입니다.'
    row = segment(); row['kind'] = 'events'
    generate_segments([row], BrokenSLM(), tmp_path / 'cache', tmp_path / 'review.json')
    assert row['review']['status'] == 'revision-unchecked'


def test_revised_notice_reaches_tts_and_export(tmp_path, monkeypatch):
    data = json.loads((ROOT / 'data/raw/2026-10-03/items.json').read_text())
    channel = next(row for row in data['channels'] if len(row['notices']) >= 2)
    bad = channel['notices'][0]
    bad['title'] = '검수 실패 공지'
    bad['body'] = '검수 실패 시험 내용입니다.'
    bad['deadline'] = None
    bad['dday'] = None
    bad['reason'] = 'new'
    data['channels'] = [dict(channel_id=channel['channel_id'], notices=[bad], meals=[])]
    input_path = tmp_path / 'items.json'
    input_path.write_text(json.dumps(data), encoding='utf-8')

    class OneBadSLM(FakeSLM):
        def generate(self, payload, errors):
            if '검수 실패' in payload['title']:
                return '원문에 없는 금액 999999원입니다.' if not errors else '검수 실패 공지를 안내해요.'
            return '공지 내용을 안내해요.'

    client = Mock()
    client.synthesize.return_value = b'mock audio'
    monkeypatch.setattr('briefing.build.audio_info', lambda raw: 1.0)
    output = tmp_path / 'dist'
    report = build(input_path, output=output, cache=tmp_path / 'cache', allow_archive=True,
                   client=client, slm_client=OneBadSLM())
    assert not report['skipped_notices']
    assert client.synthesize.called
    manifest = json.loads((output / 'manifest.json').read_text())
    exported = app_export.app_segments(manifest, data, 'female')
    cards = [card for row in exported for card in row['items']]
    assert bad['id'] in {card['postId'] for card in cards}
    assert any(card['postId'] for card in cards)


def test_all_revised_notices_are_exported_with_empty_fallback(tmp_path, monkeypatch):
    data = json.loads((ROOT / 'data/raw/2026-10-03/items.json').read_text())
    for channel in data['channels']:
        channel['notices'] = channel['notices'][:1]
        for notice in channel['notices']:
            notice['title'] = '전부 실패하는 공지'
            notice['body'] = '내용'
    input_path = tmp_path / 'items.json'
    input_path.write_text(json.dumps(data), encoding='utf-8')
    class AllBadSLM(FakeSLM):
        def generate(self, payload, errors):
            return '없는 정보 999999입니다.' if payload['kind'] == 'notice' else '오늘의 안내입니다.'
    client = Mock(); client.synthesize.return_value = b'mock audio'
    monkeypatch.setattr('briefing.build.audio_info', lambda raw: 1.0)
    output = tmp_path / 'dist'
    report = build(input_path, output=output, cache=tmp_path / 'cache', allow_archive=True,
                   client=client, slm_client=AllBadSLM())
    manifest = json.loads((output / 'manifest.json').read_text())
    rows = app_export.app_segments(manifest, data, 'female')
    assert report['skipped_notices']
    assert not any(s['kind'] == 'notice' for s in manifest['segments'])
    assert {'empty', 'outro'} <= {row['channel_id'] for row in rows}


def test_plan_records_progress_to_injected_path(tmp_path):
    path = tmp_path / 'progress.json'
    report = build(ROOT / 'data/raw/2026-10-03/items.json', plan=True,
                   cache=tmp_path / 'cache', slm_client=FakeSLM(), progress=ProgressRecorder(path))
    saved = json.loads(path.read_text())
    assert report['slm_segments'] > 0
    assert saved['stage'] == 'plan' and saved['status'] == 'completed'


def test_workflow_artifacts_failures_and_branch_publish_guard():
    workflow = yaml.safe_load((ROOT / '.github/workflows/briefing.yml').read_text())
    steps = workflow['jobs']['briefing']['steps']
    checkout = next(step for step in steps if step.get('uses') == 'actions/checkout@v7')
    build_step = next(step for step in steps if step.get('name') == '대본과 음성 생성')
    assert "verify_publication(Path('dist'), '${{ steps.day.outputs.day }}')" in build_step['run']
    assert checkout['with']['ref'] == '${{ github.ref }}'
    saves = [step for step in steps if step.get('uses') == 'actions/cache/save@v6']
    assert len(saves) == 2 and all(step['if'] == 'always()' for step in saves)
    artifacts = [step for step in steps if step.get('uses') == 'actions/upload-artifact@v7']
    diagnostics = next(step for step in artifacts if '진단' in step['name'])
    assert diagnostics['if'] == 'always()'
    assert 'output/briefing-progress.json' in diagnostics['with']['path']
    assert '${{ runner.temp }}/ollama.log' in diagnostics['with']['path']
    audio_cache = next(step for step in steps if step.get('id') == 'audio-cache')
    audio_save = next(step for step in saves if '대본·음성' in step.get('name', ''))
    assert '!.cache/briefing/.build-lock' in audio_cache['with']['path']
    assert '!.cache/briefing/.build-lock' in audio_save['with']['path']
    publish = next(step for step in steps if step.get('name') == 'main에 저장하고 배포 실행')
    assert 'github.event.repository.default_branch' in publish['if']
