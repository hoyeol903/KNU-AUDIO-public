"""Prepare and verify a private, run-specific Kaggle briefing kernel package."""
import argparse
import base64
from datetime import date, datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from briefing.qwen_tts import MODE
from briefing.model_cache import DATASET_SLUG

ROOT = Path(__file__).resolve().parents[1]
KERNEL_PREFIX = 'knu-audio-briefing'


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def context_for(root, day, run_id, attempt, github_sha, username):
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('날짜는 YYYY-MM-DD 형식이어야 합니다.')
    if not run_id.isdigit() or not attempt.isdigit():
        raise ValueError('GitHub run ID와 attempt는 숫자여야 합니다.')
    if not re.fullmatch(r'[a-z0-9-]{1,39}', username.lower()):
        raise ValueError('KAGGLE_USERNAME 형식이 올바르지 않습니다.')
    if not re.fullmatch(r'[0-9a-f]{7,64}', github_sha.lower()):
        raise ValueError('GitHub commit SHA 형식이 올바르지 않습니다.')
    items = root / 'data/raw' / day / 'items.json'
    if not items.is_file():
        raise FileNotFoundError(f'선택한 날짜의 수집 스냅샷이 없습니다: {day}')
    slug = f'{KERNEL_PREFIX}-{run_id}-{attempt}'
    kernel_id = f'{username.lower()}/{slug}'
    return dict(day=day, run_id=run_id, run_attempt=attempt, github_sha=github_sha.lower(),
                username=username.lower(), kernel_id=kernel_id, input_sha256=sha256_file(items))


