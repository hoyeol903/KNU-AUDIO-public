"""Collect the required channel set once, preserving per-board progress."""
from datetime import datetime
import argparse
from copy import deepcopy
from pathlib import Path
import time

import yaml

from collector.http import Client
from collector.run import (OTHER_SOURCES, PUBLIC_SOURCES, ROOT, VALIDATION_PATH,
                           board_id_for, collect, select_channels)
from collector.store import (DEFAULT_PATH, SEOUL, load_collection_report,
                             load_collection_state, load_notices,
                             save_collection_report)


def read_resume_report(path, boards):
    try:
        report = load_collection_report(path)
    except (OSError, ValueError) as exc:
        raise ValueError(f'재개 보고서를 읽을 수 없습니다: {exc}') from exc
    if not isinstance(report, dict) or not isinstance(report.get('channels'), list):
        raise ValueError('재개 보고서 형식 오류: channels 배열이 필요합니다')
    current = {board_id_for(board): board['channel_ids'] for board in boards}
    seen, completed = set(), {}
    for index, channel in enumerate(report['channels']):
        if not isinstance(channel, dict):
            raise ValueError(f'재개 보고서 형식 오류: channels[{index}]가 객체가 아닙니다')
        board_id = channel.get('source_board_id')
        ids = channel.get('channel_ids')
        if not isinstance(board_id, str) or board_id not in current:
            raise ValueError(f'재개 보고서 형식 오류: 알 수 없는 source_board_id ({board_id!r})')
        if board_id in seen:
            raise ValueError(f'재개 보고서 형식 오류: 중복 source_board_id ({board_id})')
        seen.add(board_id)
        if not isinstance(ids, list) or ids != current[board_id]:
            raise ValueError(f'재개 보고서 형식 오류: {board_id}의 channel_ids가 현재 설정과 다릅니다')
        if not isinstance(channel.get('window_complete'), bool) or not isinstance(channel.get('truncated'), bool):
            raise ValueError(f'재개 보고서 형식 오류: {board_id}의 window_complete/truncated는 bool이어야 합니다')
        if not isinstance(channel.get('errors'), list):
            raise ValueError(f'재개 보고서 형식 오류: {board_id}의 errors는 배열이어야 합니다')
        if channel['window_complete'] and not channel['errors'] and not channel['truncated']:
            copied = deepcopy(channel)
            copied['resumed'] = True
            completed[board_id] = copied
    return completed


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-report', type=Path)
    args = parser.parse_args(argv)
    channels_path = ROOT / 'data/channels.yaml'
    with channels_path.open(encoding='utf-8') as stream:
        channels = yaml.safe_load(stream)
    validation = load_collection_report(VALIDATION_PATH)
    cms = select_channels(channels, required_all=True, validation=validation)
    ids = [channel_id for channel in cms for channel_id in channel['channel_ids']]
    ids += list(PUBLIC_SOURCES) + list(OTHER_SOURCES)
    selected = select_channels(channels, requested=ids, validation=validation)
    assert sum(len(board['channel_ids']) for board in selected) == 139
    assert len(selected) == 136

    carried = read_resume_report(args.resume_report, selected) if args.resume_report else {}

    stamp = datetime.now(SEOUL).strftime('%Y%m%dT%H%M%S%f%z')
    report_path = ROOT / 'data/runs' / f'required-recent-{stamp}.json'
    if args.resume_report and report_path.resolve() == args.resume_report.resolve():
        report_path = report_path.with_name(report_path.stem + '-resumed.json')
    state_before = load_collection_state(DEFAULT_PATH)
    before_db_count = len(load_notices(DEFAULT_PATH))
    initialized_before = sorted(board for board, marker in state_before['boards'].items()
                                if marker['initialized_at'])
    started_at = datetime.now(SEOUL).isoformat(timespec='seconds')
    started = time.monotonic()
    run_report = dict(started_at=started_at, finished_at=None, duration_sec=None,
                      request_count=0, metrics_scope='current-run',
                      resume_report=str(args.resume_report.resolve()) if args.resume_report else None,
                      resumed_boards=len(carried), db_count_before=before_db_count,
                      db_count_after=None, initialized_before=initialized_before,
                      initialized_after=None, expected_channels=139,
                      expected_boards=136, completed_boards=len(carried),
                      channels=list(carried.values()))
    save_collection_report(run_report, report_path)

    with Client() as client:
        if carried:
            print(f"재개 보고서에서 정상 완료한 게시판 {len(carried)}개를 건너뜁니다.", flush=True)
        for index, board in enumerate(selected, 1):
            board_id = board['source_board_id'] if 'source_board_id' in board else None
            board_id = board_id_for(board)
            if board_id in carried:
                continue
            prior = load_collection_state(DEFAULT_PATH)['boards'].get(board_id, {})
            mode = 'daily' if prior.get('initialized_at') else 'start'
            board_started = datetime.now(SEOUL).isoformat(timespec='seconds')
            req_before = client.request_count
            print(f"[{index}/136] 시작 {board['name']} ({mode})", flush=True)
            try:
                result = collect(client, board, db_path=DEFAULT_PATH, max_pages=1000,
                                 mode=mode, progress=lambda message: print(message, flush=True))
            except Exception as exc:
                result = dict(channel_id=board['id'], channel_ids=board['channel_ids'],
                              source_board_id=board_id, mode=mode, listed=0, successful=0,
                              window_complete=False, truncated=False, new=[], updated=[],
                              unchanged=[], skipped=[], errors=[dict(source=board['id'],
                              message=f'{type(exc).__name__}: {exc}', url=board['source_url'])],
                              request_count=client.request_count - req_before,
                              duration_sec=round(time.monotonic() - started, 3))
            result['initialized_at_before'] = prior.get('initialized_at')
            result['initialized_at_after'] = load_collection_state(DEFAULT_PATH)['boards'].get(board_id, {}).get('initialized_at')
            result['started_at'] = board_started
            result['finished_at'] = datetime.now(SEOUL).isoformat(timespec='seconds')
            result['success'] = bool(result.get('window_complete') and not result.get('errors')
                                     and not result.get('truncated'))
            result['normal_empty'] = bool(result['success'] and result.get('listed') == 0)
            run_report['channels'].append(result)
            run_report['completed_boards'] = len(run_report['channels'])
            run_report['request_count'] = client.request_count
            run_report['db_count_after'] = len(load_notices(DEFAULT_PATH))
            current_state = load_collection_state(DEFAULT_PATH)
            run_report['initialized_after'] = sorted(key for key, marker in current_state['boards'].items()
                                                      if marker['initialized_at'])
            run_report['finished_at'] = result['finished_at']
            run_report['duration_sec'] = round(time.monotonic() - started, 3)
            save_collection_report(run_report, report_path)
            print(f"[{index}/136] 완료 {board['name']}: {result.get('listed', 0)} 목록, "
                  f"{result.get('successful', 0)} 상세, 신규 {len(result.get('new', []))}, "
                  f"오류 {len(result.get('errors', []))}, 완료판정 {result['success']}", flush=True)
    run_report['completed_boards'] = len(run_report['channels'])
    run_report['db_count_after'] = len(load_notices(DEFAULT_PATH))
    current_state = load_collection_state(DEFAULT_PATH)
    run_report['initialized_after'] = sorted(key for key, marker in current_state['boards'].items()
                                              if marker['initialized_at'])
    run_report['finished_at'] = datetime.now(SEOUL).isoformat(timespec='seconds')
    run_report['duration_sec'] = round(time.monotonic() - started, 3)
    save_collection_report(run_report, report_path)
    print(f"REPORT_PATH={report_path}", flush=True)


if __name__ == '__main__':
    main()
