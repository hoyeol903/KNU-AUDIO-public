"""저장된 자료를 GitHub Pages용 정적 앱으로 내보낸다. 네트워크 요청은 하지 않는다."""
import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
import re
import shutil

from collector import preview
from collector.preview import ROOT, catalog, snapshot
from collector.store import DEFAULT_PATH, SEOUL, load_collection_report, load_notices, save_json


# 단과대학별 캐릭터 사진(tools/avatars/<번호>.webp). 사진이 없는 학부는 화면에서 비워 둔다.
COLLEGE_AVATARS = {name: f'avatars/{number:02}.webp' for number, name in enumerate([
    '농업생명과학대학', '공과대학', '사범대학', 'IT대학', '과학기술대학', '인문대학', '자연과학대학', '생태환경대학',
    '사회과학대학', '첨단기술융합대학', 'AI대학', '생활과학대학', '예술대학', '경상대학', '수의과대학', '의과대학',
    '치과대학', '간호대학', '약학대학', '자율전공학부', '자율미래인재학부', '행정학부',
    '공과대학/농업생명과학대학',  # 공학 첨단자율학부
], 1)}


def _meal_groups(meals):
    # 끼니·가격·대표 이름 줄 수는 주간 표에서 읽은 자료에만 있다.
    return [dict(label=meal.get('label'), hours=meal['time'], menu=meal['menu'], price=meal.get('price'),
                 head=meal.get('head', 0)) for meal in meals]


def _first_hours(groups):
    return next((group['hours'] for group in groups if group['hours']), None)


def required_notice_boards(channels):
    """Returns the configured full required physical boards, deduplicated by source URL."""
    required = [c for c in channels if c.get('type') == 'notice'
                and c.get('classification') == 'required' and c.get('collection_enabled')]
    if not required:
        return []
    from collector.run import VALIDATION_PATH, all_required_channels, board_id_for
    validation = load_collection_report(VALIDATION_PATH) if VALIDATION_PATH.exists() else None
    return [dict(source_board_id=board_id_for(board), channel_ids=board['channel_ids'])
            for board in all_required_channels(channels, validation)]


def collection_status(channels, expected_boards, reports, context, now):
    """Summarizes physical required-board status for today without trusting stale reports."""
    today = now.date().isoformat()
    names = {channel['id']: channel.get('name', channel['id']) for channel in channels}
    expected = {board['source_board_id']: board for board in expected_boards}
    latest = {row['source_board_id']: row for row in reports
              if isinstance(row, dict) and row.get('source_board_id') in expected}

    def timestamp(value):
        if not isinstance(value, str):
            return None
        try:
            result = datetime.fromisoformat(value)
        except ValueError:
            return None
        if result.tzinfo is None:
            return None
        result = result.astimezone(SEOUL)
        return result if result <= now else None

    last_checked = []
    success = failed = not_collected = 0
    failures = []
    for board_id, board in expected.items():
        report = latest.get(board_id)
        if not report:
            not_collected += 1
            continue
        started = timestamp(report.get('started_at'))
        finished = timestamp(report.get('finished_at')) or started
        if finished:
            last_checked.append(finished)
        if not started or started.date().isoformat() != today:
            not_collected += 1
            continue
        errors = report.get('errors') or []
        reasons = [error.get('message', '수집 오류') for error in errors if isinstance(error, dict)]
        if report.get('truncated'):
            reasons.append('페이지 제한으로 전체 범위를 확인하지 못했습니다')
        if errors or report.get('truncated'):
            failed += 1
            channel_ids = report.get('channel_ids') or board['channel_ids']
            failures.append(dict(source_board_id=board_id,
                                 name=' / '.join(names.get(channel_id, channel_id) for channel_id in channel_ids),
                                 reasons=reasons))
        elif report.get('window_complete') is True:
            success += 1
        else:
            not_collected += 1

    from collector.daily_sources import MEAL_SOURCES
    meal_ids = [channel['id'] for channel in channels if channel.get('type') == 'meal'
                and channel.get('collection_enabled') and channel['id'] in MEAL_SOURCES]
    current_context = context if isinstance(context, dict) and context.get('date') == today else None
    context_time = timestamp(current_context.get('collected_at')) if current_context else None
    source_rows = current_context.get('sources', []) if context_time else []
    source_checks = {}
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        checked = timestamp(row.get('checked_at'))
        if checked and checked.date().isoformat() == today:
            last_checked.append(checked)
        if row.get('source') in meal_ids and checked and checked.date().isoformat() == today:
            source_checks[row['source']] = checked
    meal_errors = {row.get('source') for row in current_context.get('errors', [])
                   if isinstance(row, dict)} if context_time else set()
    meal_failed = sum(channel_id in meal_errors for channel_id in meal_ids)
    meal_success = sum(channel_id in source_checks and channel_id not in meal_errors for channel_id in meal_ids)
    meal_missing = len(meal_ids) - meal_failed - meal_success
    last_checked_at = max(last_checked).isoformat(timespec='seconds') if last_checked else None
    return dict(date=today, lastCollectedAt=last_checked_at, physicalBoards=len(expected),
                todaySuccess=success, todayFailed=failed, todayNotCollected=not_collected,
                failedBoards=failures,
                meals=dict(total=len(meal_ids), todaySuccess=meal_success, todayFailed=meal_failed,
                           todayNotCollected=meal_missing))
