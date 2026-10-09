"""로컬 학식 갱신 후 앱 미리보기 PR을 만든다."""
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from collector.store import SEOUL, load_collection_report

ROOT = Path(__file__).resolve().parents[1]


def main(root=ROOT, run=subprocess.run, now=None):
    root = Path(root)
    now = now or (lambda: datetime.now(SEOUL))

    def git(*args, check=True, **kwargs):
        return run(['git', *args], cwd=root, text=True, capture_output=True, check=check, **kwargs)

    def command(args, **kwargs):
        return run(args, cwd=root, text=True, capture_output=True, **kwargs)

    try:
        auth = command(['gh', 'auth', 'status'])
        if auth.returncode:
            raise RuntimeError('gh 로그인이 필요합니다.')
        remote = git('remote', 'get-url', 'origin').stdout.strip().removesuffix('.git')
        repositories = {prefix + name: 'hoyeol903/' + name
                        for name in ('KNU-AUDIO', 'KNU-AUDIO-public')
                        for prefix in ('https://github.com/hoyeol903/', 'git@github.com:hoyeol903/', 'ssh://git@github.com/hoyeol903/')}
        if remote not in repositories:
            raise RuntimeError(f'예상 저장소가 아닙니다: {remote}')
        repository = repositories[remote]
        if git('status', '--porcelain', '--untracked-files=all').stdout.strip():
            raise RuntimeError('작업 트리가 깨끗하지 않습니다. 변경을 정리한 뒤 다시 실행하세요.')
        head = git('symbolic-ref', 'refs/remotes/origin/HEAD').stdout.strip()
        default = head.removeprefix('refs/remotes/origin/')
        if not default:
            raise RuntimeError('origin 기본 브랜치를 확인할 수 없습니다.')
        git('fetch', 'origin', default)
        started = now()
        day = started.date().isoformat()
        branch = 'feat/local-meals-' + started.strftime('%Y%m%d-%H%M%S')
        git('switch', '-c', branch, f'origin/{default}')

        collection_started = now()
        print(f'{day} 학식을 수집합니다…', flush=True)
        collected = command([sys.executable, '-m', 'collector.daily_sources', '--meals-only'])
        if collected.returncode not in (0, 1):
            raise RuntimeError(f'수집 명령 실패({collected.returncode}): {collected.stderr}')
        if now().date().isoformat() != day:
            raise RuntimeError('실행 중 한국 날짜가 바뀌었습니다. 잘못된 날짜 자료를 게시하지 않았습니다.')
        context_path = root / 'data/raw' / day / 'context.json'
        if not context_path.exists():
            raise RuntimeError(f'수집 context가 없습니다: {context_path}')
        context = load_collection_report(context_path)
        collected_at = datetime.fromisoformat(context.get('collected_at', ''))
        if context.get('date') != day or collected_at.utcoffset() is None or collected_at < collection_started:
            raise RuntimeError(f'이번 실행에서 갱신된 오늘 context가 아닙니다: {context_path}')
        has_data = any(meal.get('menu') for channel in context.get('channels', []) for meal in channel.get('meals', []))
        has_data |= any(meal.get('menu') for week in context.get('meal_week', {}).values()
                        for item in week for meal in item.get('meals', []))
        errors = context.get('errors', [])
        if not has_data:
            raise RuntimeError(f'사용 가능한 식단 자료가 없어 게시를 중단했습니다. context: {context_path}; 오류: {errors}')
        print('정적 앱을 내보냅니다…', flush=True)
        exported = command([sys.executable, '-m', 'collector.export_app'])
        if exported.returncode:
            raise RuntimeError(f'앱 내보내기 실패: {exported.stderr}')
        git('add', '--', f'data/raw/{day}/context.json', 'output/app')
        diff_status = git('diff', '--cached', '--quiet', check=False).returncode
        if diff_status not in (0, 1):
            raise RuntimeError('stage 변경 사항을 확인하지 못했습니다.')
        if diff_status == 0:
            print('변경 사항이 없어 PR을 만들지 않았습니다.')
            return 0
        staged = git('diff', '--cached', '--name-only').stdout.splitlines()
        if any(path != f'data/raw/{day}/context.json' and not path.startswith('output/app/') for path in staged):
            raise RuntimeError(f'허용되지 않은 파일이 stage에 있습니다: {staged}')
        if not staged:
            raise RuntimeError('stage 파일 목록을 확인하지 못했습니다.')
        git('commit', '-m', f'학식 자료 갱신 ({day})')
        git('push', '-u', 'origin', branch)
        details = '\n'.join(f"- {row.get('source', 'source')}: {row.get('message', '수집 오류')}" for row in errors) or '- 수집 오류 없음'
        body = f'로컬 학식 자료를 갱신하고 정적 앱을 내보냈습니다.\n\n수집 오류(일부 자료가 비어 있을 수 있음):\n{details}\n'
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.md') as stream:
            stream.write(body)
            stream.flush()
            created = command(['gh', 'pr', 'create', '--repo', repository, '--base', default, '--head', branch,
                               '--title', f'학식 자료 갱신 ({day})', '--body-file', stream.name])
        if created.returncode:
            raise RuntimeError(f'PR 생성 실패. 브랜치 {branch}는 원격에 남아 있습니다: {created.stderr}')
        print(created.stdout.strip())
        return 0
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        detail = f': {exc.stderr.strip()}' if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ''
        print(f'중단: {exc}{detail}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
