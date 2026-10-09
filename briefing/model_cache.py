"""Kaggle에 미리 올린 고정 버전 음성 모델을 검증해 읽는다."""
import hashlib
import json
from pathlib import Path

MODEL = 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
REVISION = '0c0e3051f131929182e2c023b9537f8b1c68adfe'
DATASET_SLUG = 'knu-audio-qwen3-tts-17b-0c0e3051'
MANIFEST_SHA256 = '41a458e85ca35fecdd66e3073a4225c7fb558462c0837dfae76756077740b7b2'
REQUIRED_FILES = ('config.json', 'model.safetensors', 'generation_config.json',
                  'tokenizer_config.json', 'vocab.json', 'merges.txt',
                  'preprocessor_config.json', 'speech_tokenizer/config.json',
                  'speech_tokenizer/model.safetensors', 'speech_tokenizer/preprocessor_config.json')


def metadata(directory):
    directory = Path(directory)
    raw = (directory / 'model-cache.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError('저장된 음성 모델의 검증 목록이 고정 버전과 다릅니다.')
    manifest = json.loads(raw)
    if manifest.get('model') != MODEL or manifest.get('revision') != REVISION:
        raise ValueError('저장된 음성 모델 이름 또는 버전이 다릅니다.')
    if not set(REQUIRED_FILES) <= set(manifest.get('files', {})):
        raise ValueError('저장된 음성 모델에 필수 파일이 없습니다.')
    return manifest


def find_model_directory(input_root):
    matches = []
    for marker in Path(input_root).rglob('model-cache.json'):
        try:
            manifest = metadata(marker.parent)
        except (OSError, ValueError):
            continue
        if manifest['revision'] == REVISION:
            matches.append(marker.parent)
    if len(matches) != 1:
        raise ValueError('연결된 고정 버전 음성 모델을 하나로 찾지 못했습니다. Kaggle 데이터셋 연결을 확인하세요.')
    return matches[0]


def verify_model_directory(directory):
    directory = Path(directory).resolve()
    manifest = metadata(directory)
    for name, expected in manifest['files'].items():
        relative = Path(name)
        path = (directory / relative).resolve()
        if (relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(directory)
                or not path.is_file() or path.stat().st_size != expected['size']):
            raise ValueError(f'저장된 음성 모델의 경로 또는 파일 크기가 잘못되었습니다: {name}')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected['sha256']:
            raise ValueError(f'저장된 음성 모델의 파일 해시가 다릅니다: {name}')
    return str(directory)
