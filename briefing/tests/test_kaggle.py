import base64
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from briefing import kaggle, kaggle_worker


def test_worker_bootstraps_isolated_venv_and_stops_inside_it(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    root.mkdir()
    runtime = tmp_path / 'runtime'
    venv = runtime / 'venv'
    calls = []
    monkeypatch.setattr(kaggle_worker.subprocess, 'run', lambda command, **kwargs: calls.append((command, kwargs)))
    monkeypatch.setattr(kaggle_worker.sys, 'prefix', str(tmp_path / 'system'))

    assert kaggle_worker._bootstrap_runtime(root, 'bundle-sha', runtime) is True
    assert calls[0][0] == [kaggle_worker.sys.executable, '-m', 'venv', '--without-pip', str(venv)]
    assert calls[1][0] == [kaggle_worker.sys.executable, '-m', 'pip', '--python', str(venv / 'bin/python'),
                           'install', '--disable-pip-version-check', 'pip']
    assert calls[2][0][:2] == [str(venv / 'bin/python'), '-c']
    assert calls[2][0][2:] == ['import sys; from briefing.kaggle_worker import run; run(*sys.argv[1:])',
                               str(root), 'bundle-sha']
    assert calls[2][1]['cwd'] == root and calls[2][1]['check'] is True
    assert calls[2][1]['env']['PATH'].split(':')[0] == str(venv / 'bin')

    monkeypatch.setattr(kaggle_worker.sys, 'prefix', str(venv))
    assert kaggle_worker._bootstrap_runtime(root, 'bundle-sha', runtime) is False
    assert len(calls) == 3


def test_package_is_private_t4_and_contains_only_runtime_snapshot(tmp_path):
    kernel_dir = tmp_path / 'kernel'
    expected_path = tmp_path / 'expected.json'
    expected = kaggle.prepare_kernel(
        kaggle.ROOT, '2026-10-05', '123456', '1', 'a' * 40, 'muyahoyeol', kernel_dir, expected_path)
    metadata = json.loads((kernel_dir / 'kernel-metadata.json').read_text())
    assert metadata['id'] == expected['kernel_id'] == 'muyahoyeol/knu-audio-briefing-123456-1'
    assert metadata['is_private'] is True and metadata['enable_gpu'] is True
    assert metadata['machine_shape'] == 'NvidiaTeslaT4' and metadata['enable_internet'] is True
    from briefing.model_cache import DATASET_SLUG
    assert metadata['dataset_sources'] == ['muyahoyeol/' + DATASET_SLUG]
    assert expected['day'] == '2026-10-05'

    runner = (kernel_dir / 'run.py').read_text()
    payload = re.search(r"BUNDLE = '([A-Za-z0-9+/=]+)'", runner).group(1)
    bundle = base64.b64decode(payload)
    assert hashlib.sha256(bundle).hexdigest() == expected['bundle_sha256']
    with tarfile.open(fileobj=io.BytesIO(bundle), mode='r:gz') as archive:
        names = set(archive.getnames())
    assert 'data/raw/2026-10-05/items.json' in names
    assert 'data/channels.yaml' in names and 'data/departments.yaml' in names
    assert 'briefing/kaggle_worker.py' in names and 'scripts/start-ollama-ci.sh' in names
    assert not any(name.startswith(('briefing/tests/', 'collector/tests/')) or name.startswith('.env')
                   for name in names)
    assert 'KAGGLE_API_TOKEN' not in runner


def test_explicit_historical_input_keeps_its_selected_date(tmp_path):
    expected = kaggle.prepare_kernel(
        kaggle.ROOT, '2026-10-05', '123457', '1', 'b' * 40, 'muyahoyeol',
        tmp_path / 'kernel', tmp_path / 'expected.json')
    assert json.loads((tmp_path / 'expected.json').read_text())['day'] == '2026-10-05'
    assert expected['input_sha256'] == kaggle.sha256_file(kaggle.ROOT / 'data/raw/2026-10-05/items.json')


def test_kernel_push_version_and_status_parsing():
    assert kaggle.parse_kernel_version('Kernel version 7 successfully pushed.') == '7'
    with pytest.raises(RuntimeError, match='버전 번호'):
        kaggle.parse_kernel_version('Kernel push error: GPU quota reached')
    assert kaggle.parse_kernel_status('x has status "KernelWorkerStatus.COMPLETE"') == 'complete'
    assert kaggle.parse_kernel_status('x has status "KernelWorkerStatus.RUNNING"') == 'running'
    assert kaggle.parse_kernel_status('x has status "KernelWorkerStatus.ERROR"') == 'failed'
    assert kaggle.parse_kernel_status('unknown output') == 'unknown'


def test_wait_for_kernel_bounds_status_calls_and_returns_on_complete():
    clock_value = [0.0]
    calls = []

    def runner(command, **kwargs):
        calls.append(kwargs)
        status = 'RUNNING' if len(calls) == 1 else 'COMPLETE'
        return SimpleNamespace(returncode=0, stdout=f'KernelWorkerStatus.{status}', stderr='')

    def sleep(duration):
        clock_value[0] += duration

    kaggle.wait_for_kernel('muyahoyeol/run-123', timeout=180, interval=45,
                           runner=runner, sleep=sleep, clock=lambda: clock_value[0], report=lambda _: None)
    assert len(calls) == 2 and all(call['timeout'] <= 120 for call in calls)


def test_wait_for_kernel_fails_on_kernel_error_without_retry():
    runner = Mock(return_value=SimpleNamespace(returncode=0, stdout='KernelWorkerStatus.ERROR', stderr=''))
    with pytest.raises(RuntimeError, match='정상 완료'):
        kaggle.wait_for_kernel('muyahoyeol/run-124', runner=runner, sleep=Mock(), report=lambda _: None)
    runner.assert_called_once()


def test_output_verification_checks_identity_hashes_and_audio_paths(tmp_path, monkeypatch):
    out = tmp_path / 'output'
    expected = dict(day='2026-10-05', run_id='12', run_attempt='1', github_sha='c' * 40,
                    kernel_id='muyahoyeol/knu-audio-briefing-12-1', input_sha256='1' * 64,
                    bundle_sha256='2' * 64)
    (out / 'dist/audio').mkdir(parents=True)
    (out / 'app').mkdir()
    (out / 'diagnostics').mkdir()
    files = {
        'dist/manifest.json': dict(date=expected['day'], mode='slm-qwen3-tts', segments=[{}]),
        'dist/audio/clip.mp3': b'fake-mp3',
        'app/segments.json': dict(date=expected['day'], segments=[dict(audio='clip.mp3')]),
        'app/clip.mp3': b'fake-mp3',
        'diagnostics/briefing-progress.json': dict(status='completed'),
    }
    hashes = {}
    for rel, value in files.items():
        path = out / rel
        if isinstance(value, bytes):
            path.write_bytes(value)
            digest = hashlib.sha256(value).hexdigest()
        else:
            path.write_text(json.dumps(value))
            digest = kaggle.sha256_file(path)
        hashes[rel] = digest
    run_manifest = dict(**expected, status='complete', gpu_name='Tesla T4', files=hashes)
    (out / 'briefing-run.json').write_text(json.dumps(run_manifest))
    expected_path = tmp_path / 'expected.json'
    expected_path.write_text(json.dumps(expected))

    monkeypatch.setattr('briefing.daily.verify_publication', lambda *_: None)
    class FakeMP3:
        info = SimpleNamespace(length=1.0)
    monkeypatch.setattr('mutagen.mp3.MP3', lambda *_: FakeMP3())
    assert kaggle.verify_output(out, expected_path)['gpu_name'] == 'Tesla T4'

    run_manifest['github_sha'] = 'd' * 40
    (out / 'briefing-run.json').write_text(json.dumps(run_manifest))
    with pytest.raises(ValueError, match='github_sha'):
        kaggle.verify_output(out, expected_path)


def test_default_wait_continues_after_two_hours():
    times=iter([0, 8000, 16000, 24000])
    results=iter(['running', 'complete'])
    def runner(*args, **kwargs):
        assert kwargs['timeout']==120
        return SimpleNamespace(returncode=0,stdout=next(results),stderr='')
    kaggle.wait_for_kernel('muyahoyeol/run-long',runner=runner,clock=lambda: next(times),sleep=Mock(),report=lambda _:None)
