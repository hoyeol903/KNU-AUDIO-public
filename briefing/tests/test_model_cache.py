import hashlib
import json
from pathlib import Path

import pytest

from briefing import model_cache
from briefing.qwen_tts import MODEL, cached_model_source


def fixture(root, monkeypatch):
    directory = root / 'dataset' / 'model'
    directory.mkdir(parents=True)
    files = {}
    for name in model_cache.REQUIRED_FILES:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'model test file')
        files[name] = dict(size=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    manifest = dict(model=MODEL, revision=model_cache.REVISION, files=files)
    marker = directory / 'model-cache.json'
    marker.write_text(json.dumps(manifest))
    monkeypatch.setattr(model_cache, 'MANIFEST_SHA256', hashlib.sha256(marker.read_bytes()).hexdigest())
    return directory, marker, manifest


def test_mounted_model_is_used_directly_without_network_or_copy(tmp_path, monkeypatch):
    directory, _, _ = fixture(tmp_path, monkeypatch)
    assert model_cache.find_model_directory(tmp_path) == directory
    monkeypatch.setenv('KNU_TTS_MODEL_PATH', str(directory))
    assert cached_model_source(MODEL, tmp_path / 'empty-hf-cache') == str(directory)
    assert not (tmp_path / 'empty-hf-cache').exists()


@pytest.mark.parametrize('problem', ['missing', 'hash', 'manifest', 'wrong-model', 'path'])
def test_bad_dataset_fails_instead_of_downloading_another_model(tmp_path, monkeypatch, problem):
    directory, marker, manifest = fixture(tmp_path, monkeypatch)
    if problem == 'missing':
        (directory / 'model.safetensors').unlink()
    elif problem == 'hash':
        (directory / 'model.safetensors').write_bytes(b'wrong test file')
    elif problem == 'manifest':
        marker.write_text('{}')
    elif problem == 'wrong-model':
        manifest['model'] = 'wrong'
        marker.write_text(json.dumps(manifest))
        monkeypatch.setattr(model_cache, 'MANIFEST_SHA256', hashlib.sha256(marker.read_bytes()).hexdigest())
    else:
        manifest['files']['../outside'] = dict(size=1, sha256='0' * 64)
        marker.write_text(json.dumps(manifest))
        monkeypatch.setattr(model_cache, 'MANIFEST_SHA256', hashlib.sha256(marker.read_bytes()).hexdigest())
    monkeypatch.setenv('KNU_TTS_MODEL_PATH', str(directory))
    with pytest.raises((ValueError, FileNotFoundError)):
        cached_model_source(MODEL, tmp_path / 'hf-cache')


def test_missing_mount_and_wrong_requested_model_are_explicit_errors(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='데이터셋 연결'):
        model_cache.find_model_directory(tmp_path)
    directory, _, _ = fixture(tmp_path, monkeypatch)
    monkeypatch.setenv('KNU_TTS_MODEL_PATH', str(directory))
    with pytest.raises(ValueError, match='요청한 음성 모델'):
        cached_model_source('wrong', tmp_path)


def test_tts_loader_receives_verified_dataset_directory(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock
    from briefing.qwen_tts import QwenTTS
    directory, _, _ = fixture(tmp_path, monkeypatch)
    monkeypatch.setenv('KNU_TTS_MODEL_PATH', str(directory))
    factory = Mock()
    factory.from_pretrained.return_value = SimpleNamespace(
        get_supported_speakers=lambda: ['sohee', 'aiden'], get_supported_languages=lambda: ['Korean'])
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False), float32='float32'))
    monkeypatch.setitem(sys.modules, 'qwen_tts', SimpleNamespace(Qwen3TTSModel=factory))
    QwenTTS()._load(MODEL)
    factory.from_pretrained.assert_called_once_with(
        str(directory), device_map='cpu', dtype='float32', attn_implementation='eager')
