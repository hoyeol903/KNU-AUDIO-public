"""공지 JSON 저장. 원문 수집과 브리핑 선정은 호출자가 담당한다."""
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from collector.privacy import redact

SEOUL = timezone(timedelta(hours=9))
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data/db/notices.json"
INPUT_FIELDS = {
    "source_board_id", "source_post_id", "channel_ids", "title", "url",
    "posted_at", "deadline", "body", "body_status",
}
STORED_FIELDS = INPUT_FIELDS | {"id", "first_seen_at", "last_checked_at", "content_hash"}
HASH_FIELDS = ("title", "posted_at", "deadline", "body", "body_status")
BODY_STATUSES = {"text", "image-only", "attachment-only", "empty", "needs-review"}


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("이력 시각은 +09:00 ISO 8601 문자열이어야 합니다")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("잘못된 이력 시각") from exc
    if parsed.utcoffset() != timedelta(hours=9) or "T" not in value:
        raise ValueError("이력 시각은 Asia/Seoul의 +09:00이어야 합니다")
    return parsed


def _validate(row, stored=False):
    fields = STORED_FIELDS if stored else INPUT_FIELDS
    if not isinstance(row, dict) or set(row) != fields:
        raise ValueError("공지의 필수 필드 누락 또는 알 수 없는 필드")
    for key in ("source_board_id", "source_post_id", "title", "url"):
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError(f"{key}는 비어 있지 않은 문자열이어야 합니다")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", row["source_board_id"]):
        raise ValueError("source_board_id는 소문자 영문·숫자·하이픈·밑줄 식별자입니다")
    if row["source_post_id"] != row["source_post_id"].strip():
        raise ValueError("source_post_id 앞뒤에 공백을 넣을 수 없습니다")
    if not re.match(r"https?://[^/\s]+(?:/|$)", row["url"]) or re.search(r"\s", row["url"]):
        raise ValueError("url은 HTTP(S) 원문 주소여야 합니다")
    channels = row["channel_ids"]
    if not isinstance(channels, list) or not channels or any(
        not isinstance(c, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", c)
        for c in channels
    ):
        raise ValueError("channel_ids는 비어 있지 않은 채널 ID 배열이어야 합니다")
    for key in ("posted_at", "deadline"):
        value = row[key]
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError(f"{key}는 YYYY-MM-DD 또는 null이어야 합니다")
            date.fromisoformat(value)
    status, body = row["body_status"], row["body"]
    if not isinstance(status, str) or status not in BODY_STATUSES:
        raise ValueError("알 수 없는 body_status")
    if body is not None and not isinstance(body, str):
        raise ValueError("body는 문자열 또는 null이어야 합니다")
    if status == "text" and (body is None or not body.strip()):
        raise ValueError("text 상태에는 실제 본문 텍스트가 필요합니다")
    if status == "empty" and body != "":
        raise ValueError("확인된 빈 본문은 empty와 빈 문자열로 기록합니다")
    if status in {"image-only", "attachment-only"} and body is not None:
        raise ValueError("텍스트를 읽지 못한 이미지·첨부 전용 본문은 null입니다")
    if stored:
        if channels != sorted(set(channels)):
            raise ValueError("저장된 채널 ID는 중복 없이 정렬돼야 합니다")
        if row["id"] != _notice_id(row) or row["content_hash"] != _content_hash(row):
            raise ValueError("저장된 공지 ID 또는 내용 해시가 일치하지 않습니다")
        if _timestamp(row["first_seen_at"]) > _timestamp(row["last_checked_at"]):
            raise ValueError("마지막 확인 시각이 최초 발견 시각보다 빠릅니다")


def _notice_id(row):
    return row["source_board_id"] + ":" + row["source_post_id"]


def _content_hash(row):
    content = {key: row[key] for key in HASH_FIELDS}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load_notices(path=DEFAULT_PATH):
    """미생성 파일은 []; 손상된 JSON·잘못된 레코드는 예외로 알린다."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        rows = json.load(stream)
    if not isinstance(rows, list):
        raise ValueError("공지 저장 파일의 최상위 값은 배열이어야 합니다")
    for row in rows:
        _validate(row, stored=True)
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("저장 파일에 중복 공지 ID가 있습니다")
    return rows


def _write_atomic(path, rows):
    rows = redact(rows)
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and set(row) == STORED_FIELDS:
                row['content_hash'] = _content_hash(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(rows, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_json(value, path):
    """임의의 정적 전달 JSON을 공통 저장 규칙으로 원자적으로 쓴다."""
    _write_atomic(Path(path), value)


def upsert_notices(notices, *, checked_at=None, path=DEFAULT_PATH):
    """검증된 상세 확인 결과를 병합. new/updated/unchanged ID 목록을 반환한다.

    한 호출의 모든 입력을 검증한 뒤 저장한다. 요청·파싱 실패는 이 함수에
    빈 공지로 전달하지 않고 호출자가 errors로 기록한다.
    """
    if checked_at is None:
        checked_at = datetime.now(SEOUL).isoformat()
    checked = _timestamp(checked_at)
    if not isinstance(notices, list):
        raise ValueError("notices는 배열이어야 합니다")
    pending = {}
    for row in notices:
        _validate(row)
        row = dict(redact(row), channel_ids=sorted(set(row["channel_ids"])))
        key = _notice_id(row)
        if key in pending:
            prior = pending[key]
            if any(row[k] != prior[k] for k in INPUT_FIELDS - {"channel_ids"}):
                raise ValueError(f"동일 글의 상충하는 입력: {key}")
            row["channel_ids"] = sorted(set(row["channel_ids"]) | set(prior["channel_ids"]))
        pending[key] = row
    # ponytail: 단일 writer 전제. Actions 실행을 직렬화하고 다중 writer가 필요하면 파일 잠금 추가.
    existing = {row["id"]: row for row in load_notices(path)}
    result = {"new": [], "updated": [], "unchanged": []}
    for key, row in sorted(pending.items()):
        previous = existing.get(key)
        if previous is not None and checked < _timestamp(previous["last_checked_at"]):
            raise ValueError(f"과거 수집 결과로 최신 공지를 덮어쓸 수 없습니다: {key}")
        digest = _content_hash(row)
        if previous is None:
            change = "new"
        else:
            change = "updated" if previous["content_hash"] != digest else "unchanged"
            row["channel_ids"] = sorted(set(row["channel_ids"]) | set(previous["channel_ids"]))
        existing[key] = dict(row, id=key, content_hash=digest, last_checked_at=checked_at,
                             first_seen_at=previous["first_seen_at"] if previous else checked_at)
        result[change].append(key)
    if pending:
        _write_atomic(Path(path), [existing[key] for key in sorted(existing)])
    return result


def save_collection_report(report, path):
    """공지 DB와 별도로 수집 결과·실패 내역을 원자적으로 저장한다."""
    _write_atomic(Path(path), report)


def save_daily_items(items, path):
    """채널별 전달 파일의 날짜·중복·선정 이유를 확인하고 원자적으로 저장."""
    if not isinstance(items, dict) or set(items) != {'date', 'collected_at', 'weather', 'channels', 'schedule', 'errors'}:
        raise ValueError('items.json 최상위 필드가 잘못됐습니다')
    if not isinstance(items['date'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', items['date']):
        raise ValueError('items 날짜는 YYYY-MM-DD이어야 합니다')
    day = date.fromisoformat(items['date'])
    if _timestamp(items['collected_at']).date() != day:
        raise ValueError('items 날짜와 생성 시각의 한국 날짜가 다릅니다')
    if not isinstance(items['channels'], list) or not isinstance(items['errors'], list):
        raise ValueError('채널과 오류는 배열이어야 합니다')
    if not isinstance(items['weather'], dict) or set(items['weather']) != {'summary', 'temp_min', 'temp_max', 'rain_prob'} or not isinstance(items['schedule'], list):
        raise ValueError('날씨·일정 구조가 잘못됐습니다')
    weather = items['weather']
    if weather['summary'] is not None and (not isinstance(weather['summary'], str) or not weather['summary'].strip()):
        raise ValueError('날씨 요약 자료형 오류')
    for key in ('temp_min', 'temp_max', 'rain_prob'):
        value = weather[key]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError('날씨 숫자 자료형 오류')
    if weather['rain_prob'] is not None and not 0 <= weather['rain_prob'] <= 100:
        raise ValueError('강수 확률은 0~100입니다')
    if weather['temp_min'] is not None and weather['temp_max'] is not None and weather['temp_min'] > weather['temp_max']:
        raise ValueError('최저 기온이 최고 기온보다 높습니다')
    for row in items['schedule']:
        if not isinstance(row, dict) or set(row) != {'title', 'start', 'end', 'dday'} or not isinstance(row['title'], str) or not row['title'].strip():
            raise ValueError('학사일정 필드 오류')
        for key in ('start', 'end'):
            if row[key] is None and key == 'end':
                continue
            if not isinstance(row[key], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row[key]):
                raise ValueError('학사일정 날짜 형식 오류')
            date.fromisoformat(row[key])
        if row['end'] is not None and row['end'] < row['start']:
            raise ValueError('학사일정 종료일 오류')
        if type(row['dday']) is not int or row['dday'] != (date.fromisoformat(row['start']) - day).days:
            raise ValueError('학사일정 남은 일수 오류')
    for error in items['errors']:
        if not isinstance(error, dict) or set(error) != {'source', 'message'} or any(not isinstance(v, str) or not v.strip() for v in error.values()):
            raise ValueError('오류의 출처·메시지가 잘못됐습니다')
    ids = set()
    for channel in items['channels']:
        if not isinstance(channel, dict) or set(channel) != {'channel_id', 'notices', 'meals'} or not isinstance(channel['notices'], list) or not isinstance(channel['meals'], list):
            raise ValueError('채널 필드가 잘못됐습니다')
        key = channel['channel_id']
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', key) or key in ids:
            raise ValueError('잘못되거나 중복된 채널 ID')
        ids.add(key)
        for meal in channel['meals']:
            if not isinstance(meal, dict) or set(meal) != {'place', 'time', 'menu'} or not isinstance(meal['place'], str) or not meal['place'].strip():
                raise ValueError('학식 필드 오류')
            if meal['time'] is not None and (not isinstance(meal['time'], str) or not meal['time'].strip()):
                raise ValueError('학식 시간 자료형 오류')
            if not isinstance(meal['menu'], list) or not meal['menu'] or any(not isinstance(v, str) or not v.strip() for v in meal['menu']):
                raise ValueError('학식 메뉴 오류')
        posts = set()
        for row in channel['notices']:
            if not isinstance(row, dict) or set(row) != {'id', 'channel_id', 'source', 'title', 'url', 'posted_at', 'deadline', 'dday', 'body', 'reason'}:
                raise ValueError('전달 공지 필드가 잘못됐습니다')
            if any(not isinstance(row[k], str) or not row[k].strip() for k in ('id', 'source', 'title', 'url')):
                raise ValueError('공지 ID·출처·제목·주소가 비었습니다')
            if not re.match(r'https?://[^/\s]+(?:/|$)', row['url']) or re.search(r'\s', row['url']) or (row['body'] is not None and not isinstance(row['body'], str)):
                raise ValueError('원문 주소·본문 자료형이 잘못됐습니다')
            for k in ('posted_at', 'deadline'):
                if row[k] is not None:
                    if not isinstance(row[k], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row[k]):
                        raise ValueError('공지 날짜 형식이 잘못됐습니다')
                    date.fromisoformat(row[k])
            if row['channel_id'] != key or row['id'] in posts or row['reason'] not in {'new', 'reminder'}:
                raise ValueError('공지 채널·중복·선정 이유가 잘못됐습니다')
            posts.add(row['id'])
            expected = (date.fromisoformat(row['deadline']) - day).days if row['deadline'] else None
            if (row['dday'] is not None and type(row['dday']) is not int) or row['dday'] != expected or (expected is not None and expected < 0) or (row['reason'] == 'reminder' and expected not in {0, 1, 3}):
                raise ValueError('마감 남은 일수·알림 조건이 잘못됐습니다')
    _write_atomic(Path(path), items)


def update_deadlines(deadlines, *, path=DEFAULT_PATH):
    """저장된 원문에서 뽑은 마감일만 갱신. 실제 사이트 확인 시각을 바꾸지 않는다."""
    if not isinstance(deadlines, dict):
        raise ValueError('마감일 갱신은 공지 ID와 날짜의 객체여야 합니다')
    rows = load_notices(path)
    by_id = {row['id']: row for row in rows}
    if deadlines.keys() - by_id.keys():
        raise ValueError('저장되지 않은 공지의 마감일을 바꿀 수 없습니다')
    changed = []
    for key, deadline in deadlines.items():
        row = by_id[key]
        if row['deadline'] == deadline:
            continue
        row['deadline'] = deadline
        row['content_hash'] = _content_hash(row)
        _validate(row, stored=True)
        changed.append(key)
    if changed:
        _write_atomic(Path(path), rows)
    return sorted(changed)


def link_board_channels(board_id, channel_ids, path=DEFAULT_PATH):
    """같은 게시판의 채널 연결만 추가. 본문 해시·상세 확인 시각은 유지한다."""
    if not channel_ids or any(not isinstance(c, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', c) for c in channel_ids):
        raise ValueError('잘못된 채널 ID')
    rows = load_notices(path)
    changed = 0
    for row in rows:
        if row['source_board_id'] == board_id:
            merged = sorted(set(row['channel_ids']) | set(channel_ids))
            if merged != row['channel_ids']:
                row['channel_ids'] = merged
                changed += 1
    if changed:
        _write_atomic(Path(path), rows)
    return changed


def load_collection_report(path):
    """저장한 실행 보고서를 읽는다. 누락·손상은 예외로 알린다."""
    with Path(path).open(encoding='utf-8') as stream:
        report = json.load(stream)
    if not isinstance(report, dict):
        raise ValueError('실행 보고서는 객체여야 합니다')
    return report


def collection_state_path(db_path=DEFAULT_PATH):
    path = Path(db_path)
    return path.with_name(path.stem + '-collection-state.json')


def _validate_collection_state(state):
    if not isinstance(state, dict) or set(state) != {'boards'} or not isinstance(state['boards'], dict):
        raise ValueError('수집 상태는 boards 객체여야 합니다')
    for board, markers in state['boards'].items():
        if not isinstance(board, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', board):
            raise ValueError('잘못된 수집 상태 게시판 ID')
        if not isinstance(markers, dict) or set(markers) != {'initialized_at', 'last_full_scan_at'}:
            raise ValueError('수집 상태의 기준 시각 필드가 잘못됐습니다')
        for value in markers.values():
            if value is not None:
                _timestamp(value)
        if markers['last_full_scan_at'] is not None and markers['initialized_at'] is None:
            raise ValueError('초기 적재 없이 전체 점검을 완료할 수 없습니다')


def load_collection_state(db_path=DEFAULT_PATH):
    path = collection_state_path(db_path)
    if not path.exists():
        return {'boards': {}}
    with path.open(encoding='utf-8') as stream:
        state = json.load(stream)
    _validate_collection_state(state)
    return state


def save_collection_state(state, db_path=DEFAULT_PATH):
    _validate_collection_state(state)
    _write_atomic(collection_state_path(db_path), state)
