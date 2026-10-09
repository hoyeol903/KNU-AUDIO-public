"""학교·전자공학부·검증된 KNU CMS 공지 수집과 저장."""
import argparse
import re
import time
from urllib.parse import urlsplit, parse_qs
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from collector import public_notices, other_notices
from collector.deadlines import extract_deadline
from collector.daily_items import discovery_reason, build_items
from collector.privacy import redact

from collector.http import Client, FetchError
from collector.knu_cms import ParseError, parse_detail, parse_list, next_page, to_notice, title_matches
from collector.store import (DEFAULT_PATH, SEOUL, load_notices, save_collection_report,
                             upsert_notices, load_collection_state, save_collection_state,
                             link_board_channels, load_collection_report, save_daily_items)

ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ID = 'notice-6c1f8a512fa4'
BOARD_ID = 'knu-korean-kor1657071357'
RECENT_DAYS = 30
DETAIL_RECHECK_DAYS = 7
OLD_RECHECK_DAYS = 7
DEFAULT_CMS_CHANNEL_IDS = [CHANNEL_ID, 'notice-1abc9573202c', 'notice-472ae4378387']
VALIDATION_PATH = ROOT / 'data/knu-cms-validation.json'
PUBLIC_SOURCES = {
    'knu-academic': ('knu-wbbs', 'https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/stdList.action?menu_idx=42', 'knu-wbbs-stu_812'),
    'notice-df44dd8507c1': ('gt-board', 'https://see.knu.ac.kr/content/board/notice.html', 'knu-see-notice'),
}
DEFAULT_CHANNEL_IDS = list(PUBLIC_SOURCES) + DEFAULT_CMS_CHANNEL_IDS
OTHER_SOURCES = {
    'notice-b1133d4c8b3b': ('gnuboard', 'http://biotech.knu.ac.kr/bbs/board.php?bo_table=sub6_1', 'knu-biotech-sub6_1'),
    'notice-b34ee1a00417': ('gnuboard', 'https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&lang=kor', 'knu-computer-sub6_1_a'),
    'notice-fefffa32e24c': ('gnuboard', 'https://computer.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&lang=kor', 'knu-computer-sub6_1_a'),
    'notice-6b04da14aae1': ('gnuboard', 'https://chinese.knu.ac.kr/bbs/board.php?bo_table=notice', 'knu-chinese-notice'),
    'notice-a363da417a07': ('med-cms', 'http://med.knu.ac.kr/pages/sub.htm?nav_code=knu1670583748', 'knu-med-notice001'),
    'notice-7414782e7dbb': ('custom-bid-board', 'https://dent.knu.ac.kr/sub/board.html?bid=k1news', 'knu-dent-k1news'),
}


def board_id_for(channel):
    for template, source_url, board_id in (PUBLIC_SOURCES | OTHER_SOURCES).values():
        if channel['source_url'] == source_url:
            return board_id
    url = urlsplit(channel['source_url'])
    match = re.fullmatch(r'/HOME/([A-Za-z0-9_-]+)/sub.htm', url.path)
    nav = parse_qs(url.query).get('nav_code', [])
    if not url.hostname or not url.hostname.endswith('.knu.ac.kr') or not match or len(nav) != 1 or not re.fullmatch(r'[A-Za-z0-9_-]+', nav[0]):
        raise ValueError('지원하지 않는 KNU CMS 게시판 주소')
    return ('knu-' + match[1] + '-' + nav[0]).lower()


