"""원문의 명시된 마감일만 읽는다. 연도 생략·여러 마감·선착순은 검토 대상으로 남긴다."""
import argparse
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from collector.store import DEFAULT_PATH, SEOUL, load_notices, save_collection_report, update_deadlines

ACTION = r'(?:신청|접수|제출|등록|납부|응모|모집|참여|추천|회신)'
LABEL = re.compile(ACTION + r'\s*(?:기간|기한|마감(?:일)?)|마감\s*(?:일|기한)?')
FULL_DATE = re.compile(r'(?<!\d)(\d{4})\s*(?:[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})\.?|년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일)(?!\d)')
SHORT_DATE = re.compile(r'(?<!\d)\d{1,2}\s*(?:[./-]\s*\d{1,2}|월\s*\d{1,2}\s*일)')
DATE_SUFFIX = r'\s*(?:\([월화수목금토일](?:요일)?\)\s*)?(?:\d{1,2}\s*(?::\s*\d{2}|시(?:\s*\d{1,2}분)?)\s*)?'
UNTIL = re.compile('^' + DATE_SUFFIX + r'(?:까지|마감)')
RANGE = re.compile('^' + DATE_SUFFIX + r'[~∼〜～–—-]\s*$')
CONDITIONAL = re.compile(r'선착순|조기\s*(?:마감|종료)|소진|모집\s*인원\s*마감|상시|수시|추후|별도\s*안내|미정|미확정')
EARLY_CLOSE = re.compile(r'선착순|조기\s*(?:마감|종료)|소진|모집\s*인원\s*마감')
RELATIVE = re.compile(r'부터|이내|이후|이전|익일|당일|다음\s*날|\d+\s*(?:일|주|개월)\s*(?:간|후)')


def extract_deadline(title, body):
    """deadline/status/evidence/reason 반환. 게시일·제목의 학년도에서 연도를 빌리지 않는다."""
    if not isinstance(title, str) or (body is not None and not isinstance(body, str)):
        raise ValueError('제목·본문은 문자열이어야 합니다')
    lines = [line.strip() for line in (title + '\n' + (body or '')).splitlines() if line.strip()]
    evidence, candidates, reasons = [], set(), set()
    for index, line in enumerate(lines):
        labels = list(LABEL.finditer(line))
        dates = list(FULL_DATE.finditer(line))
        # 표/문단에서 날짜가 다음 줄에 있는 경우만 이어 읽는다.
        if labels and not dates and not line[labels[-1].end():].strip(' :：.ㆍ·') and index + 1 < len(lines):
            line += ' ' + lines[index + 1]
            dates = list(FULL_DATE.finditer(line))
        until_action = False
        if not labels:
            for stamp in dates:
                suffix = line[stamp.end():]
                before = line[max(0, stamp.start() - 30):stamp.start()]
                until = UNTIL.match(suffix)
                if until and (re.search(ACTION + r'\s*[:：]\s*$', before) or
                              re.match(r'\s*' + ACTION, suffix[until.end():])):
                    until_action = True
                    break
            if not until_action:
                continue
        # 원문 근거를 그대로 남겨 사람이 확인할 수 있게 한다.
        evidence.append(line)
        if CONDITIONAL.search(line):
            reasons.add('조건부·상시 마감')
            continue
        if len(labels) > 1:
            reasons.add('한 문장에 여러 신청·마감 항목')
            continue
        if labels:
            label = labels[0]
            tail = line[label.end():]
            stamps = list(FULL_DATE.finditer(tail))
            period = '기간' in label.group()
        else:
            tail, stamps, period = line, dates, False
        if RELATIVE.search(tail):
            reasons.add('상대적인 기한 표현이 섞여 있음')
            continue
        if not stamps:
            reasons.add('연도까지 명시된 마감 날짜 없음')
            continue
        values = []
        invalid = False
        for stamp in stamps:
            try:
                y, m, d, km, kd = stamp.groups()
                values.append(date(int(y), int(m or km), int(d or kd)))
            except ValueError:
                invalid = True
        if invalid:
            reasons.add('유효하지 않은 날짜')
            continue
        # 완전한 날짜 2개가 명시된 단일 기간만 종료일을 선택한다.
        if len(stamps) == 2 and RANGE.fullmatch(tail[stamps[0].end():stamps[1].start()]):
            if values[1] < values[0]:
                reasons.add('시작일보다 빠른 종료일')
                continue
            suffix = tail[stamps[-1].end():]
            if SHORT_DATE.search(suffix) or re.search(r'[~∼〜～]', suffix):
                reasons.add('추가 날짜·기간이 섞여 있음')
                continue
            candidates.add(values[-1].isoformat())
        elif len(stamps) == 1:
            stamp = stamps[0]
            prefix, suffix = tail[:stamp.start()], tail[stamp.end():]
            if SHORT_DATE.search(prefix) or SHORT_DATE.search(suffix) or re.search(r'[~∼〜～]', suffix):
                reasons.add('연도 생략 또는 여러 날짜·기간')
            elif period and not UNTIL.match(suffix) and not prefix.strip(' :：').endswith(('~', '∼', '〜', '～')):
                reasons.add('기간의 종료일인지 불명확')
            else:
                candidates.add(values[0].isoformat())
        else:
            reasons.add('날짜와 마감 항목 관계가 불명확')
    if len(candidates) > 1:
        reasons.add('서로 다른 마감일이 여러 개')
    if candidates and EARLY_CLOSE.search(title + '\n' + (body or '')):
        reasons.add('본문에 조건부·미확정 안내가 있어 확인 필요')
    # ponytail: 모든 후보의 합의를 요구하는 보수적 규칙. 회차/대상별 마감은 수동 검토 후 별도 계약으로 확장.
    status = 'needs-review' if reasons else 'found' if candidates else 'not-found'
    return dict(deadline=next(iter(candidates)) if status == 'found' else None, status=status,
                evidence=list(dict.fromkeys(evidence)), reason='; '.join(sorted(reasons)) or None)


def backfill(*, db_path=DEFAULT_PATH, apply=False, report_path=None):
    rows = load_notices(db_path)
    counts, checks, updates = Counter(), [], {}
    for row in rows:
        result = extract_deadline(row['title'], row['body'])
        counts[result['status']] += 1
        if result['status'] != 'not-found':
            checks.append(dict(notice_id=row['id'], title=row['title'], url=row['url'],
                               posted_at=row['posted_at'], previous_deadline=row['deadline'], **result))
        if result['status'] == 'found' and row['deadline'] is None:
            updates[row['id']] = result['deadline']
    changed = update_deadlines(updates, path=db_path) if apply else []
    report = dict(created_at=datetime.now(SEOUL).isoformat(), mode='apply' if apply else 'preview',
                  checked=len(rows), counts=dict(counts), proposed=len(updates), updated=changed, checks=checks)
    if report_path is not None:
        save_collection_report(report, report_path)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-path', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--apply', action='store_true', help='기존 마감일이 비어 있는 글에만 적용')
    parser.add_argument('--report-path', type=Path)
    args = parser.parse_args()
    path = args.report_path or DEFAULT_PATH.parents[1] / 'runs' / (datetime.now(SEOUL).strftime('%Y%m%dT%H%M%S%f') + '-deadlines.json')
    result = backfill(db_path=args.db_path, apply=args.apply, report_path=path)
    print(f"확인 {result['checked']}개 / 판정 {result['counts']} / 적용 가능 {result['proposed']}개 / 실제 변경 {len(result['updated'])}개")
    print(f'근거와 검토 목록: {path}')


if __name__ == '__main__':
    main()
