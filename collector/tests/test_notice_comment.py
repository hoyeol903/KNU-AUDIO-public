import csv
import json

from tools import notice_comment


STARTED = '2026-10-06T07:00:00+09:00'
CHANNELS = [
    dict(id='channel-a', name='A학과 | 공지', source_url='https://example.com/a'),
    dict(id='channel-b', name='B학과', source_url='https://example.com/b'),
]


def test_failure_rows_deduplicate_merged_board_errors_and_keep_prior_failures():
    report = dict(started_at=STARTED, channels=[
        dict(source_board_id='shared', channel_id='channel-a', channel_ids=['channel-a'], started_at=STARTED,
             errors=[dict(source='channel-a', url='https://example.com/fail|1',
                          message='ConnectTimeout: timed out')], truncated=False, window_complete=False),
        dict(source_board_id='shared', channel_id='channel-b', channel_ids=['channel-b'], started_at=STARTED,
             errors=[dict(source='channel-b', url='https://example.com/fail|1',
                          message='ConnectTimeout: timed out')], truncated=False, window_complete=False),
        dict(source_board_id='old', channel_id='channel-b', channel_ids=['channel-b'],
             started_at='2026-10-05T07:00:00+09:00', errors=[dict(url='https://example.com/old', message='old')],
             truncated=False, window_complete=False),
    ], extras={'errors': []})
    rows = notice_comment.failure_rows(report, CHANNELS, STARTED)
    assert len(rows) == 2
    shared = next(row for row in rows if row['url'].endswith('fail|1'))
    assert shared['board'] == 'A학과 | 공지 / B학과'
    assert shared['cause'] == '요청 시간 초과'
    assert shared['original'] == 'ConnectTimeout: timed out'
    assert shared['status'] == '이번 실행 실패'
    assert next(row for row in rows if row['url'].endswith('/old'))['status'] == '이전 실패 · 재수집 대기'


def test_failures_use_report_not_items_warnings():
    report = dict(started_at=STARTED, channels=[], extras={'errors': []})
    items_with_informational_warnings = dict(errors=[dict(source='channel-a', message='본문 미확인')] * 70)
    rows = notice_comment.failure_rows(report, CHANNELS, STARTED)
    assert items_with_informational_warnings['errors'] and rows == []


def test_board_timestamp_rounded_to_seconds_is_current_run():
    report = dict(started_at='2026-10-06T07:00:01+09:00', channels=[
        dict(source_board_id='board-a', channel_id='channel-a', channel_ids=['channel-a'],
             started_at='2026-10-06T07:00:00+09:00', errors=[dict(message='timeout')],
             truncated=False, window_complete=False),
    ])
    rows = notice_comment.failure_rows(report, CHANNELS, '2026-10-06T07:00:00.900000+09:00')
    assert rows[0]['status'] == '이번 실행 실패'


def test_failure_rows_include_truncation_and_extra_errors():
    report = dict(started_at=STARTED, channels=[
        dict(source_board_id='board-a', channel_id='channel-a', channel_ids=['channel-a'], started_at=STARTED,
             errors=[], truncated=True, window_complete=False),
    ], extras={'errors': [dict(source='weather', url='https://example.com/weather', message='ReadTimeout')]})
    rows = notice_comment.failure_rows(report, CHANNELS, STARTED)
    assert {(row['board'], row['cause']) for row in rows} == {
        ('A학과 | 공지', '수집 오류'), ('날씨', '요청 시간 초과')}


def test_load_current_report_rejects_stale_or_missing_started_at(tmp_path):
    report = tmp_path / 'report.json'
    report.write_text(json.dumps(dict(started_at='2026-10-05T07:00:00+09:00', channels=[])))
    assert notice_comment.load_current_report(report, STARTED) is None
    report.write_text(json.dumps(dict(channels=[])))
    assert notice_comment.load_current_report(report, STARTED) is None


def test_failure_csv_has_bom_and_header_when_there_are_no_failures(tmp_path):
    path = tmp_path / 'collection-failures.csv'
    notice_comment.write_failures([], path)
    assert path.read_bytes().startswith(b'\xef\xbb\xbf')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        assert next(csv.reader(stream)) == notice_comment.FAILURE_FIELDS


def test_export_failure_fallback_omits_stale_notice_links_and_rows():
    text = notice_comment.comment([dict(기준일='2026-10-06', 구분='신규', 게시판='old', 제목='old',
                                        링크='https://example.com', 게시일='', 마감일='')],
                                  'org/repo', 'a' * 40, 'owner', export_outcome='failure',
                                  report_available=True, run_url='https://example.com/actions/1')
    assert 'old' not in text
    assert notice_comment.SITE_URL not in text
    assert '정적 앱 자료 생성에 실패' in text
    assert 'https://example.com/actions/1' in text


def test_comment_escapes_markdown_cells_and_does_not_claim_success_without_report():
    text = notice_comment.comment([], 'org/repo', 'sha', 'owner',
                                  failures=[dict(board='a|b', url='https://x/<bad>', cause='[timeout]', status='이번 실행 실패')],
                                  report_available=True)
    assert r'a\|b' in text and '&lt;bad&gt;' in text and r'\[timeout\]' in text
    fallback = notice_comment.comment([], 'org/repo', 'sha', 'owner', report_available=False,
                                      collection_outcome='success')
    assert '수집 완료' not in fallback
    assert '보고서가 없습니다' in fallback
