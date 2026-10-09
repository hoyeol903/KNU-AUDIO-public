"""완료된 Kaggle 묶음의 캐시를 해시 검증 후 다음 실행에 연결한다."""
import hashlib
import json
from pathlib import Path
import shutil


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(cache, target, context, failures, status):
    cache, target = Path(cache), Path(target)
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    for source in sorted(cache.rglob('*')):
        if source.is_file() and source.suffix in {'.mp3', '.json'}:
            relative = source.relative_to(cache)
            destination = target / 'cache' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            files[relative.as_posix()] = checksum(destination)
    from collector.store import save_json
    save_json(dict(signature=context['checkpoint_signature'], day=context['day'],
                   kernel_id=context['kernel_id'], status=status, files=files, failed_audio=failures), target / 'state.json')


def restore(source, cache, signature):
    source, cache = Path(source).resolve(), Path(cache)
    state = json.loads((source / 'state.json').read_text())
    if state['signature'] != signature:
        raise ValueError('이어가기 자료의 원문·코드·모델 설정이 이번 실행과 다릅니다.')
    validated = []
    for name, expected in state['files'].items():
        relative = Path(name)
        path = (source / 'cache' / relative).resolve()
        if (relative.is_absolute() or '..' in relative.parts or relative.suffix not in {'.mp3', '.json'}
                or not path.is_relative_to(source / 'cache') or not path.is_file() or checksum(path) != expected):
            raise ValueError('이어가기 캐시의 경로 또는 파일 해시가 잘못되었습니다.')
        validated.append((relative, path))
    for relative, path in validated:
        destination = cache / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return state['failed_audio']