def saved_meal_week(day, today_context, raw_dir):
    """식당별 (수집일, 주간 식단). 식단은 로컬에서 가끔만 수집하므로 오늘이 들어 있는 가장 최근 주간 표를 쓴다."""
    found = {channel_id: (day.isoformat(), week)
             for channel_id, week in (today_context or {}).get('meal_week', {}).items()}
    for offset in range(1, 7):
        source = (day - timedelta(days=offset)).isoformat()
        path = Path(raw_dir) / source / 'context.json'
        if not path.exists():
            continue
        for channel_id, week in load_collection_report(path).get('meal_week', {}).items():
            if channel_id not in found and any(row['date'] == day.isoformat() for row in week):
                found[channel_id] = (source, week)
    return found


def app_data(channels, departments, data, by_notice, stored_ids, meal_week):
    """새 화면용 자료: meta(홈 한 장)와 채널별 최근 글. D-day는 화면에서 계산하므로 넣지 않는다."""
    items, checks = data['items'], data['checks']
    errors = items['errors']
    failed = {error['source'] for error in errors}
    boards_of = {}
    for row in checks:
        boards_of.setdefault(row['id'].split(':', 1)[0], set()).update(row['channel_ids'])
    # 게시판 ID로 적힌 오류는 그 게시판을 쓰는 채널마다 붙여 화면이 내 것만 거를 수 있게 한다.
    issues = [dict(source=source, text=error['message'])
              for error in errors for source in sorted(boards_of.get(error['source'], [error['source']]))]

    weather = items['weather']
    ok = weather['summary'] is not None
    schedule = [dict(title=row['title'], start=row['start'], end=row['end']) for row in items['schedule']]
    meals = {channel['channel_id']: channel['meals'] for channel in items['channels']}
    cafes = []
    for channel in channels:
        if channel['type'] != 'meal' or not channel.get('collection_enabled'):
            continue
        menu_from, week = meal_week.get(channel['id'], (None, []))
        saved = next((day for day in week if day['date'] == items['date']), None)
        groups = _meal_groups(saved['meals'] if saved and saved['meals'] else meals.get(channel['id'], []))
        messages = [error['message'] for error in errors if error['source'] == channel['id']]
        if groups:
            status = 'ok'
        elif channel['id'] in meals:
            # ponytail: 미게시는 오류 문구로 구분한다. 문구가 바뀌면 수집기가 상태 코드를 직접 남기게 한다.
            status = 'failed' if any('미게시' not in message for message in messages) else 'empty'
        else:
            # 오늘 식단을 수집하지 않았으면 앞서 받은 주간 표의 오늘 칸을 따른다.
            status = saved['status'] if saved else 'failed'
        cafes.append(dict(id=channel['id'], name=channel['name'], url=channel.get('source_url'), status=status, menuFrom=menu_from,
                          hours=_first_hours(groups), groups=groups, days=[
                              dict(date=day['date'], status=day['status'], hours=_first_hours(_meal_groups(day['meals'])),
                                   groups=_meal_groups(day['meals'])) for day in week]))

    required = [c for c in channels if c['type'] == 'notice' and c.get('classification') == 'required']
    by_channel = {channel['id']: [] for channel in required}
    for row in checks:
        for channel_id in row['channel_ids']:
            if channel_id in by_channel:
                by_channel[channel_id].append(row)
    boards, posts = [], {}
    for channel in required:
        rows = sorted(by_channel[channel['id']], key=lambda row: row['posted_at'] or '', reverse=True)
        today = [row for row in rows if row['status'] == 'selected']
        # 마감 알림은 오래된 글에서도 나오므로 최근 30개 밖의 오늘 글도 함께 싣는다.
        shown = rows[:30] + [row for row in today if row not in rows[:30]]
        boards.append(dict(
            id=channel['id'], name=channel['name'], url=channel.get('source_url'), saved=len(rows),
            collected=channel['id'] in stored_ids,
            today=[dict(postId=row['id'], kind='new' if row['reason'] == 'new' else 'deadline', title=row['title'],
                        date=row['posted_at'], deadline=row['deadline']) for row in today]))
        if shown:
            posts[channel['id']] = [dict(
                id=row['id'], title=row['title'], date=row['posted_at'], deadline=row['deadline'], url=row['url'],
                body=by_notice[row['id']]['body'] if row['body_status'] == 'text' else None,
                bodyStatus='ok' if row['body_status'] == 'text' else 'unreadable') for row in shown]
    meta = dict(
        asOf=items['date'], checkedAt=items['collected_at'][11:16],
        weather=dict(status='ok' if ok else 'failed', summary=weather['summary'], min=weather['temp_min'],
                     max=weather['temp_max'], rain=weather['rain_prob']),
        schedule=dict(status='failed' if 'schedule' in failed else 'ok' if schedule else 'empty', items=schedule),
        cafes=cafes,
        departments=[dict(id=d['id'], dept=d['name'], college=d['college'], avatar=COLLEGE_AVATARS.get(d['college']), requiredBoards=[
            c['id'] for c in required if c.get('required') == 'all' or d['id'] in c.get('required_department_ids', [])])
            for d in departments],
        boards=boards, issues=issues)
    return meta, posts


