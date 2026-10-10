"""Worker invoked by the private, GPU-backed Kaggle script."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _gpu_info():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('Kaggle CUDA GPU가 보이지 않습니다. CPU 대체 실행은 허용하지 않습니다.')
    name = torch.cuda.get_device_name(0)
    if 't4' not in name.casefold():
        raise RuntimeError(f'요청한 NVIDIA T4 GPU가 아닙니다: {name}')
    print(f'보이는 GPU 수: {torch.cuda.device_count()}', flush=True)
    return dict(gpu_name=name, cuda_version=torch.version.cuda, torch_version=torch.__version__)


def _ensure_system_tools():
    required = ('curl', 'zstd', 'ffmpeg')
    missing = [tool for tool in required if not shutil.which(tool)]
    if not missing:
        return
    if not shutil.which('apt-get'):
        raise RuntimeError('Kaggle 실행 이미지에 필요한 도구가 없습니다: ' + ', '.join(missing))
    subprocess.run(['apt-get', 'update'], check=True, timeout=300)
    subprocess.run(['apt-get', 'install', '-y', 'curl', 'zstd', 'ffmpeg'], check=True, timeout=300)
    still_missing = [tool for tool in required if not shutil.which(tool)]
    if still_missing:
        raise RuntimeError('시스템 도구 설치 후에도 실행 파일을 찾지 못했습니다: ' + ', '.join(still_missing))


def _copy_file(source, destination):
    if Path(source).is_file():
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _tail(path, lines=80):
    try:
        return '\n'.join(Path(path).read_text(encoding='utf-8', errors='replace').splitlines()[-lines:])
    except OSError:
        return ''


def _bootstrap_runtime(root, bundle_sha, runtime_dir):
    venv_dir = Path(runtime_dir) / 'venv'
    venv_python = venv_dir / 'bin/python'
    if Path(sys.prefix).resolve() == venv_dir.resolve():
        return False

    Path(runtime_dir).mkdir(parents=True, exist_ok=True)
    if not venv_python.exists():
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv_dir)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', '--python', str(venv_python),
                    'install', '--disable-pip-version-check', 'pip'], check=True)
    env = os.environ.copy()
    env['PATH'] = str(venv_dir / 'bin') + os.pathsep + env.get('PATH', '')
    subprocess.run([str(venv_python), '-c',
                    'import sys; from briefing.kaggle_worker import run; run(*sys.argv[1:])',
                    str(root), bundle_sha], cwd=root, env=env, check=True)
    return True


def _package_outputs(root, context, bundle_sha, gpu, run_dir, runtime_dir):
    from collector.store import save_json

    root, run_dir = Path(root), Path(run_dir)
    dist = root / 'dist'
    app = root / 'output/app/data/briefing'
    diagnostics = run_dir / 'diagnostics'
    diagnostics.mkdir(parents=True, exist_ok=True)
    if dist.is_dir():
        shutil.copytree(dist, run_dir / 'dist', dirs_exist_ok=True)
    if app.is_dir():
        shutil.copytree(app, run_dir / 'app', dirs_exist_ok=True)
    for filename in ('briefing-progress.json', 'briefing-report.json', 'review.json'):
        _copy_file(root / 'output' / filename, diagnostics / filename)
    _copy_file(Path(runtime_dir) / 'ollama.log', diagnostics / 'ollama.log')
    save_json(gpu, run_dir / 'gpu-info.json')

    files = {}
    for path in sorted(run_dir.rglob('*')):
        if path.is_file() and path.name != 'briefing-run.json':
            files[path.relative_to(run_dir).as_posix()] = _sha256(path)
    run_manifest = dict(status='complete', day=context['day'], run_id=context['run_id'],
                        run_attempt=context['run_attempt'], github_sha=context['github_sha'],
                        kernel_id=context['kernel_id'], input_sha256=context['input_sha256'],
                        bundle_sha256=bundle_sha, gpu_name=gpu['gpu_name'],
                        cuda_version=gpu['cuda_version'], torch_version=gpu['torch_version'], files=files)
    save_json(run_manifest, run_dir / 'briefing-run.json')



# 커널 하나가 음성 생성에 쓰는 시간. 넘으면 저장하고 다음 커널에서 잇는다.
# 커널마다 패키지 설치·모델 적재가 반복되므로, 강제 종료 때 잃어도 되는 범위에서 길게 잡는다.
AUDIO_BATCH_SECONDS = 2 * 60 * 60


def prepare_slm(root, items, cache, runtime_dir, env, github_path):
    from briefing.build import read_yaml
    from briefing.content import create_segments
    from briefing.slm import cached_provider
    config = read_yaml(root / 'config/briefing.yaml')
    segments, _ = create_segments(items, read_yaml(root / 'data/channels.yaml'),
                                  config, read_yaml(root / 'config/events.yaml'))
    provider = cached_provider(segments, config['slm'], cache)
    if provider is not None:
        print('대본 캐시 전부 확인: 대본 AI 설치·실행을 건너뜁니다.', flush=True)
        return provider
    print('기존 Ollama 실행 스크립트로 대본 모델을 준비합니다.', flush=True)
    try:
        subprocess.run(['bash', str(root / 'scripts/start-ollama-ci.sh')], cwd=root, env=env, check=True)
    except BaseException:
        log = _tail(runtime_dir / 'ollama.log')
        if log:
            print('Ollama 로그 마지막 부분:\n' + log, flush=True)
        raise
    if github_path.is_file():
        ollama_bin = github_path.read_text(encoding='utf-8').strip().splitlines()
        if ollama_bin:
            env['PATH'] = ollama_bin[-1] + os.pathsep + env.get('PATH', '')
    os.environ.update({key: env[key] for key in ('HF_HOME', 'OLLAMA_HOST') if key in env})
    os.environ['OLLAMA_HOST'] = '127.0.0.1:11434'
    if 'PATH' in env:
        os.environ['PATH'] = env['PATH']

    return None


def run(root, bundle_sha):
    root = Path(root).resolve()
    runtime_dir = Path('/tmp/knu-audio-runtime')
    if _bootstrap_runtime(root, bundle_sha, runtime_dir):
        return
    context_path = root / 'kaggle-run-context.json'
    context = json.loads(context_path.read_text(encoding='utf-8'))
    source_input = root / 'data/raw' / context['day'] / 'items.json'
    if _sha256(source_input) != context['input_sha256']:
        raise RuntimeError('Kaggle 번들의 수집 입력 해시가 다릅니다.')
    input_data = json.loads(source_input.read_text(encoding='utf-8'))
    if input_data.get('date') != context['day']:
        raise RuntimeError('Kaggle 번들의 수집 날짜가 선택 날짜와 다릅니다.')

    runtime_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['HF_HOME'] = '/tmp/knu-audio-cache/huggingface'
    env['OLLAMA_GPU'] = 'true'
    env['RUNNER_TEMP'] = str(runtime_dir)
    github_path = runtime_dir / 'github-path'
    env['GITHUB_PATH'] = str(github_path)
    print('필요한 TTS 패키지를 준비합니다.', flush=True)
    _ensure_system_tools()
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                    '-r', str(root / 'requirements.txt'), '-r', str(root / 'requirements-tts.txt')],
                   cwd=root, env=env, check=True)
    gpu = _gpu_info()
    print(f"확인된 Kaggle GPU: {gpu['gpu_name']} · CUDA {gpu['cuda_version']}", flush=True)
    from collector.store import load_collection_report
    from briefing.build import AudioBatchComplete, ProgressRecorder, build
    from briefing import checkpoint
    from briefing.daily import verify_publication
    from briefing.app_export import export
    items = load_collection_report(source_input)
    if items['date'] != context['day']:
        raise RuntimeError('Kaggle 번들의 수집 날짜가 선택 날짜와 다릅니다.')

    recorder = ProgressRecorder(root / 'output/briefing-progress.json')
    run_dir = Path('/kaggle/working/briefing-artifacts')
    if run_dir.exists():
        shutil.rmtree(run_dir)
    cache = Path('/tmp/knu-audio-cache/briefing')
    failures = {}
    if context.get('resume_kernel'):
        matches = [p.parent for p in Path('/kaggle/input').rglob('state.json')
                   if p.parent.name == 'checkpoint'
                   and json.loads(p.read_text()).get('kernel_id') == context['resume_kernel']]
        if len(matches) != 1:
            raise RuntimeError('이어갈 Kaggle 결과의 checkpoint를 찾지 못했습니다.')
        failures = checkpoint.restore(matches[0], cache, context['checkpoint_signature'])
        print(f'저장된 음성·대본 복원: {context["resume_kernel"]}', flush=True)
    os.environ['HF_HOME'] = env['HF_HOME']
    try:
        print('음성 모델(Base)은 실행 중 Hugging Face에서 받습니다.', flush=True)
        slm_client = prepare_slm(root, items, cache, runtime_dir, env, github_path)
        build(source_input, output=root / 'dist', cache=cache,
              allow_archive=True, progress=recorder,
              audio_batch_seconds=AUDIO_BATCH_SECONDS if context.get('batch') else None, failed_audio=failures,
              slm_client=slm_client)
        verify_publication(root / 'dist', context['day'])
        export(root / 'dist', root / 'output/app/data/briefing', items_path=source_input)
        if context.get('batch'):
            checkpoint.save(cache, run_dir / 'checkpoint', context, failures, 'complete')
        _package_outputs(root, context, bundle_sha, gpu, run_dir, runtime_dir)
        print('Kaggle 브리핑 산출물과 실행 식별자 저장 완료.', flush=True)
    except AudioBatchComplete:
        checkpoint.save(cache, run_dir / 'checkpoint', context, failures, 'pending')
        diagnostics = run_dir / 'diagnostics'
        for name in ('briefing-progress.json', 'briefing-report.json', 'review.json'):
            _copy_file(root / 'output' / name, diagnostics / name)
        print(f'음성 생성 {AUDIO_BATCH_SECONDS // 60}분 묶음 저장 완료. 다음 묶음에서 이어갑니다.', flush=True)
    except BaseException:
        diagnostics = run_dir / 'diagnostics'
        diagnostics.mkdir(parents=True, exist_ok=True)
        _copy_file(root / 'output/briefing-progress.json', diagnostics / 'briefing-progress.json')
        _copy_file(root / 'output/briefing-report.json', diagnostics / 'briefing-report.json')
        _copy_file(root / 'output/review.json', diagnostics / 'review.json')
        _copy_file(runtime_dir / 'ollama.log', diagnostics / 'ollama.log')
        try:
            (diagnostics / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        except OSError:
            pass
        log = _tail(runtime_dir / 'ollama.log')
        if log:
            print('Ollama 로그 마지막 부분:\n' + log, flush=True)
        raise
