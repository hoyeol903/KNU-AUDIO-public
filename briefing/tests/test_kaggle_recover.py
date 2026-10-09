import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from briefing import kaggle_recover as recovery


def fixture(tmp_path, monkeypatch, *, requested=True, complete=True, branch='main'):
    monkeypatch.setenv('GH_REPO', 'owner/repo')
    context = {'run_id': '123', 'run_attempt': '1', 'github_sha': 'a' * 40,
               'kernel_id': 'muyahoyeol/knu-audio-briefing-123-1-b9', 'day': '2026-10-09'}
    def gh(*args):
        if args[0] == 'api':
            if args[1].endswith('/runs/123'):
                return json.dumps({'head_branch': branch, 'path': '.github/workflows/briefing-kaggle.yml',
                                   'run_attempt': 1, 'head_sha': 'a' * 40})
            return json.dumps({'default_branch': 'main'})
        original = Path(args[-1]); original.mkdir(parents=True)
        (original / 'expected.json').write_text(json.dumps(context))
        (original / 'publish-requested.txt').write_text(str(requested).lower())
        return ''
    monkeypatch.setattr(recovery, 'gh', gh)
    wait = Mock(); monkeypatch.setattr(recovery.kaggle, 'wait_for_kernel', wait)
    verify = Mock(); monkeypatch.setattr(recovery.kaggle, 'verify_output', verify)
    def download(args):
        output = Path(args[args.index('--path') + 1]) / 'briefing-artifacts/checkpoint'
        output.mkdir(parents=True)
        (output / 'state.json').write_text(json.dumps({'status': 'complete' if complete else 'pending'}))
    monkeypatch.setattr(recovery, 'cli', download)
    return wait, verify


def test_recover_uses_original_context_and_does_not_generate_audio(tmp_path, monkeypatch):
    wait, verify = fixture(tmp_path, monkeypatch)
    assert recovery.recover('123', root=tmp_path)
    wait.assert_called_once_with('muyahoyeol/knu-audio-briefing-123-1-b9', version='1', interval=60)
    verify.assert_called_once()
    assert json.loads((tmp_path / 'expected.json').read_text())['kernel_version'] == 1


def test_recover_respects_disabled_publication(tmp_path, monkeypatch):
    wait, verify = fixture(tmp_path, monkeypatch, requested=False)
    assert not recovery.recover('123', root=tmp_path)
    wait.assert_not_called(); verify.assert_not_called()


@pytest.mark.parametrize('options', [{'complete': False}, {'branch': 'feature'}])
def test_recover_rejects_partial_results_and_other_branches(tmp_path, monkeypatch, options):
    _, verify = fixture(tmp_path, monkeypatch, **options)
    with pytest.raises(ValueError):
        recovery.recover('123', root=tmp_path)
    verify.assert_not_called()


def test_recovery_workflow_keeps_waiting_separate_from_serialized_publication():
    import yaml
    workflow = yaml.safe_load(Path('.github/workflows/briefing-kaggle-recover.yml').read_text())
    assert set(workflow['jobs']) == {'recover', 'publish'}
    assert workflow['jobs']['publish']['needs'] == 'recover'
    assert workflow['jobs']['publish']['concurrency']['group'] == 'knu-collector-writer'
    assert 'concurrency' not in workflow['jobs']['recover']
    event = workflow.get('on', workflow.get(True))
    assert event['workflow_run']['workflows'] == ['Kaggle GPU 브리핑 생성']
