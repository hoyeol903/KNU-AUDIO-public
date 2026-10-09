import json
from briefing.review import failure_details
from briefing.slm import generate_segments


def test_failed_attempts_keep_redacted_drafts_only_in_private_report(tmp_path):
    class Provider:
        def identity(self):
            return 'test'

        def generate(self, payload, errors):
            return '비용 999원, 연락 person@example.edu 또는 010-1234-5678, 학번 20261234'

    segment = dict(id='one', notice_id='notice-one', kind='notice', generation='slm',
                   title='모집', source_text='비용 100원', reference='', channel_ids=['test'], url=None)
    report_path = tmp_path / 'review.json'
    generate_segments([segment], Provider(), tmp_path, report_path)
    report = json.loads(report_path.read_text())
    attempts = report['segments'][0]['attempts']
    assert len(attempts) == 1
    assert attempts[0]['script'].count('[개인정보 가림]') == 3
    assert any(f['rule'] == 'number' and f['match'] == '999' for f in attempts[0]['findings'])
    for raw in ('person@example.edu', '010-1234-5678', '20261234'):
        assert raw not in report_path.read_text()
    assert '_skip_notice' not in segment
    assert segment['review']['status'] == 'revision-unchecked'
    assert segment['review']['passed'] is None
    assert list((tmp_path / 'scripts').glob('*.json'))


def test_diagnostic_redaction_handles_invalid_and_overlapping_identifiers():
    assert failure_details(None, {})['script'] is None
    result = failure_details('주민번호 900101-1234567, 씨발', {})
    assert '900101' not in result['script'] and '1234567' not in result['script']
    assert '씨발' not in result['script']


def test_diagnostics_mask_four_digit_phone_prefix():
    result = failure_details("문의 0507-1234-5678", {})
    assert result["script"] == "문의 [개인정보 가림]"
    assert "1234" not in json.dumps(result, ensure_ascii=False)


def test_evening_range_and_explicit_table_unit_regressions():
    from briefing.review import review, revision_feedback
    source = dict(source_text='검사 일시: 19:00~19:50', reference='')
    assert not review('검사는 저녁 7시부터 7시 50분까지예요.', source)
    assert review('검사는 저녁 7시부터 8시까지예요.', source)
    correction = revision_feedback('검사는 저녁 8시에 끝나요.', source)
    assert correction['issues'][0]['value'] == '20:0'
    assert '검사 일시: 19:00~19:50' in correction['issues'][0]['source_quotes']
    assert not review('아침 9시예요.', dict(source_text='09:00', reference=''))
    assert not review('밤 12시예요.', dict(source_text='00:00', reference=''))
    table = dict(source_text='1) 객실 (단위:원)\n14인실\n70,000\n2) 신청\n80,000', reference='')
    assert not review('객실 요금은 7만 원이에요.', table)
    assert review('객실 요금은 8만 원이에요.', table)
    assert review('객실 요금은 7만 원이에요.', dict(source_text='객실\n70,000', reference=''))


def test_retry_receives_masked_first_draft_and_source_evidence(tmp_path):
    from copy import deepcopy
    calls = []
    class Provider:
        def identity(self): return 'test'
        def generate(self, payload, errors):
            calls.append(deepcopy(payload))
            return '검사는 저녁 8시에 끝나요.' if not errors else '검사는 저녁 7시 50분에 끝나요.'
    row = dict(id='one', kind='notice', generation='slm', title='검사',
               source_text='검사 일시: 19:00~19:50\n문의 person@example.edu', reference='')
    generate_segments([row], Provider(), tmp_path, tmp_path / 'review.json')
    assert len(calls) == 2
    assert 'person@example.edu' not in json.dumps(calls)
    assert '[개인정보 가림]' not in calls[0]['source_text']
    assert calls[1]['revision']['previous_script'] == '검사는 저녁 8시에 끝나요.'
    assert calls[1]['revision']['issues'][0]['source_quotes'] == ['검사 일시: 19:00~19:50']
    assert row['review']['status'] == 'revision-unchecked'


def test_saved_five_failures_keep_real_errors_and_remove_known_false_positives():
    from pathlib import Path
    from briefing.review import review
    rows = json.loads((Path(__file__).parent / 'fixtures/review-20261007.json').read_text())
    assert not review('검사는 저녁 7시부터 7시 50분까지예요.', rows[0])
    assert review('검사는 저녁 7시부터 8시까지예요.', rows[0])
    assert review(rows[1]['first_draft'], rows[1])  # 2026 -> 2:26 remains an error.
    assert not review('14인실 요금은 7만 원이에요.', rows[3])


def test_redaction_markers_are_not_spoken():
    from briefing.review import review
    assert review('문의는 [개인정보 가림]입니다.', dict(source_text='문의처', reference=''))


def test_retry_and_its_cache_skip_second_review(tmp_path, monkeypatch):
    from unittest.mock import Mock
    import briefing.slm as slm
    checker = Mock(return_value=['원문 자료에 없는 숫자 값이 있습니다.'])
    monkeypatch.setattr(slm, 'review', checker)
    provider = Mock()
    provider.identity.return_value = 'test'
    provider.generate.side_effect = ['999원입니다.', '888원입니다.']
    row = dict(id='one', kind='notice', generation='slm', title='비용',
               source_text='100원', reference='')
    generate_segments([row], provider, tmp_path, tmp_path/'review.json')
    assert checker.call_count == 1
    assert row['script'] == '888원입니다.'
    assert row['review']['passed'] is None
    generate_segments([row], provider, tmp_path, tmp_path/'review.json')
    assert checker.call_count == 1 and provider.generate.call_count == 2


def test_empty_second_draft_still_fails(tmp_path):
    import pytest
    from unittest.mock import Mock
    provider = Mock()
    provider.identity.return_value = 'test'
    provider.generate.side_effect = ['999원입니다.', '   ']
    row = dict(id='one', kind='notice', generation='slm', title='비용', source_text='100원', reference='')
    with pytest.raises(ValueError, match='비어'):
        generate_segments([row], provider, tmp_path, tmp_path/'review.json')
