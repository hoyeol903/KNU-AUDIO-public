"""검증된 공지 DB에서 오늘 신규·마감 알림을 골라 채널별 입력 파일 생성."""
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

import yaml

from collector.store import (DEFAULT_PATH, SEOUL, load_notices, load_collection_state,
                             load_collection_report, save_daily_items)


def discovery_reason(row, baseline, day):
    if baseline is None:
        return None
    first = datetime.fromisoformat(row['first_seen_at'])
    if first <= datetime.fromisoformat(baseline) or first.date() != day:
        return None
    posted = date.fromisoformat(row['posted_at']) if row['posted_at'] else None
    return 'new' if posted and day - timedelta(days=30) <= posted <= day else 'late'


def decide_notice(row, baseline, now, failed_urls=()):
    """전달 여부와 첫 탈락 이유. 수집기와 테스트 화면이 같은 판단을 쓴다."""
    day = now.date()
    result = dict(status='skipped', reason=None, dday=None)
    if row['posted_at'] and date.fromisoformat(row['posted_at']) > day:
        return dict(result, code='future', message='게시 날짜가 아직 미래입니다')
    dday = (date.fromisoformat(row['deadline']) - day).days if row['deadline'] else None
    result['dday'] = dday
    if dday is not None and dday < 0:
        return dict(result, code='expired', message='이미 마감한 공지입니다')
    discovered = discovery_reason(row, baseline, day)
    reason = 'new' if discovered == 'new' else 'reminder' if dday in {0, 1, 3} else None
    result['reason'] = reason
    if reason is None:
        return dict(result, code='no-trigger', message='오늘 신규 또는 마감 3일·1일·당일 조건에 해당하지 않습니다')
    checked = datetime.fromisoformat(row['last_checked_at'])
    if checked.date() != day or checked > now or unquote(row['url']) in failed_urls:
        return dict(result, code='stale', message='선정 후보의 오늘 상세 확인이 없어 제외했습니다')
    return dict(result, status='selected', code=reason,
                message='오늘 처음 발견한 최근 공지' if reason == 'new' else f'마감 {dday}일 전 재안내')


