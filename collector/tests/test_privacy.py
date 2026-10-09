import json

from collector.privacy import redact_text, redact
from collector.store import upsert_notices, load_notices, save_json


def test_redaction_keeps_source_facts_and_official_contacts():
    source='학번: 2099123456\n성명: 가나별\n가나별 씨가 수상했습니다.\n연락 010-2345-6789\n신청 2026-10-12 12:00, 복지관 3층, 선착순 30명\n053-950-1234 office@knu.ac.kr'
    output=redact_text(source)
    assert '2099123456' not in output and '가나별' not in output and '010-2345-6789' not in output
    assert '신청 2026-10-12 12:00, 복지관 3층, 선착순 30명' in output
    assert '053-950-1234 office@knu.ac.kr' in output
    assert redact_text(output)==output


def test_html_fixture_identifiers_are_also_masked():
    output=redact_text('<p>학번:</p><p>2099123456</p><p>성명: 가나별</p>')
    assert '2099123456' not in output and '가나별' not in output
    assert output.count('<p>')==3
    assert redact_text('공모전에는 학번을 입력하세요. 신청기간 2026년 10월 12일까지.')=='공모전에는 학번을 입력하세요. 신청기간 2026년 10월 12일까지.'


def test_store_hash_uses_redacted_body_and_repeat_collection_is_unchanged(tmp_path):
    notice=dict(source_board_id='test',source_post_id='1',channel_ids=['test'],title='수상 안내',
        url='https://example.com/1',posted_at='2026-10-09',deadline=None,
        body='학번: 2099123456\n성명: 가나별',body_status='text')
    path=tmp_path/'notices.json'
    assert upsert_notices([notice],checked_at='2026-10-09T05:00:00+09:00',path=path)['new']==['test:1']
    rows=load_notices(path)
    assert '2099123456' not in rows[0]['body']
    assert upsert_notices([notice],checked_at='2026-10-10T05:00:00+09:00',path=path)['unchanged']==['test:1']
    assert notice['body'].startswith('학번: 2099')


def test_other_json_outputs_are_redacted_without_changing_schema(tmp_path):
    value=dict(date='2026-10-09',channels=[dict(body='연락 01023456789')],dday=3)
    path=tmp_path/'items.json';save_json(value,path)
    saved=json.loads(path.read_text())
    assert saved==redact(value) and set(saved)==set(value)
    assert saved['dday']==3 and '01023456789' not in path.read_text()


def test_roster_table_and_attachment_password_are_not_republished():
    text = '납부기간: 2026. 10. 14.~10. 15. 16:00\n학번\n성명\n2099123456\n가나별\n2099****56\n가*별'
    result = redact_text(text)
    assert result == '납부기간: 2026. 10. 14.~10. 15. 16:00\n[개인정보 가림]'
    assert redact_text('붙임 명단 (PW 9999)') == '붙임 명단 (PW [개인정보 가림])'
    assert redact_text('대상: 2026학번, 신청 2026-10-14') == '대상: 2026학번, 신청 2026-10-14'


def test_names_only_roster_is_masked_with_notice_context():
    notice = {'title': '교직 선발 명단', 'body': '2학년 가나별\n2학년 다라별\n오리엔테이션 2026-10-15 14:00'}
    result = redact(notice)
    assert '가나별' not in result['body'] and '다라별' not in result['body']
    assert '2026-10-15 14:00' in result['body']