def select_channels(channels, requested=None, required_all=False, validation=None):
    """같은 게시판은 한 번 요청하고 논리 채널 ID를 함께 저장한다."""
    verified = set(DEFAULT_CMS_CHANNEL_IDS)
    by_id = {c['id']: c for c in channels}
    for channel_id, (template, url, board) in (PUBLIC_SOURCES | OTHER_SOURCES).items():
        c = by_id.get(channel_id)
        if c and c['source_url'] == url and c['template'] == template:
            verified.add(channel_id)
    for row in (validation or {}).get('channels', []):
        verified.discard(row['channel_id'])
        channel = by_id.get(row['channel_id'])
        if channel and row['status'] in {'verified', 'empty'} and row['source_url'] == channel['source_url']:
            if row['source_board_id'] == board_id_for(channel):
                verified.add(channel['id'])
    ids = requested or ([c['id'] for c in channels if c['classification'] == 'required' and c['template'] == 'knu-cms' and c['id'] in verified]
                        if required_all else DEFAULT_CHANNEL_IDS)
    grouped = {}
    for channel_id in dict.fromkeys(ids):
        channel = by_id.get(channel_id)
        if not channel or channel_id not in verified or not channel.get('collection_enabled') or channel.get('template') not in {'knu-cms', 'knu-wbbs', 'gt-board', 'gnuboard', 'med-cms', 'custom-bid-board'}:
            raise ValueError(f'목록·상세 검증을 통과한 지원 채널이 아닙니다: {channel_id}')
        board = board_id_for(channel)
        if board not in grouped:
            grouped[board] = dict(channel, channel_ids=[])
        grouped[board]['channel_ids'].append(channel_id)
    return list(grouped.values())


def select_failed_channels(channels, report, validation=None):
    rows = report.get('channels') if isinstance(report, dict) else None
    if not isinstance(rows, list):
        raise ValueError('재수집 보고서에 channels 목록이 없습니다')
    by_id = {c['id']: c for c in channels}
    ids = []
    for row in rows:
        if not isinstance(row, dict) or not (row.get('errors') or row.get('truncated')):
            continue
        board = row.get('source_board_id')
        reported_ids = row.get('channel_ids') or ([row['channel_id']] if row.get('channel_id') else [])
        if (not isinstance(board, str) or not isinstance(reported_ids, list) or not reported_ids
                or any(not isinstance(channel_id, str) for channel_id in reported_ids)):
            raise ValueError('실패 게시판 보고서에 source_board_id 또는 channel ID가 없습니다')
        for channel_id in reported_ids:
            channel = by_id.get(channel_id)
            if channel is None or board_id_for(channel) != board:
                raise ValueError(f'재수집 보고서와 현재 채널 설정이 일치하지 않습니다: {channel_id}')
            ids.append(channel_id)
    return select_channels(channels, list(dict.fromkeys(ids)), validation=validation) if ids else []


def merge_board_reports(existing, updates):
    merged = {row['source_board_id']: row for row in existing}
    for row in updates:
        merged[row['source_board_id']] = row
    return list(merged.values())


def retry_report_path(value):
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    runs = (ROOT / 'data/runs').resolve()
    if path.parent != runs or path.suffix.lower() != '.json' or not path.is_file():
        raise ValueError('재수집 보고서는 저장소의 data/runs/*.json 파일이어야 합니다')
    return path


def all_required_channels(channels, validation):
    cms = select_channels(channels, required_all=True, validation=validation)
    ids = [channel_id for channel in cms for channel_id in channel['channel_ids']] + list(PUBLIC_SOURCES) + list(OTHER_SOURCES)
    return select_channels(channels, ids, validation=validation)


def needs_detail(item, previous, now):
    if previous is None or item['posted_at'] is None:
        return True
    if item['posted_at'] != previous['posted_at'] or not title_matches(item['title'], previous['title']):
        return True
    if date.fromisoformat(item['posted_at']) >= now.date() - timedelta(days=DETAIL_RECHECK_DAYS):
        return True
    if previous['deadline'] and date.fromisoformat(previous['deadline']) >= now.date():
        return True
    if previous['body_status'] == 'needs-review':
        return True
    return now - datetime.fromisoformat(previous['last_checked_at']) >= timedelta(days=OLD_RECHECK_DAYS)


