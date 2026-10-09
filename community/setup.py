"""Create a free D1 DB, apply idempotent schema, and bind the selected Pages environment.
Token comes from the environment/GitHub Secrets and is never printed.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import urllib.error
import urllib.request


def api(method, path, body=None):
    token = os.environ.get('CLOUDFLARE_API_TOKEN')
    if not token:
        raise RuntimeError('CLOUDFLARE_API_TOKEN Secret이 필요합니다.')
    request = urllib.request.Request('https://api.cloudflare.com/client/v4/' + path, method=method,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        # Only status/path are reported; neither token nor request/response headers are logged.
        raise RuntimeError(f'Cloudflare {error.code}: {method} {path}. 계정의 D1 편집·Pages 편집 권한을 확인하세요.') from None
    if not data.get('success'):
        raise RuntimeError('Cloudflare 요청 실패: ' + method + ' ' + path)
    return data['result']


def setup(environment):
    account = os.environ['CLOUDFLARE_ACCOUNT_ID']
    base = f'accounts/{account}'
    name = 'knua-community' + ('-preview' if environment == 'preview' else '')
    databases = api('GET', base + '/d1/database?per_page=100')
    database = next((d for d in databases if d['name'] == name), None)
    if database is None:
        database = api('POST', base + '/d1/database', {'name': name})
    uuid = database['uuid']
    schema = Path(__file__).resolve().parent.parent / 'migrations/0001_community.sql'
    statement = ''
    for line in schema.read_text().splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            results = api('POST', base + f'/d1/database/{uuid}/query', {'sql': statement})
            if any(not r.get('success', False) for r in results):
                raise RuntimeError('D1 스키마 적용에 실패했습니다. 배포를 중지합니다.')
            statement = ''
    project_path = base + '/pages/projects/knu-audio'
    project = api('GET', project_path)
    config = project.get('deployment_configs', {}).get(environment, {}) or {}
    bindings = dict(config.get('d1_databases') or {})
    bindings['COMMUNITY_DB'] = {'id': uuid}
    api('PATCH', project_path, {'deployment_configs': {environment: {'d1_databases': bindings}}})
    print(f'{environment}: {name} 스키마·COMMUNITY_DB 연결 완료. 요금제 변경 없음.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', choices=['preview', 'production'], required=True)
    args = parser.parse_args()
    try:
        setup(args.environment)
    except (RuntimeError, KeyError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
