"""시간 묶음마다 정상 종료한 Kaggle 결과를 다음 실행에 연결한다."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from briefing import kaggle


def cli(args, *, required=True):
    result = subprocess.run(['kaggle', *args], capture_output=True, text=True, check=False, timeout=180)
    if required and result.returncode:
        raise RuntimeError('Kaggle 요청 실패: ' + (result.stdout + result.stderr)[-2000:])
    return result


def previous_checkpoint(context, folder):
    """같은 GitHub 실행의 이전 attempt에서 정상 종료한 마지막 묶음을 찾는다."""
    resume = None
    for attempt in range(int(context['run_attempt']) - 1, 0, -1):
        batch = 1
        while True:
            kernel = f"{context['username']}/{kaggle.KERNEL_PREFIX}-{context['run_id']}-{attempt}-b{batch}"
            status = cli(['kernels', 'status', kernel], required=False)
            if status.returncode:
                message = status.stdout + status.stderr
                if '404' in message or 'not found' in message.lower():
                    break
                raise RuntimeError('이전 묶음 조회 실패: ' + message[-2000:])
            if kaggle.parse_kernel_status(status.stdout + status.stderr) != 'complete':
                break
            target = Path(folder) / f'{attempt}-{batch}'
            cli(['kernels', 'output', kernel + '/1', '--path', str(target), '--file-pattern',
                 '^briefing-artifacts/checkpoint/state.json$', '--force'])
            state_path = target / 'briefing-artifacts/checkpoint/state.json'
            if not state_path.is_file():
                break
            state = json.loads(state_path.read_text())
            if state['signature'] != context['checkpoint_signature']:
                break
            resume = kernel
            batch += 1
        if resume:
            return resume
    return None


def run_batches(root, expected_path, kernel_dir, output, logs, *, resume_kernel=None):
    root, expected_path, output = Path(root), Path(expected_path), Path(output)
    context = json.loads(expected_path.read_text())
    if resume_kernel is None:
        resume_kernel = previous_checkpoint(context, output.parent / 'previous-checkpoints')
    if resume_kernel and not resume_kernel.startswith(context['username'] + '/' + kaggle.KERNEL_PREFIX + '-'):
        raise ValueError('이 계정의 KNU-AUDIO checkpoint만 이어갈 수 있습니다.')
    batch = 1
    while True:
        expected = kaggle.prepare_kernel(root, context['day'], context['run_id'], context['run_attempt'],
                                        context['github_sha'], context['username'], kernel_dir, expected_path,
                                        batch=batch, resume_kernel=resume_kernel)
        kernel = expected['kernel_id']
        pushed = cli(['kernels', 'push', '--path', str(kernel_dir), '--accelerator', 'NvidiaTeslaT4'])
        version = kaggle.parse_kernel_version(pushed.stdout + pushed.stderr)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
                stream.write(f'kernel_id={kernel}\nkernel_version={version}\n')
        try:
            kaggle.wait_for_kernel(kernel, version=version, interval=60)
        except BaseException:
            diagnostic = cli(['kernels', 'output', kernel + '/' + version, '--path', str(output),
                              '--file-pattern', '^briefing-artifacts/diagnostics/', '--force'], required=False)
            Path(logs).write_text(diagnostic.stdout + diagnostic.stderr)
            raise
        cli(['kernels', 'output', kernel + '/' + version, '--path', str(output),
             '--file-pattern', '^briefing-artifacts/', '--force'])
        state = json.loads((output / 'briefing-artifacts/checkpoint/state.json').read_text())
        if state['signature'] != expected['checkpoint_signature'] or state['kernel_id'] != kernel:
            raise ValueError('묶음 저장 결과의 실행 정보가 일치하지 않습니다.')
        Path(output.parent / 'resume.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))
        print(f'묶음 {batch} 저장 완료: {len(state["files"])}개 캐시 파일', flush=True)
        if state['status'] == 'complete':
            expected['kernel_version'] = int(version)
            expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2))
            return
        if state['status'] != 'pending':
            raise ValueError('알 수 없는 checkpoint 상태')
        resume_kernel = kernel
        batch += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--kernel-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--logs', type=Path, required=True)
    parser.add_argument('--resume-kernel')
    args = parser.parse_args()
    run_batches(kaggle.ROOT, args.expected, args.kernel_dir, args.output, args.logs,
                resume_kernel=args.resume_kernel or None)
