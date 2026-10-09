"""GitHub 대기가 끝나도 Kaggle의 완료 결과를 검증해 게시 작업에 넘긴다."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from briefing import kaggle
from briefing.kaggle_batch import cli


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True, timeout=180).stdout


def recover(run_id, *, manual=False, root=Path('.cache/kaggle')):
    if not run_id.isdigit():
        raise ValueError('GitHub 실행 ID는 숫자여야 합니다.')
    repo = os.environ['GH_REPO']
    run = json.loads(gh('api', f'repos/{repo}/actions/runs/{run_id}'))
    default = json.loads(gh('api', f'repos/{repo}'))['default_branch']
    if run['head_branch'] != default or run['path'] != '.github/workflows/briefing-kaggle.yml':
        raise ValueError('기본 브랜치의 Kaggle 음성 실행만 게시할 수 있습니다.')
    root = Path(root)
    original = root / 'original'
    name = f"kaggle-briefing-*-{run_id}-{run['run_attempt']}"
    gh('run', 'download', run_id, '--repo', repo, '--pattern', name, '--dir', str(original))
    candidates = list(original.rglob('expected.json'))
    if len(candidates) != 1:
        raise ValueError('원래 실행의 검증 정보를 하나로 특정할 수 없습니다.')
    source = candidates[0]
    requested = source.parent / 'publish-requested.txt'
    if not manual and (not requested.is_file() or requested.read_text().strip() != 'true'):
        print('자동 게시를 요청하지 않은 실행입니다.')
        return False
    expected = json.loads(source.read_text())
    if expected['run_id'] != run_id or expected['github_sha'] != run['head_sha']:
        # source_sha 입력으로 다른 커밋을 고정한 실행은 별도로 확인한다.
        commit = json.loads(gh('api', f"repos/{repo}/commits/{expected['github_sha']}"))
        if expected['run_id'] != run_id or commit['sha'] != expected['github_sha']:
            raise ValueError('원래 실행 정보가 일치하지 않습니다.')
    kernel = expected['kernel_id']
    if not kernel.startswith(os.environ.get('KAGGLE_USERNAME', 'muyahoyeol') + '/knu-audio-briefing-' + run_id + '-'):
        raise ValueError('원래 실행의 Kaggle 커널이 아닙니다.')
    version = str(expected.get('kernel_version', 1))
    kaggle.wait_for_kernel(kernel, version=version, interval=60)
    output = root / 'output'
    if output.exists():
        shutil.rmtree(output)
    cli(['kernels', 'output', kernel + '/' + version, '--path', str(output),
         '--file-pattern', '^briefing-artifacts/', '--force'])
    state = json.loads((output / 'briefing-artifacts/checkpoint/state.json').read_text())
    if state['status'] != 'complete':
        raise ValueError('아직 전체 생성이 끝나지 않았습니다. 저장된 묶음부터 이어가야 합니다.')
    expected['kernel_version'] = int(version)
    expected_path = root / 'expected.json'
    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n')
    kaggle.verify_output(output / 'briefing-artifacts', expected_path)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--manual', choices=['true', 'false'], default='false')
    args = parser.parse_args()
    ready = recover(args.run_id, manual=args.manual == 'true')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write(f'ready={str(ready).lower()}\n')