def build_items(rows, state, channels, *, now=None, reports=(), context=None):
    now = now or datetime.now(SEOUL)
    if now.utcoffset() != timedelta(hours=9):
        raise ValueError('판정 시각은 Asia/Seoul +09:00이어야 합니다')
    day = now.date()
    errors = [dict(source=name, message=message) for name, message in (
        ('weather', '오늘 날씨를 수집하지 않았습니다'),
        ('meals', '오늘 식단은 로컬에서 아직 수집하지 않았습니다'),
        ('schedule', '오늘 학사일정을 수집하지 않았습니다'))] if context is None else []
    if context is not None:
        checked = datetime.fromisoformat(context['collected_at'])
        if context['date'] != day.isoformat() or checked.utcoffset() != timedelta(hours=9) or checked.date() != day or checked > now:
            raise ValueError('날씨·학식·일정 자료의 한국 날짜·확인 시각이 맞지 않습니다')
        errors.extend(context['errors'])
        seen_sources = {row['source'] for row in context.get('sources', [])}
        seen_sources.update(row['source'] for row in context['errors'])
        from collector.daily_sources import MEAL_SOURCES
        meal_requested = (any(row.get('channel_id') in MEAL_SOURCES for row in context['channels'])
                          or any(source in MEAL_SOURCES for source in seen_sources))
        if not meal_requested:
            errors.append(dict(source='meals', message='오늘 식단은 로컬에서 아직 수집하지 않았습니다'))
    failed_urls = set()
    checked_boards = set()
    for report in reports:
        for board in report['channels']:
            if datetime.fromisoformat(board['started_at']).date() != day:
                raise ValueError('다른 날짜의 수집 보고서는 오늘 자료에 합칠 수 없습니다')
            if board.get('window_complete') and not board['truncated']:
                checked_boards.add(board['source_board_id'])
            for error in board['errors']:
                url = error.get('url')
                message = error['message'] + (' (' + url + ')' if url else '')
                errors.append(dict(source=error['source'], message=message))
                if url:
                    failed_urls.add(unquote(url))
            if board['truncated']:
                errors.append(dict(source=board['channel_id'], message='페이지 제한으로 수집 범위를 다 확인하지 못했습니다'))
    result = []
    for channel in channels:
        board = channel['source_board_id']
        baseline = state['boards'].get(board, {}).get('initialized_at')
        linked = [r for r in rows if r['source_board_id'] == board and channel['id'] in r['channel_ids']]
        if baseline is None:
            errors.append(dict(source=channel['id'], message='게시판 운영 시작이 아직 완료되지 않았습니다'))
        fresh = {r['id'] for r in linked if datetime.fromisoformat(r['last_checked_at']).date() == day
                 and datetime.fromisoformat(r['last_checked_at']) <= now and unquote(r['url']) not in failed_urls}
        if not linked and board not in checked_boards:
            errors.append(dict(source=channel['id'], message='오늘 목록 확인 기록이 없습니다. 빈 게시판인지 확인할 수 없습니다'))
        if linked and not fresh:
            errors.append(dict(source=channel['id'], message='오늘 확인한 상세 자료가 없습니다. 저장된 과거 자료는 선정하지 않았습니다'))
        notices = []
        for row in linked:
            decision = decide_notice(row, baseline, now, failed_urls)
            if decision['code'] == 'stale':
                errors.append(dict(source=channel['id'], message=row['id'] + ': 선정 후보의 오늘 상세 확인이 없어 제외했습니다'))
            if decision['status'] != 'selected':
                continue
            notices.append(dict(id=row['id'], channel_id=channel['id'], source=channel['name'],
                                title=row['title'], url=row['url'], posted_at=row['posted_at'],
                                deadline=row['deadline'], dday=decision['dday'], body=row['body'], reason=decision['reason']))
            if row['body_status'] in {'image-only', 'attachment-only', 'needs-review'}:
                errors.append(dict(source=channel['id'], message=row['id'] + ': 본문을 온전히 읽지 못했습니다 (' + row['body_status'] + ')'))
        notices.sort(key=lambda r: (r['dday'] if r['dday'] is not None else 10**9, r['id']))
        result.append(dict(channel_id=channel['id'], notices=notices, meals=[]))
    if context is not None:
        from collector.daily_sources import MEAL_SOURCES
        for channel in context['channels']:
            if channel['channel_id'] not in MEAL_SOURCES or channel['notices']:
                raise ValueError('날씨·학식·일정 자료에 잘못된 채널이 있습니다')
            result.append(channel)
    errors = [dict(source=source, message=message) for source, message in
              dict.fromkeys((e['source'], e['message']) for e in errors)]
    return dict(date=day.isoformat(), collected_at=now.isoformat(),
                weather=context['weather'] if context is not None else dict(summary=None, temp_min=None, temp_max=None, rain_prob=None),
                channels=result, schedule=context['schedule'] if context is not None else [], errors=errors)


def load_context():
    path = Path(__file__).resolve().parents[1] / 'data/raw' / datetime.now(SEOUL).date().isoformat() / 'context.json'
    return load_collection_report(path) if path.exists() else None


def main():
    from collector.run import ROOT, VALIDATION_PATH, select_channels, board_id_for
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-path', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--channel-id', action='append')
    parser.add_argument('--collection-report', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    channels = yaml.safe_load((ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    validation = load_collection_report(VALIDATION_PATH)
    selected = select_channels(channels, args.channel_id, validation=validation)
    # 공유 게시판의 각 논리 채널을 출력한다.
    by_id = {c['id']: c for c in channels}
    logical = [dict(by_id[id], source_board_id=board_id_for(c)) for c in selected for id in c['channel_ids']]
    now = datetime.now(SEOUL)
    items = build_items(load_notices(args.db_path), load_collection_state(args.db_path), logical, now=now,
                        reports=[load_collection_report(p) for p in args.collection_report], context=load_context())
    path = args.output or ROOT / 'data/raw' / items['date'] / 'items.json'
    save_daily_items(items, path)
    print(f"{items['date']}: 채널 {len(items['channels'])}개 / 공지 {sum(len(c['notices']) for c in items['channels'])}개 / 확인할 항목 {len(items['errors'])}개")
    print(path)


if __name__ == '__main__':
    main()
