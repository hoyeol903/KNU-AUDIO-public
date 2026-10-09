"""실행을 시작할 때 GPU 한도가 남은 Kaggle 계정을 하나 고른다. 실행 중에는 계정을 바꾸지 않는다."""
import argparse
import os
import re
import subprocess

from briefing.model_cache import DATASET_SLUG

GPU_REMAINING = re.compile(r'^GPU\s+[\d.]+h\s+([\d.]+)h', re.M)
KERNEL_PREFIX = 'knu-audio-briefing'


def accounts(env=None):
    """KAGGLE_USERNAME_1/KAGGLE_TOKEN_1(기본), _2(보조) 중 이름과 토큰이 모두 있는 계정."""
    env = os.environ if env is None else env
    rows = []
    for slot in ('1', '2'):
        username, token = env.get('KAGGLE_USERNAME_' + slot, '').strip().lower(), env.get('KAGGLE_TOKEN_' + slot, '').strip()
        if username and token:
            rows.append(dict(slot=slot, username=username, token=token))
    return rows


def _kaggle(account, *args):
    return subprocess.run(['kaggle', *args], capture_output=True, text=True, check=False, timeout=180,
                          env=dict(os.environ, KAGGLE_USERNAME=account['username'], KAGGLE_API_TOKEN=account['token']))


def remaining_gpu_hours(account, run=_kaggle):
    result = run(account, 'quota')
    match = GPU_REMAINING.search(result.stdout or '')
    return float(match[1]) if result.returncode == 0 and match else None


def can_read_model(account, owner, run=_kaggle):
    return run(account, 'datasets', 'files', owner + '/' + DATASET_SLUG).returncode == 0


def has_kernel(account, slug, run=_kaggle):
    return run(account, 'kernels', 'status', account['username'] + '/' + slug).returncode == 0


def choose(rows, minimum, *, owner=None, previous_slug=None, quota=remaining_gpu_hours, readable=can_read_model,
           exists=has_kernel, report=print):
    """기본 계정의 남은 GPU 시간이 minimum 이상이면 기본 계정, 아니면 더 많이 남은 보조 계정."""
    if not rows:
        raise ValueError('Kaggle 계정이 설정되지 않았습니다. KAGGLE_API_TOKEN Secret을 확인하세요.')
    if owner:
        # 이어가기는 저장된 묶음이 있는 계정에서만 할 수 있다.
        match = next((row for row in rows if row['username'] == owner.lower()), None)
        if not match:
            raise ValueError('이어갈 커널의 계정이 설정된 Kaggle 계정과 다릅니다.')
        report(f"계정 {match['slot']} 사용: 이어갈 커널의 계정")
        return match
    if previous_slug:
        match = next((row for row in rows if exists(row, previous_slug)), None)
        if match:
            report(f"계정 {match['slot']} 사용: 이전 시도의 묶음이 있는 계정")
            return match
    primary = rows[0]
    hours = {row['slot']: quota(row) for row in rows}
    for row in rows:
        left = hours[row['slot']]
        report(f"계정 {row['slot']} 남은 GPU: " + ('확인 실패' if left is None else f'{left:.2f}시간'))
    if len(rows) == 1 or (hours[primary['slot']] or 0) >= minimum:
        report(f"계정 {primary['slot']} 사용")
        return primary
    spare = [row for row in rows[1:] if (hours[row['slot']] or 0) > (hours[primary['slot']] or 0)
             and readable(row, primary['username'])]
    chosen = max(spare, key=lambda row: hours[row['slot']], default=primary)
    report(f"계정 {chosen['slot']} 사용" + ('' if chosen is primary else f': 기본 계정의 남은 GPU가 {minimum}시간보다 적음'))
    return chosen


def activate(owner):
    """이미 시작한 실행이 쓴 계정의 인증 정보를 현재 프로세스에 적용한다."""
    rows = accounts()
    if not rows:
        if owner != os.environ.get('KAGGLE_USERNAME', 'muyahoyeol').lower():
            raise ValueError('원래 실행의 Kaggle 커널이 아닙니다.')
        return
    match = next((row for row in rows if row['username'] == owner.lower()), None)
    if not match:
        raise ValueError('원래 실행의 Kaggle 커널이 아닙니다.')
    os.environ.update(KAGGLE_USERNAME=match['username'], KAGGLE_API_TOKEN=match['token'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minimum', type=float, default=3)
    parser.add_argument('--resume-kernel', default='')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--run-attempt', type=int, default=1)
    args = parser.parse_args()
    rows = accounts()
    previous = (f'{KERNEL_PREFIX}-{args.run_id}-{args.run_attempt - 1}-b1'
                if args.run_id and args.run_attempt > 1 else None)
    chosen = choose(rows, args.minimum, owner=args.resume_kernel.split('/')[0] or None, previous_slug=previous)
    # 음성 모델은 기본 계정의 비공개 데이터셋 하나를 함께 쓴다(보조 계정에 공유해 둔다).
    with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as stream:
        stream.write(f"KAGGLE_USERNAME={chosen['username']}\nKAGGLE_API_TOKEN={chosen['token']}\n"
                     f"KAGGLE_MODEL_OWNER={rows[0]['username']}\n")


if __name__ == '__main__':
    main()
