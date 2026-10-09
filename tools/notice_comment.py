"""오늘 공지·수집 실패를 GitHub 이슈 댓글과 CSV로 출력한다. 네트워크 요청은 하지 않는다."""
import argparse
import csv
from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile

import yaml

from collector.store import SEOUL, load_collection_report

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / 'output/app/data/new-notices.csv'
FAILURES_PATH = ROOT / 'output/app/data/collection-failures.csv'
SITE_URL = 'https://knu-audio.pages.dev/data/new-notices.csv'
FAILURES_URL = 'https://knu-audio.pages.dev/data/collection-failures.csv'
MAX_ROWS = 100
FAILURE_FIELDS = ['게시판', '실패 URL', '간단한 원인', '원문 오류', '상태', '재시도 안내']
RETRY_ADVICE = '일시 오류면 다음 자동 수집을 기다리거나 Actions에서 실패 게시판 재수집을 실행하세요.'


def _cell(value):
    return (str(value or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('|', r'\|').replace('[', r'\[').replace(']', r'\]').replace('\n', ' '))


def _cause(message):
    lowered = message.casefold()
    if any(word in lowered for word in ('timeout', 'timed out', '시간 초과', '응답 지연')):
        return '요청 시간 초과'
    if any(word in lowered for word in ('connectionerror', 'connection refused', 'name resolution', '연결 실패')):
        return '사이트 연결 실패'
    if any(word in lowered for word in ('httperror', 'status code', 'http 4', 'http 5', '응답 코드')):
        return '사이트 응답 오류'
    if any(word in lowered for word in ('parseerror', '구조 변경', '파싱', '찾을 수 없습니다')):
        return '페이지 형식 확인 필요'
    return '수집 오류'


def _started(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result if result.utcoffset() is not None else None


def load_current_report(path, started_at):
    """Load only the exact report for this collection invocation."""
    if not path or not Path(path).is_file():
        return None
    try:
        report = load_collection_report(path)
        report_started = _started(report.get('started_at'))
        expected = _started(started_at)
    except (OSError, ValueError, TypeError):
        return None
    if report_started is None or expected is None or report_started < expected:
        return None
    if not isinstance(report.get('channels'), list):
        return None
    return report


def failure_rows(report, channels, started_at):
    if not report:
        return []
    names = {row['id']: row.get('name', row['id']) for row in channels if isinstance(row, dict) and row.get('id')}
    expected = _started(started_at)
    expected_board_start = expected.replace(microsecond=0) if expected else None
    by_key = {}

    def add(source, channel_ids, url, message, status):
        ids = channel_ids or ([source] if source else [])
        label = ' / '.join(dict.fromkeys(names.get(cid, cid) for cid in ids)) or '수집 자료'
        key = (source, url or '', message)
        row = by_key.get(key)
        if row is None:
            row = dict(board=label, url=url or '', cause=_cause(message), original=message,
                       status=status, retry=RETRY_ADVICE)
            by_key[key] = row
        elif label != row['board'] and label not in row['board']:
            row['board'] += ' / ' + label
        return row

    for board in report['channels']:
        if not isinstance(board, dict):
            continue
        source = board.get('source_board_id') or board.get('channel_id')
        ids = board.get('channel_ids') or ([board.get('channel_id')] if board.get('channel_id') else [])
        board_started = _started(board.get('started_at'))
        current = bool(expected_board_start and board_started and board_started >= expected_board_start)
        status = '이번 실행 실패' if current else '이전 실패 · 재수집 대기'
        errors = board.get('errors') or []
        for error in errors:
            if not isinstance(error, dict):
                continue
            message = str(error.get('message') or '수집 오류')
            url = error.get('url') or next((channel.get('source_url') for channel in channels
                                            if channel.get('id') in ids and channel.get('source_url')), '')
            add(source, ids, url, message, status)
        if board.get('truncated'):
            message = '페이지 제한으로 수집 범위를 다 확인하지 못했습니다'
            url = next((channel.get('source_url') for channel in channels
                        if channel.get('id') in ids and channel.get('source_url')), '')
            add(source, ids, url, message, status)
        elif board.get('window_complete') is False and not errors:
            message = '수집 범위를 끝까지 확인하지 못했습니다'
            url = next((channel.get('source_url') for channel in channels
                        if channel.get('id') in ids and channel.get('source_url')), '')
            add(source, ids, url, message, status)
    for error in report.get('extras', {}).get('errors', []) if isinstance(report.get('extras'), dict) else []:
        if not isinstance(error, dict):
            continue
        source = error.get('source', '기타 자료')
        channel_ids = [source] if source in names else []
        fallback = {'weather': '날씨', 'schedule': '학사일정'}.get(source)
        if fallback:
            names[source] = fallback
            channel_ids = [source]
        add(source, channel_ids, error.get('url', ''), str(error.get('message') or '수집 오류'), '이번 실행 실패')
    return list(by_key.values())


def write_failures(rows, path=FAILURES_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=FAILURE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({'게시판': row['board'], '실패 URL': row['url'], '간단한 원인': row['cause'],
                             '원문 오류': row['original'], '상태': row['status'], '재시도 안내': row['retry']})
    os.replace(temporary, path)


def comment(rows, repo, sha, owner, *, failures=(), collection_outcome='success',
            export_outcome='success', save_outcome='success', report_available=True, run_url=''):
    day = rows[0]['기준일'] if rows else datetime.now(SEOUL).date().isoformat()
    new = sum(row['구분'] == '신규' for row in rows)
    lines = []
    if not report_available:
        if collection_outcome == 'success':
            lines += [f'@{owner} {day} 이번 실행의 상세 수집 보고서가 없습니다.',
                      '실행은 오류 없이 끝났지만 결과를 확인할 수 없습니다.']
        else:
            lines += [f'@{owner} {day} 수집 단계가 실패했고 상세 보고서도 없습니다.']
    elif collection_outcome != 'success':
        lines.append(f'@{owner} {day} 수집 중 오류가 발생했습니다. 성공한 자료는 저장 단계에서 보존합니다.')
    else:
        lines.append(f'@{owner} {day} 수집 완료: 신규 {new}건, 마감 알림 {len(rows) - new}건')
    if run_url:
        lines += ['', f'[Actions 실행 로그]({run_url})']
    if save_outcome != 'success':
        lines += ['', '수집 결과 저장에 실패했습니다. 다운로드 링크에는 최신 CSV가 반영되지 않았을 수 있습니다.']
    elif export_outcome != 'success':
        lines += ['', '정적 앱 자료 생성에 실패해 공지 목록이나 최신 CSV 링크를 표시하지 않습니다.']
    elif report_available:
        lines += ['', f'[공지 CSV]({SITE_URL}) · [수집 실패 CSV]({FAILURES_URL})',
                  f'[이번 실행의 실패 CSV](https://github.com/{repo}/blob/{sha}/output/app/data/collection-failures.csv)']
        if rows:
            lines += ['', '| 게시판 | 구분 | 제목 | 게시일 | 마감일 |', '|---|---|---|---|---|']
            lines += [f"| {_cell(row['게시판'])} | {_cell(row['구분'])} | [{_cell(row['제목'])}]({row['링크']}) | {_cell(row['게시일'])} | {_cell(row['마감일'])} |"
                      for row in rows[:MAX_ROWS]]
            if len(rows) > MAX_ROWS:
                lines += ['', f'표에는 {MAX_ROWS}건만 실었습니다. 전체 {len(rows)}건은 CSV에서 확인하세요.']
    if failures:
        lines += ['', f'수집 실패·미완료 항목 {len(failures)}건', '',
                  '| 게시판 | 실패 URL | 원인 | 상태 |', '|---|---|---|---|']
        lines += [f"| {_cell(row['board'])} | {_cell(row['url'])} | {_cell(row['cause'])} | {_cell(row['status'])} |"
                  for row in failures[:MAX_ROWS]]
        if len(failures) > MAX_ROWS:
            lines += ['', f'표에는 {MAX_ROWS}건만 실었습니다. 전체 {len(failures)}건은 실패 CSV에서 확인하세요.']
        lines += ['', '재시도 안내: 일시 오류라면 다음 자동 수집을 기다리거나 Actions에서 실패 게시판 재수집을 실행하세요.']
    elif report_available:
        lines += ['', '수집 실패나 미완료 게시판이 없습니다.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', nargs='?')
    parser.add_argument('sha', nargs='?')
    parser.add_argument('owner', nargs='?')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--started-at')
    parser.add_argument('--write-failures', type=Path)
    parser.add_argument('--collect-outcome', default='success')
    parser.add_argument('--export-outcome', default='success')
    parser.add_argument('--save-outcome', default='success')
    parser.add_argument('--run-url', default='')
    args = parser.parse_args()
    report = load_current_report(args.report, args.started_at) if args.report else None
    with (ROOT / 'data/channels.yaml').open(encoding='utf-8') as stream:
        channels = yaml.safe_load(stream)
    failures = failure_rows(report, channels, args.started_at)
    if args.write_failures:
        write_failures(failures, args.write_failures)
        return
    rows = []
    if report and args.export_outcome == 'success':
        try:
            with CSV_PATH.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
        except OSError:
            pass
    print(comment(rows, args.repo or '', args.sha or '', args.owner or 'owner', failures=failures,
                  collection_outcome=args.collect_outcome, export_outcome=args.export_outcome,
                  save_outcome=args.save_outcome, report_available=bool(report), run_url=args.run_url), end='')


if __name__ == '__main__':
    main()
