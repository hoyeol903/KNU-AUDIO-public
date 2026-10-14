"""수집부터 홈페이지 배포까지 끝난 결과만 한 번 알린다."""
import base64
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
import time
from urllib.request import urlopen, Request
from zoneinfo import ZoneInfo

SITE = 'https://hoyeol903.github.io/KNU-AUDIO-public/'
WORKFLOWS = {
    'collect.yml': '수집', 'briefing-kaggle.yml': '생성',
    'briefing-kaggle-recover.yml': '복구', 'deploy.yml': '배포',
}


def command(*args):
    return subprocess.check_output(['gh', *args], text=True, timeout=120).strip()


def api(path, **fields):
    args = ['api', f'repos/{os.environ["GH_REPO"]}/{path}']
    for key, value in fields.items():
        args += ['-f', f'{key}={value}']
    for attempt in range(3):
        try:
            return json.loads(command(*args))
        except (OSError, subprocess.SubprocessError):
            if fields or attempt == 2:
                raise
            time.sleep(5)


def run_info(run_id):
    return api(f'actions/runs/{run_id}')


def value(title, key):
    match = re.search(r'(?:^| \| )' + key + r'=(\d+|예|아니오|없음)(?: \||$)', title)
    return match[1] if match else None


def dispatch(workflow, **inputs):
    args = ['workflow', 'run', workflow, '--ref', os.environ['DEFAULT_BRANCH']]
    for key, val in inputs.items():
        args += ['-f', f'{key}={val}']
    command(*args)


def day_of(run):
    return datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Seoul')).date()


def sentence(day, reason=None):
    label = f'{day.month}/{day.day} ({"월화수목금토일"[day.weekday()]})'
    return (f'{label} 오늘 브리핑 업로드에 실패했습니다. {reason}' if reason
            else f'{label} 오늘 브리핑이 정상적으로 업로드되었습니다.')


def notify(day, reason=None):
    marker = f'<!-- briefing-final:{day.isoformat()} -->'
    issues = api('issues?state=open&per_page=100')
    issue = next((row for row in issues if row['title'] == '오늘 브리핑 결과' and 'pull_request' not in row), None)
    body = marker + '\n@' + os.environ['GH_OWNER'] + '\n\n' + sentence(day, reason)
    if not issue:
        api('issues', title='오늘 브리핑 결과', body=body)
        return
    if marker in issue.get('body', ''):
        return
    page = 1
    while True:
        comments = api(f'issues/{issue["number"]}/comments?per_page=100&page={page}')
        if any(marker in row['body'] for row in comments):
            return
        if len(comments) < 100:
            break
        page += 1
    api(f'issues/{issue["number"]}/comments', body=body)


def retry_or_notify(run, root_id, retried, reason, sleep=time.sleep):
    if retried:
        notify(day_of(run_info(root_id)), reason)
        return
    sleep(30 * 60)
    # 음성은 새로 생성하지 않는다. 실패한 게시·배포만 기존 결과로 한 번 복구한다.
    try:
        if Path(run['path']).name == 'deploy.yml':
            dispatch('deploy.yml', briefing_run_id=str(root_id), final_retry='true')
        else:
            dispatch('briefing-kaggle-recover.yml', run_id=str(root_id))
    except (OSError, subprocess.SubprocessError):
        notify(day_of(run_info(root_id)), '30분 뒤 재시도 작업을 시작하지 못했습니다.')


def verify_site(day):
    with urlopen(SITE + 'data/briefing/segments.json?final=' + day.isoformat(), timeout=30) as response:
        data = json.load(response)
    if data.get('date') != day.isoformat() or not data.get('segments'):
        raise ValueError('오늘 음성이 사이트에 반영되지 않았습니다.')
    files = {row.get('audio', '') for row in data['segments']}
    if any(not re.fullmatch(r'[a-f0-9]{64}\.mp3', name) for name in files):
        raise ValueError('사이트 음성 파일 정보가 없습니다.')
    def check(name):
        with urlopen(Request(SITE + 'data/briefing/' + name, method='HEAD'), timeout=20) as response:
            if response.status != 200:
                raise ValueError('사이트 음성 파일을 열지 못했습니다.')
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(check, files))


def main(event, sleep=time.sleep):
    event_run = event['workflow_run']
    run = run_info(event_run['id'])
    branch = os.environ['DEFAULT_BRANCH']
    kind = Path(run['path']).name
    if run['head_branch'] != branch or kind not in WORKFLOWS or run['status'] != 'completed':
        return
    title = run.get('display_title', '')
    if kind == 'collect.yml':
        runs = api('actions/workflows/briefing-kaggle.yml/runs?per_page=100')['workflow_runs']
        if any(value(row.get('display_title', ''), '수집') == str(run['id']) for row in runs):
            return  # 생성 작업이 최종 배포까지 이어받는다.
        notify(day_of(run), '자료 수집 또는 음성 작업 시작을 완료하지 못했습니다.')
        return
    if kind == 'briefing-kaggle.yml':
        if value(title, '게시') == '아니오':
            return
        if run['conclusion'] == 'cancelled':
            notify(day_of(run), '작업이 취소되어 업로드하지 못했습니다.')
            return
        if run['conclusion'] == 'success':
            return  # 홈페이지 배포 완료 때 알린다.
        retry_or_notify(run, run['id'], False, '대본·음성 생성 또는 게시를 완료하지 못했습니다.', sleep)
        return
    root_id = value(title, '원본')
    if not root_id or root_id == '없음':
        return  # 일반 화면 수정 배포는 일일 브리핑 메일을 보내지 않는다.
    root = run_info(root_id)
    if root['path'] != '.github/workflows/briefing-kaggle.yml' or root['head_branch'] != branch:
        raise ValueError('일일 브리핑의 원래 실행이 아닙니다.')
    if run['conclusion'] == 'cancelled':
        notify(day_of(root), '작업이 취소되어 업로드하지 못했습니다.')
        return
    if kind == 'briefing-kaggle-recover.yml':
        if run['conclusion'] != 'success':
            notify(day_of(root), '기존 생성 결과를 가져와 게시하는 재시도에도 실패했습니다.')
        return
    retried = value(title, '재시도') == '예'
    if run['conclusion'] != 'success':
        retry_or_notify(run, root_id, retried, '30분 뒤 다시 시도했지만 사이트 배포에 실패했습니다.', sleep)
        return
    try:
        verify_site(day_of(root))
    except (OSError, ValueError):
        retry_or_notify(run, root_id, retried, '재시도 후에도 오늘 음성의 사이트 반영을 확인하지 못했습니다.', sleep)
        return
    collection_id = value(root.get('display_title', ''), '수집')
    reason = None
    record_file = api(f'contents/data/runs/briefing-kaggle-{day_of(root)}.json?ref={branch}')
    record = json.loads(base64.b64decode(record_file['content']))
    if str(record.get('run_id')) != str(root_id):
        return  # 같은 날 더 최신 실행이 이미 게시됐다면 옛 실행으로 알리지 않는다.
    if record.get('audio_failures', 0) or record.get('skipped_notices', 0):
        reason = '사이트는 배포됐지만 일부 대본 또는 음성 생성에 실패했습니다.'
    if collection_id and collection_id != '없음' and run_info(collection_id)['conclusion'] != 'success':
        reason = '사이트는 배포됐지만 일부 자료 수집에 실패했습니다.'
    notify(day_of(root), reason)


if __name__ == '__main__':
    main(json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text()))