def collect(client, channel, *, db_path=DEFAULT_PATH, max_pages=1000, now=None, progress=None, mode='daily'):
    started = time.monotonic()
    requests_before = getattr(client, 'request_count', 0)
    board_id = board_id_for(channel)
    list_parser, detail_parser, page_parser = parse_list, parse_detail, next_page
    if board_id == 'knu-wbbs-stu_812':
        list_parser, detail_parser, page_parser = public_notices.parse_school_list, public_notices.parse_school_detail, public_notices.school_next_page
    elif board_id == 'knu-see-notice':
        list_parser, detail_parser, page_parser = public_notices.parse_see_list, public_notices.parse_see_detail, public_notices.see_next_page
    elif channel.get('template') == 'gnuboard':
        list_parser, detail_parser, page_parser = other_notices.parse_gnu_list, other_notices.parse_gnu_detail, other_notices.gnu_next_page
    elif board_id == 'knu-med-notice001':
        list_parser, detail_parser, page_parser = other_notices.parse_med_list, other_notices.parse_med_detail, other_notices.med_next_page
    elif board_id == 'knu-dent-k1news':
        list_parser, detail_parser, page_parser = other_notices.parse_dent_list, other_notices.parse_dent_detail, other_notices.dent_next_page
    fixed_now = now is not None
    now = now or datetime.now(SEOUL)
    if now.utcoffset() != timedelta(hours=9):
        raise ValueError('판정 시각은 Asia/Seoul +09:00이어야 합니다')
    if mode not in {'daily', 'full', 'init', 'start'}:
        raise ValueError('mode는 daily/full/init/start 중 하나여야 합니다')
    state = load_collection_state(db_path)
    markers = state['boards'].get(board_id, dict(initialized_at=None, last_full_scan_at=None))
    baseline = markers['initialized_at']
    if mode == 'start' and baseline is not None:
        raise ValueError('이미 운영을 시작한 게시판입니다. daily 또는 full을 사용하세요')
    bootstrap = baseline is None or mode in {'init', 'start'}
    full = mode != 'start' and (bootstrap or mode in {'full', 'init'})
    cutoff = now.date() - timedelta(days=RECENT_DAYS)
    existing = load_notices(db_path)
    channel_ids = channel.get('channel_ids', [channel['id']])
    linked = link_board_channels(board_id, channel_ids, db_path)
    if linked:
        existing = load_notices(db_path)
    by_id = {row['source_post_id']: row for row in existing if row['source_board_id'] == board_id}
    report = dict(channel_id=channel['id'], channel_ids=channel_ids, linked=linked, source_board_id=board_id,
                  started_at=datetime.now(SEOUL).isoformat(timespec='seconds'),
                  initial_import=not any(r['source_board_id'] == board_id for r in existing),
                  mode='start' if mode == 'start' else 'init' if bootstrap else 'full' if full else 'daily', bootstrap=bootstrap,
                  new_candidates=[], late_discoveries=[], window_complete=False,
                  scope='first-page', listed=0, successful=0,
                  new=[], updated=[], unchanged=[], skipped=[], needs_review=[], deadline_checks=[], errors=[])
    if max_pages < 1:
        raise ValueError('max_pages는 1 이상이어야 합니다')
    report.update(scope='page-traversal', pages=0, max_pages=max_pages, truncated=False)
    items_by_id = {}
    visited = set()
    old_pages = 0
    url = channel['source_url']
    while url:
        if url in visited:
            report['errors'].append(dict(source=channel['id'], url=url, message='페이지 순환 감지'))
            break
        visited.add(url)
        try:
            html, actual_url = client.get(url)
            page_items = list_parser(html, actual_url)
            for item in page_items:
                previous = items_by_id.get(item['source_post_id'])
                if previous and (previous['posted_at'] != item['posted_at'] or not
                                 (title_matches(previous['title'], item['title']) or title_matches(item['title'], previous['title']))):
                    raise ParseError('페이지 사이 같은 글의 내용이 달라 재확인 필요')
                if previous:
                    previous['pinned'] = previous.get('pinned', False) or item.get('pinned', False)
                else:
                    items_by_id[item['source_post_id']] = item
            report['pages'] += 1
            if progress:
                progress(f"목록 {report['pages']}페이지 / 고유 글 {len(items_by_id)}개")
            following = page_parser(html, actual_url) if page_items else None
            regular = [item for item in page_items if not item.get('pinned')]
            old_page = bool(regular) and all(item['posted_at'] is not None and
                        date.fromisoformat(item['posted_at']) < cutoff for item in regular)
            old_pages = old_pages + 1 if old_page else 0
        except (FetchError, ParseError) as exc:
            report['errors'].append(dict(source=channel['id'], url=url, message=str(exc)))
            break
        # ponytail: 2페이지 경계의 비정상 정렬 누락은 필요할 때 수동 full로 확인.
        if not following or (not full and old_pages >= 2):
            report['window_complete'] = True
            break
        if following and report['pages'] >= max_pages:
            report['truncated'] = True
            break
        url = following
    items = list(items_by_id.values())
    report['listed'] = len(items)
    direct_ids = set()
    if not full:
        for post_id, row in by_id.items():
            urgent = row['deadline'] and date.fromisoformat(row['deadline']) >= now.date()
            if post_id not in items_by_id and (urgent or row['posted_at'] is None or row['body_status'] == 'needs-review'):
                items.append(dict(source_post_id=post_id, title=row['title'], posted_at=row['posted_at'],
                                  url=row['url'], pinned=False))
                direct_ids.add(post_id)
    report['direct_checks'] = len(direct_ids)
    notices = []
    def flush():
        if notices:
            result = upsert_notices(notices, path=db_path, checked_at=now.isoformat() if fixed_now else None)
            for key in ('new', 'updated', 'unchanged'):
                report[key].extend(result[key])
            report['successful'] += len(notices)
            notices.clear()

    for index, item in enumerate(items, 1):
        previous = by_id.get(item['source_post_id'])
        notice_id = board_id + ':' + item['source_post_id']
        if item['posted_at'] is None:
            report['needs_review'].append(notice_id)
        if not needs_detail(item, previous, now):
            report['skipped'].append(notice_id)
            continue
        try:
            html, url = client.get(item['url'])
            detail = detail_parser(html, url, posted_at=item['posted_at']) if channel.get('template') == 'gnuboard' else detail_parser(html, url)
            if item['source_post_id'] in direct_ids:
                # 저장된 제목·게시일은 목록 검증 근거가 아니다. 원래 글 ID는 계속 검증한다.
                item = dict(item, title=detail['title'], posted_at=detail['posted_at'])
            notice = redact(to_notice(item, detail, board_id=board_id, channel_ids=channel_ids))
            deadline = extract_deadline(notice['title'], notice['body'])
            if deadline['status'] != 'not-found':
                report['deadline_checks'].append(dict(notice_id=notice_id, **deadline))
            if deadline['status'] == 'found':
                notice['deadline'] = deadline['deadline']
            elif deadline['status'] == 'needs-review' and notice_id not in report['needs_review']:
                report['needs_review'].append(notice_id)
            if previous and previous['deadline'] and notice['deadline'] is None:
                if all(previous[k] == notice[k] for k in ('title', 'posted_at', 'body', 'body_status')):
                    notice['deadline'] = previous['deadline']
                elif notice_id not in report['needs_review']:
                    report['needs_review'].append(notice_id)
            notices.append(notice)
            if len(notices) >= 25:
                flush()
        except (FetchError, ParseError) as exc:
            report['errors'].append(dict(source=channel['id'], url=item['url'], message=str(exc)))
        if progress and index % 25 == 0:
            progress(f"상세 판정 {index}/{len(items)} / 저장 {report['successful']} / 생략 {len(report['skipped'])} / 오류 {len(report['errors'])}")
    flush()
    if report['window_complete'] and not report['errors'] and not report['truncated']:
        stamp = (now if fixed_now else datetime.now(SEOUL)).isoformat()
        state = load_collection_state(db_path)
        state['boards'][board_id] = dict(initialized_at=stamp if bootstrap else baseline,
                                        last_full_scan_at=stamp if full else markers['last_full_scan_at'])
        save_collection_state(state, db_path)
    if not bootstrap:
        for row in load_notices(db_path):
            reason = discovery_reason(row, baseline, now.date())
            if row['source_board_id'] == board_id and reason:
                key = 'new_candidates' if reason == 'new' else 'late_discoveries'
                report[key].append(row['id'])
    report['request_count'] = getattr(client, 'request_count', 0) - requests_before
    report['duration_sec'] = round(time.monotonic() - started, 3)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--channel-id', action='append', help='검증된 채널 ID; 반복 지정 가능. 기본 학교·전자공학부·국문·영문·수학 5개')
    selection.add_argument('--required-knu-cms', action='store_true', help='검증된 필수 KNU CMS 채널 전체 선택')
    selection.add_argument('--all-required', action='store_true', help='필수 채널 전체 (KNU CMS + 학교·전자공학부 + 그 밖의 필수 게시판)')
    selection.add_argument('--retry-failed', action='store_true', help='오늘 실패 또는 잘린 게시판만 재수집')
    parser.add_argument('--retry-report', type=Path, help='재시도 대상을 고를 data/runs/*.json 보고서')
    parser.add_argument('--max-pages', type=int, default=1000)
    parser.add_argument('--mode', choices=['daily', 'full', 'init', 'start'], default='daily', help='일일 / 전체 점검 / 과거 전체 적재 / 최근 구간으로 첫 운영')
    parser.add_argument('--db-path', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--report-path', type=Path)
    parser.add_argument('--write-items', action='store_true', help='수집 후 채널별 오늘 신규·마감 알림 items.json 저장')
    parser.add_argument('--collect-extras', action='store_true', help='날씨·식당·학사일정도 실제 수집 (--write-items 필요)')
    parser.add_argument('--skip-meals', action='store_true', help='--collect-extras에서 식당은 요청하지 않음 (로컬 수동 수집용)')
    parser.add_argument('--items-path', type=Path, help='--write-items의 저장 경로 변경')
    args = parser.parse_args()
    if args.items_path and not args.write_items:
        parser.error('--items-path는 --write-items와 함께 사용합니다')
    if args.collect_extras and not args.write_items:
        parser.error('--collect-extras는 --write-items와 함께 사용합니다')
    if args.skip_meals and not args.collect_extras:
        parser.error('--skip-meals는 --collect-extras와 함께 사용합니다')
    if args.retry_failed and not args.write_items:
        parser.error('--retry-failed는 --write-items와 함께 사용합니다')
    if args.retry_failed and args.collect_extras:
        parser.error('--retry-failed는 --collect-extras와 함께 사용할 수 없습니다')
    if args.retry_report and not args.retry_failed:
        parser.error('--retry-report는 --retry-failed와 함께 사용합니다')
    with (ROOT / 'data/channels.yaml').open(encoding='utf-8') as stream:
        channels = yaml.safe_load(stream)
    validation = load_collection_report(VALIDATION_PATH) if VALIDATION_PATH.exists() else None
    retrying = args.retry_failed
    item_channels = None
    current_report_rows = None
    if retrying:
        from collector.preview import latest_reports
        today = datetime.now(SEOUL).date()
        try:
            if args.retry_report:
                source_report_path = retry_report_path(args.retry_report)
                report_source = load_collection_report(source_report_path)
            else:
                source_report_path = None
                day_reports = latest_reports(today)
                report_source = day_reports[0] if day_reports else {'channels': []}
            report_arg = ((ROOT / args.report_path) if args.report_path and not args.report_path.is_absolute()
                          else args.report_path)
            if report_arg and source_report_path and report_arg.resolve() == source_report_path:
                raise ValueError('새 보고서 경로는 재수집 원본과 달라야 합니다')
            selected = select_failed_channels(channels, report_source, validation)
            if selected:
                item_channels = all_required_channels(channels, validation)
                latest = latest_reports(today)
                current_report_rows = latest[0]['channels'] if latest else []
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        if not selected:
            print('오늘 재수집할 실패·미완료 게시판이 없습니다. HTTP 요청 없이 종료합니다.')
            return 0
    else:
        try:
            selected = all_required_channels(channels, validation) if args.all_required else \
                select_channels(channels, args.channel_id, args.required_knu_cms, validation)
        except ValueError as exc:
            parser.error(str(exc))
    print(f"선택: 논리 채널 {sum(len(c['channel_ids']) for c in selected)}개 / 고유 게시판 {len(selected)}개", flush=True)
    reports = []
    extras_fresh = None
    context = None
    if retrying:
        context_path = ROOT / 'data/raw' / datetime.now(SEOUL).date().isoformat() / 'context.json'
        if context_path.exists():
            context = load_collection_report(context_path)
    started_at = datetime.now(SEOUL).isoformat()
    started = time.monotonic()
    report_path = args.report_path or ROOT / 'data/runs' / (datetime.now(SEOUL).strftime('%Y%m%dT%H%M%S%f') + '-channels.json')
    if retrying and source_report_path and Path(report_path).resolve() == source_report_path:
        parser.error('새 보고서 경로는 재수집 원본과 달라야 합니다')
    report_rows = list(current_report_rows or [])
    with Client() as client:
        for channel in selected:
            print(f"수집 시작: {channel['name']}", flush=True)
            board_started = time.monotonic()
            started_iso = datetime.now(SEOUL).isoformat(timespec='seconds')
            try:
                report = collect(client, channel, db_path=args.db_path, max_pages=args.max_pages, mode=args.mode,
                                 progress=lambda message: print(message, flush=True))
            except Exception as exc:
                # 게시판 하나가 실패해도 나머지 수집은 이어 간다. 실패는 보고서와 items.errors에 남긴다.
                report = dict(channel_id=channel['id'], channel_ids=channel['channel_ids'],
                              source_board_id=board_id_for(channel), mode=args.mode, started_at=started_iso, listed=0, successful=0,
                              window_complete=False, truncated=False, new=[], updated=[], unchanged=[], skipped=[],
                              errors=[dict(source=channel['id'], message=f'{type(exc).__name__}: {exc}', url=channel['source_url'])],
                              request_count=0,
                              duration_sec=round(time.monotonic() - board_started, 3))
            report['finished_at'] = datetime.now(SEOUL).isoformat(timespec='seconds')
            reports.append(report)
            report_rows_to_save = merge_board_reports(report_rows, reports) if retrying else reports
            save_collection_report(dict(channels=report_rows_to_save,
                                        request_count=sum(r['request_count'] for r in reports)), report_path)
            print(f"{channel['name']}: 모드 {report.get('mode', args.mode)} / 목록 {report['listed']} / 상세 성공 {report['successful']} / 첫 저장 {len(report['new'])} / 당일 신규 후보 {len(report.get('new_candidates', []))} / 수정 {len(report['updated'])} / 생략 {len(report['skipped'])} / 실패 {len(report['errors'])} / HTTP 요청 {report['request_count']} / {report['duration_sec']}초", flush=True)
        if args.collect_extras:
            from collector.daily_sources import collect as collect_extras, save_context
            extras_fresh = collect_extras(client, datetime.now(SEOUL).date(), include_meals=not args.skip_meals)
            context = save_context(extras_fresh, ROOT / 'data/raw' / extras_fresh['date'] / 'context.json',
                                   include_meals=not args.skip_meals)
    print(f'실행 보고서: {report_path}')
    if args.write_items:
        by_id = {c['id']: c for c in channels}
        for_item_generation = item_channels if item_channels is not None else selected
        logical = [dict(by_id[id], source_board_id=board_id_for(c)) for c in for_item_generation for id in c['channel_ids']]
        report_rows_for_items = merge_board_reports(report_rows, reports) if retrying else reports
        items = build_items(load_notices(args.db_path), load_collection_state(args.db_path), logical,
                            reports=[dict(channels=report_rows_for_items)],
                            context=context if args.collect_extras or retrying else None)
        path = args.items_path or ROOT / 'data/raw' / items['date'] / 'items.json'
        save_daily_items(items, path)
        print(f"일일 입력 파일: {path} / 공지 {sum(len(c['notices']) for c in items['channels'])}개")
    request_count = sum(r['request_count'] for r in reports) + (extras_fresh['request_count'] if extras_fresh else 0)
    duration = round(time.monotonic() - started, 3)
    summary = dict(channels=merge_board_reports(report_rows, reports) if retrying else reports,
                   request_count=request_count, started_at=started_at,
                   finished_at=datetime.now(SEOUL).isoformat(), duration_sec=duration)
    if args.collect_extras:
        summary['extras'] = dict(request_count=extras_fresh['request_count'], errors=extras_fresh['errors'], sources=extras_fresh['sources'])
    save_collection_report(summary, report_path)
    print(f'전체: HTTP {request_count}회 / {duration}초')
    print('new는 DB 첫 저장입니다. 당일 신규 후보는 new_candidates이며 bootstrap 실행은 후보를 만들지 않습니다.')
    return 1 if any(r['errors'] or r['truncated'] for r in reports) or (extras_fresh and extras_fresh['errors']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