def _source_files(root, day):
    files = []
    for folder in ('briefing', 'collector'):
        files.extend(path for path in (root / folder).glob('*.py') if path.is_file())
    files.extend((root / 'config' / name) for name in ('briefing.yaml', 'events.yaml'))
    files.extend((root / 'requirements.txt', root / 'requirements-tts.txt',
                  root / 'scripts/start-ollama-ci.sh', root / 'data/channels.yaml',
                  root / 'data/departments.yaml'))
    files.extend(path for path in (root / 'web/player').iterdir() if path.is_file())
    files.append(root / 'data/raw' / day / 'items.json')
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError('Kaggle 실행에 필요한 프로젝트 파일이 없습니다: ' + ', '.join(str(p) for p in missing))
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def prepare_kernel(root, day, run_id, attempt, github_sha, username, kernel_dir, expected_path, *, batch=None, resume_kernel=None):
    """Package an explicit source/input allowlist and generate the Kaggle kernel script."""
    root = Path(root).resolve()
    kernel_dir = Path(kernel_dir)
    kernel_dir.mkdir(parents=True, exist_ok=True)
    context = context_for(root, day, str(run_id), str(attempt), github_sha, username)
    source_files = _source_files(root, day)
    context['checkpoint_signature'] = hashlib.sha256(''.join(
        path.relative_to(root).as_posix() + ':' + sha256_file(path)
        for path in source_files if not path.is_relative_to(root / 'web')).encode()).hexdigest()
    if batch is not None:
        context['batch'] = batch
        context['resume_kernel'] = resume_kernel
        context['kernel_id'] += f'-b{batch}'
    bundle_io = io.BytesIO()
    with tarfile.open(fileobj=bundle_io, mode='w:gz') as archive:
        for path in source_files:
            archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
        encoded_context = json.dumps(context, ensure_ascii=False, sort_keys=True).encode('utf-8')
        info = tarfile.TarInfo('kaggle-run-context.json')
        info.size = len(encoded_context)
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(encoded_context))
    bundle = bundle_io.getvalue()
    bundle_sha = hashlib.sha256(bundle).hexdigest()
    expected = dict(**context, bundle_sha256=bundle_sha)
    Path(expected_path).write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    wrapper = f'''import base64, hashlib, io, sys, tarfile\nfrom pathlib import Path\n\nBUNDLE_SHA256 = {bundle_sha!r}\nBUNDLE = {base64.b64encode(bundle).decode('ascii')!r}\nraw = base64.b64decode(BUNDLE, validate=True)\nif hashlib.sha256(raw).hexdigest() != BUNDLE_SHA256:\n    raise SystemExit("입력 번들 해시가 일치하지 않습니다")\nroot = Path("/tmp/knu-audio-source").resolve()\nroot.mkdir(parents=True, exist_ok=True)\nwith tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:\n    for item in archive.getmembers():\n        target = (root / item.name).resolve()\n        if (not target.is_relative_to(root) or not (item.isfile() or item.isdir()) or item.issym() or item.islnk()):\n            raise SystemExit("입력 번들에 안전하지 않은 경로가 있습니다")\n    archive.extractall(root)\nsys.path.insert(0, str(root))\nfrom briefing.kaggle_worker import run\nrun(root, BUNDLE_SHA256)\n'''
    (kernel_dir / 'run.py').write_text(wrapper, encoding='utf-8')
    metadata = dict(
        id=context['kernel_id'], title=f"KNU Audio Briefing {run_id}-{attempt}" + (f" B{batch}" if batch is not None else ""),
        code_file='run.py', language='python', kernel_type='script',
        is_private=True, enable_gpu=True, enable_internet=True,
        machine_shape='NvidiaTeslaT4', dataset_sources=[(os.environ.get('KAGGLE_MODEL_OWNER') or context['username']).lower() + '/' + DATASET_SLUG], competition_sources=[],
        kernel_sources=[resume_kernel] if resume_kernel else [], model_sources=[])
    (kernel_dir / 'kernel-metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return expected


def parse_kernel_version(text):
    match = re.search(r'Kernel version\s+(\d+)\s+successfully pushed', text, re.IGNORECASE)
    if not match:
        raise RuntimeError('Kaggle CLI가 실행 버전 번호를 반환하지 않았습니다.')
    return match.group(1)


def parse_kernel_status(text):
    match = re.search(r'KernelWorkerStatus\.([A-Z_]+)', text, re.IGNORECASE)
    if match:
        status = match.group(1).upper()
        return {'COMPLETE': 'complete', 'ERROR': 'failed', 'CANCELLED': 'failed',
                'RUNNING': 'running', 'QUEUED': 'running', 'INITIALIZED': 'running'}.get(status, 'unknown')
    lowered = text.lower()
    if re.search(r'\b(complete|completed|success|succeeded)\b', lowered):
        return 'complete'
    if re.search(r'\b(error|errored|failed|cancelled)\b', lowered):
        return 'failed'
    if re.search(r'\b(queued|running|pending|initializing)\b', lowered):
        return 'running'
    return 'unknown'


def wait_for_kernel(kernel_id, *, version=None, timeout=None, interval=45, runner=subprocess.run, sleep=time.sleep,
                    clock=time.monotonic, report=print):
    deadline = clock() + timeout if timeout is not None else None
    target = f'{kernel_id}/{version}' if version else kernel_id
    command = ['kaggle', 'kernels', 'status', target]
    while True:
        remaining = deadline - clock() if deadline is not None else float('inf')
        if remaining <= 0:
            raise TimeoutError(f'Kaggle kernel {kernel_id}이 {timeout}초 안에 끝나지 않았습니다.')
        result = runner(command, capture_output=True, text=True, check=False,
                        timeout=max(1, int(min(120, remaining))))
        text = (result.stdout or '') + (result.stderr or '')
        if result.returncode:
            raise RuntimeError(f'Kaggle kernel 상태 조회 실패({result.returncode}): {text[-2000:]}')
        status = parse_kernel_status(text)
        report(f'Kaggle kernel {kernel_id}: {status}')
        if status == 'complete':
            return
        if status in {'failed', 'unknown'}:
            raise RuntimeError(f'Kaggle kernel이 정상 완료 상태가 아닙니다: {text[-2000:]}')
        remaining = deadline - clock() if deadline is not None else float('inf')
        if remaining <= 0:
            raise TimeoutError(f'Kaggle kernel {kernel_id}이 {timeout}초 안에 끝나지 않았습니다.')
        sleep(min(interval, remaining))


def verify_output(output_dir, expected_path):
    output_dir = Path(output_dir).resolve()
    expected = json.loads(Path(expected_path).read_text(encoding='utf-8'))
    manifest_path = output_dir / 'briefing-run.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for key in ('day', 'run_id', 'run_attempt', 'github_sha', 'kernel_id', 'input_sha256', 'bundle_sha256'):
        if manifest.get(key) != expected.get(key):
            raise ValueError(f'Kaggle 결과의 {key}가 이번 GitHub 실행과 다릅니다.')
    if (manifest.get('status') != 'complete' or not manifest.get('gpu_name')
            or 't4' not in manifest['gpu_name'].casefold()):
        raise ValueError('NVIDIA T4 GPU 실행 완료 증거가 없습니다.')
    files = manifest.get('files')
    if not isinstance(files, dict) or not {'dist/manifest.json', 'app/segments.json',
                                            'diagnostics/briefing-progress.json'} <= set(files):
        raise ValueError('Kaggle 결과에 필수 산출물이 없습니다.')
    expected_files = set()
    for rel, digest in files.items():
        path = (output_dir / rel).resolve()
        if not path.is_relative_to(output_dir) or not path.is_file():
            raise ValueError(f'Kaggle 산출물 경로가 유효하지 않습니다: {rel}')
        if sha256_file(path) != digest:
            raise ValueError(f'Kaggle 산출물 해시가 맞지 않습니다: {rel}')
        expected_files.add(rel)
    actual_files = {p.relative_to(output_dir).as_posix() for p in output_dir.rglob('*')
                    if p.is_file() and p != manifest_path}
    if actual_files != expected_files:
        raise ValueError('Kaggle 결과 파일 목록이 검증 목록과 다릅니다.')
    dist_path = output_dir / 'dist'
    dist = json.loads((dist_path / 'manifest.json').read_text(encoding='utf-8'))
    app = json.loads((output_dir / 'app/segments.json').read_text(encoding='utf-8'))
    if dist.get('date') != expected['day'] or dist.get('mode') != MODE or app.get('date') != expected['day']:
        raise ValueError('Kaggle 음성 결과의 날짜 또는 모드가 이번 실행과 다릅니다.')
    if not dist.get('segments') or not app.get('segments'):
        raise ValueError('Kaggle 음성 결과가 비어 있습니다.')
    from briefing.daily import verify_publication
    from mutagen.mp3 import MP3
    verify_publication(dist_path, expected['day'])
    app_audio = (output_dir / 'app').resolve()
    for segment in app['segments']:
        relative = Path(segment.get('audio', ''))
        audio = (app_audio / relative).resolve()
        if not relative.name or not audio.is_relative_to(app_audio) or not audio.is_file() or MP3(audio).info.length <= 0:
            raise ValueError('Kaggle 앱용 음성 파일이 유효하지 않습니다.')
    return manifest


def collection_input(root, started_at, previous_input=None):
    root = Path(root).resolve()
    started = datetime.fromisoformat(started_at)
    if started.utcoffset() is None:
        raise ValueError('수집 시작 시각에 시간대가 없습니다.')
    meta = json.loads((root / 'output/app/data/meta.json').read_text(encoding='utf-8'))
    day = meta.get('asOf')
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError('앱 자료의 기준일이 올바르지 않습니다.')
    items_path = root / 'data/raw' / day / 'items.json'
    if not items_path.exists():
        return None
    items = json.loads(items_path.read_text(encoding='utf-8'))
    fields = ('date', 'weather', 'channels', 'schedule')
    if not isinstance(items, dict) or any(field not in items for field in fields):
        raise ValueError('수집 스냅샷의 브리핑 자료가 올바르지 않습니다.')
    if items.get('date') != day:
        raise ValueError('앱 자료와 수집 스냅샷 날짜가 다릅니다.')
    collected = datetime.fromisoformat(items.get('collected_at', ''))
    if collected.utcoffset() is None:
        raise ValueError('수집 스냅샷 생성 시각에 시간대가 없습니다.')
    if collected.astimezone(timezone.utc) < started.astimezone(timezone.utc):
        return None
    if previous_input and Path(previous_input).is_file():
        try:
            previous = json.loads(Path(previous_input).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ValueError('이전 수집 스냅샷을 읽을 수 없습니다.') from exc
        if not isinstance(previous, dict) or any(field not in previous for field in fields):
            raise ValueError('이전 수집 스냅샷의 브리핑 자료가 올바르지 않습니다.')
        if all(items[field] == previous[field] for field in fields):
            return None
    return day


def publish_output(root, output_dir, expected_path):
    root = Path(root).resolve()
    output_dir, expected_path = Path(output_dir).resolve(), Path(expected_path).resolve()
    manifest = verify_output(output_dir, expected_path)
    expected = json.loads(expected_path.read_text(encoding='utf-8'))
    day = expected.get('day')
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError('Kaggle 결과 날짜가 올바르지 않습니다.')
    target = root / 'output/app/data/briefing'
    current_path = target / 'segments.json'
    current = None
    if current_path.is_file():
        current = json.loads(current_path.read_text(encoding='utf-8'))
        current_day = current.get('date')
        if isinstance(current_day, str) and current_day > day:
            return {'skipped': True, 'reason': '이미 더 최신 음성이 게시되어 있습니다.'}
        previous_record = root / 'data/runs' / f'briefing-kaggle-{day}.json'
        if current_day == day and previous_record.is_file():
            previous = json.loads(previous_record.read_text(encoding='utf-8'))
            previous_order = (int(previous['run_id']), int(previous['run_attempt']))
            incoming_order = (int(expected['run_id']), int(expected['run_attempt']))
            if previous_order > incoming_order:
                return {'skipped': True, 'reason': '같은 날짜의 더 최신 실행 결과가 게시되어 있습니다.'}
    items_path = root / 'data/raw' / day / 'items.json'
    if (root / '.git').exists():
        sha = expected.get('github_sha', '')
        if not re.fullmatch(r'[0-9a-f]{7,64}', sha):
            raise ValueError('원래 실행의 commit SHA가 올바르지 않습니다.')
        original = subprocess.run(['git', 'show', f'{sha}:data/raw/{day}/items.json'],
                                  cwd=root, capture_output=True, check=False)
        if original.returncode:
            raise ValueError('생성 당시 commit의 수집 스냅샷을 읽을 수 없습니다.')
        input_bytes = original.stdout
    else:
        input_bytes = items_path.read_bytes()
    items = json.loads(input_bytes)
    if items.get('date') != day or hashlib.sha256(input_bytes).hexdigest() != expected.get('input_sha256'):
        raise ValueError('원래 수집 스냅샷이 Kaggle 실행 입력과 다릅니다.')

    source_app = output_dir / 'app'
    app = json.loads((source_app / 'segments.json').read_text(encoding='utf-8'))
    if app.get('date') != day:
        raise ValueError('Kaggle 앱 브리핑 날짜가 실행 날짜와 다릅니다.')
    files = {'segments.json'}
    for segment in app.get('segments', []):
        relative = Path(segment.get('audio', ''))
        source = (source_app / relative).resolve()
        if (not relative.name or relative.is_absolute() or relative.parent != Path('.')
                or relative.suffix.lower() != '.mp3' or '..' in relative.parts
                or not source.is_relative_to(source_app) or not source.is_file()):
            raise ValueError('Kaggle 앱 브리핑에 잘못된 음성 경로가 있습니다.')
        files.add(relative.as_posix())
    file_hashes = {name: sha256_file(source_app / name) for name in sorted(files)}
    record = dict(
        input_date=day, verified=True, run_id=manifest['run_id'], run_attempt=manifest['run_attempt'],
        github_sha=manifest['github_sha'], kernel_id=manifest['kernel_id'],
        kernel_version=expected.get('kernel_version'), gpu=manifest['gpu_name'],
        input_sha256=manifest['input_sha256'], bundle_sha256=manifest['bundle_sha256'],
        app_file_sha256=file_hashes)

    target = root / 'output/app/data/briefing'
    run_record = root / 'data/runs' / f'briefing-kaggle-{day}.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    run_record.parent.mkdir(parents=True, exist_ok=True)
    # This isolated checkout becomes visible only when the workflow pushes its verified commit.
    # 최신 음성 참조를 바꾼 뒤 보관 기간이 지난 파일만 정리한다.
    with tempfile.TemporaryDirectory(prefix='.kaggle-publish-', dir=target.parent) as temporary:
        temporary = Path(temporary)
        staged_app = temporary / 'briefing'
        staged_app.mkdir()
        for name in sorted(files):
            shutil.copy2(source_app / name, staged_app / name)
        for name, digest in file_hashes.items():
            if sha256_file(staged_app / name) != digest:
                raise ValueError(f'Kaggle 앱 파일 복사 검증에 실패했습니다: {name}')
        from collector.store import save_json
        target.mkdir(parents=True, exist_ok=True)
        for name in sorted(files - {'segments.json'}):
            os.replace(staged_app / name, target / name)
        save_json(record, run_record)
        os.replace(staged_app / 'segments.json', target / 'segments.json')
    from briefing.audio_retention import retain_audio
    retain_audio(target, day, files, records=root / 'data/runs', previous=current)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--date', required=True)
    prepare.add_argument('--run-id', required=True)
    prepare.add_argument('--run-attempt', required=True)
    prepare.add_argument('--github-sha', required=True)
    prepare.add_argument('--username', required=True)
    prepare.add_argument('--kernel-dir', type=Path, required=True)
    prepare.add_argument('--expected', type=Path, required=True)
    wait = sub.add_parser('wait')
    wait.add_argument('--kernel-id', required=True)
    wait.add_argument('--version')
    wait.add_argument('--timeout', type=int, help='명시한 경우에만 대기 시간 제한 (초)')
    wait.add_argument('--interval', type=int, default=45)
    verify = sub.add_parser('verify')
    verify.add_argument('--output', type=Path, required=True)
    verify.add_argument('--expected', type=Path, required=True)
    collection = sub.add_parser('collection-input')
    collection.add_argument('--started-at', required=True)
    collection.add_argument('--previous-input', type=Path)
    publish = sub.add_parser('publish')
    publish.add_argument('--output', type=Path, required=True)
    publish.add_argument('--expected', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        context = prepare_kernel(ROOT, args.date, args.run_id, args.run_attempt,
                                 args.github_sha, args.username, args.kernel_dir, args.expected)
        print(json.dumps({key: context[key] for key in ('day', 'kernel_id', 'input_sha256', 'bundle_sha256')}))
    elif args.command == 'wait':
        wait_for_kernel(args.kernel_id, version=args.version, timeout=args.timeout, interval=args.interval)
    elif args.command == 'verify':
        manifest = verify_output(args.output, args.expected)
        print(f"Kaggle GPU 결과 검증 완료: {manifest['day']} · {manifest['gpu_name']}")
    elif args.command == 'collection-input':
        print(collection_input(ROOT, args.started_at, args.previous_input) or '')
    else:
        record = publish_output(ROOT, args.output, args.expected)
        print(record["reason"] if record.get("skipped") else f"Kaggle GPU 결과 게시 준비 완료: {record['input_date']}")


if __name__ == '__main__':
    main()