def year_schedule(raw_dir):
    """앱 달력용 학사일정 전체. 가장 최근에 받은 해 전체 목록을 쓰고, 받은 날짜를 함께 싣는다."""
    for path in sorted(Path(raw_dir).glob('*/context.json'), reverse=True):
        rows = load_collection_report(path).get('schedule_year') or []
        if rows:
            return {'status': 'ok', 'from': path.parent.name, 'items': [
                dict(title=row['title'], start=row['start'], end=row['end']) for row in rows]}
    return {'status': 'empty', 'from': None, 'items': []}


def new_notice_rows(meta, posts):
    """오늘 선정된 공지(신규·마감 알림)를 엑셀에서 여는 표로 만든다."""
    rows = [['기준일', '게시판', '구분', '제목', '게시일', '마감일', '링크']]
    for board in meta['boards']:
        urls = {post['id']: post['url'] for post in posts.get(board['id'], [])}
        for row in board['today']:
            rows.append([meta['asOf'], board['name'], '신규' if row['kind'] == 'new' else '마감 알림', row['title'],
                         row['date'] or '', row['deadline'] or '', urls[row['postId']]])
    return rows


def export(output=ROOT / 'output/app', *, db_path=DEFAULT_PATH, raw_dir=ROOT / 'data/raw'):
    channels, departments = catalog()
    now = datetime.now(SEOUL)
    data = snapshot([channel['id'] for channel in channels], now=now, db_path=db_path)
    data['items']['channels'] = [
        {**channel, 'notices': []}
        for channel in data['items']['channels']
    ]
    stored = load_notices(db_path)
    by_notice = {row['id']: row for row in stored}
    checks = data['checks']
    include = {row['id'] for row in checks if row['status'] == 'selected'}
    for channel in channels:
        if channel['type'] == 'notice':
            rows = [row for row in checks if channel['id'] in row['channel_ids']]
            rows.sort(key=lambda row: row['posted_at'] or '', reverse=True)
            include.update(row['id'] for row in rows[:30])

    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    details = root / 'details'
    details.mkdir(exist_ok=True)
    index_path = root / '.export-details.json'
    old_boards = load_collection_report(index_path).get('boards', []) if index_path.exists() else []
    grouped = {}
    for notice_id in include:
        row = by_notice[notice_id]
        board = row['source_board_id']
        grouped.setdefault(board, {})[notice_id] = {
            key: row[key] for key in ('title', 'body', 'url', 'posted_at', 'deadline')
        }
    for board, rows in grouped.items():
        save_json(rows, details / f'{board}.json')
    channels_payload = dict(channels=channels, departments=departments,
                            stored_channel_ids=sorted({id for row in stored for id in row['channel_ids']}),
                            date=now.date().isoformat())
    # index.html은 새 화면, legacy.html은 data.json·details를 읽는 이전 시험 화면이다.
    for name, source in (('index.html', 'tools/knua-app.html'), ('briefing-onepass.js', 'tools/briefing-onepass.js'), ('legacy.html', 'tools/app-test.html'), ('privacy.html', 'tools/privacy.html')):
        temporary = root / (name + '.tmp')
        temporary.write_text((ROOT / source).read_text(encoding='utf-8'), encoding='utf-8')
        temporary.replace(root / name)
    save_json(dict(catalog=channels_payload, snapshot=data), root / 'data.json')
    context = preview.load_context()
    meta, posts = app_data(channels, departments, data, by_notice, set(channels_payload['stored_channel_ids']),
                           saved_meal_week(now.date(), context, raw_dir))
    latest = preview.latest_reports()
    report_rows = latest[0].get('channels', []) if latest else []
    meta['collection'] = collection_status(channels, required_notice_boards(channels), report_rows, context, now)
    board_dir = root / 'data/boards'
    board_dir.mkdir(parents=True, exist_ok=True)
    for path in board_dir.glob('*.json'):
        if path.stem not in posts:
            path.unlink()
    for channel_id, rows in posts.items():
        save_json(rows, board_dir / f'{channel_id}.json')
    save_json(meta, root / 'data/meta.json')
    save_json(year_schedule(raw_dir), root / 'data/schedule.json')
    from tools.daily_bgm import export as export_daily_bgm
    export_daily_bgm(root / 'data/bgm')
    shutil.copytree(ROOT / 'tools/avatars', root / 'data/avatars', dirs_exist_ok=True)
    # UI 정적 자산: 데이터 계약을 바꾸지 않고 함께 배포한다.
    for asset_dir in ('hobanu', 'branding'):
        shutil.copytree(ROOT / 'tools' / asset_dir, root / 'data' / asset_dir, dirs_exist_ok=True)
    # utf-8-sig: 엑셀이 한글을 깨뜨리지 않고 연다.
    temporary = root / 'data/new-notices.csv.tmp'
    with temporary.open('w', encoding='utf-8-sig', newline='') as stream:
        csv.writer(stream).writerows(new_notice_rows(meta, posts))
    temporary.replace(root / 'data/new-notices.csv')
    for board in old_boards:
        if board not in grouped and isinstance(board, str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]*', board):
            (details / f'{board}.json').unlink(missing_ok=True)
    save_json(dict(boards=sorted(grouped)), index_path)
    count = sum(row['status'] == 'selected' for row in checks)
    print(f'정적 앱 내보냄: {root} · 채널 {len(channels)}개 · 확인 {len(checks)}개 · 선정 {count}개 · 상세 {len(include)}개')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/app')
    parser.add_argument('--db-path', type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    export(args.output, db_path=args.db_path)


if __name__ == '__main__':
    main()
