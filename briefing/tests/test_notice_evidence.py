from briefing.content import notice_fact_hints, notice_generation_evidence, notice_required_anchors
from briefing.material import clean_notice_text
from briefing.slm import _script_errors, _script_payload


def test_labeled_notice_evidence_tracks_deadline_event_audience_method_docs_and_condition():
    title = '교직 검사 시행 안내'
    body = '''신청기간
2026.10.1.~2026.10.10. 17시까지
대상: 재학생
신청방법: 이메일 제출
필수 제출서류: 신청서
행사 일시: 2026.10.15. 14:00~15:00
행사 장소: 글로벌플라자
유의사항: 휴학생 제외
'''

    evidence = notice_generation_evidence(body, title)
    required = notice_required_anchors(evidence)

    assert evidence['cutoff']
    assert evidence['audience'] == '대상: 재학생'
    assert '이메일' in evidence['method']
    assert evidence['event']
    assert evidence['required_documents']
    assert any('휴학생 제외' in line for line in evidence['caveats'])
    assert not required['must_preserve_cutoff']  # event-purpose title prioritizes the event
    assert required['deadline_day'] == '15'
    assert required['event_days'] == ['15']
    assert required['event_times'] == [[14, 0], [15, 0]]
    assert required['place_terms'] == ['글로벌플라자']


def test_generator_payload_is_compact_cleaned_but_segment_original_is_retained():
    body = '''신청기간: 10월 10일 17시까지\n대상: 재학생 (휴학생 제외)\n신청방법: 이메일 contact@example.edu 제출 https://example.invalid/private'''
    title = '학부 프로그램 신청'
    evidence = notice_generation_evidence(body, title)
    segment = dict(kind='notice', title=title, source_text=title + '\n' + body,
                   reference='신청 안내', style_instruction='차분하게',
                   fact_hints=notice_fact_hints(body), generation_evidence=evidence,
                   constraints={'required_source_facts': notice_required_anchors(evidence)})

    payload = _script_payload(segment)

    assert segment['source_text'].endswith(body)
    assert '휴학생 제외' not in payload['source_text']
    assert 'https://example.invalid/private' not in payload['source_text']
    assert 'contact@example.edu' not in repr(payload)
    assert '(' not in payload['source_text']
    assert payload['required_source_facts']['cutoff_times'] == [[17, 0]]
    assert clean_notice_text('지원 안내(학부생·재학생)는 오늘 열려요') == '지원 안내는 오늘 열려요'


def test_notice_gate_rejects_missing_bound_deadline_time_or_submission_details():
    body = '''신청기간: 10월 10일 17시까지
대상: 재학생
신청방법: 이메일 제출
필수 제출서류: 신청서
10월 10일 17시까지 학부사무실로 제출
휴학생 제외'''
    evidence = notice_generation_evidence(body, '학부 프로그램 신청 안내')
    segment = dict(kind='notice', title='학부 프로그램 신청 안내', source_text='full original',
                   generation_evidence=evidence,
                   constraints={'max_chars': 50, 'sentence_count': (1, 2),
                                'required_source_facts': notice_required_anchors(evidence)})

    assert _script_errors('학부 프로그램 신청자는 10월 10일 16시까지 이메일로 신청해요.', segment)
    assert _script_errors('학부 프로그램 신청자는 10월 10일 17시까지 신청해요.', segment)
    assert segment['constraints']['required_source_facts']['submission_place'] == '학부사무실'
    assert segment['constraints']['required_source_facts']['submission_documents']
    assert segment['constraints']['required_source_facts']['caveat_groups']


def test_event_gate_accepts_supported_date_time_place_and_rejects_swapped_facts():
    title = '교직 적성 및 인성검사 시행 안내'
    body = '''검사 인원 및 대상: 270명, 교직과정 이수자
검사 일시: 2026.10.15. 14:00~15:00
검사 장소: 글로벌플라자'''
    evidence = notice_generation_evidence(body, title)
    segment = dict(kind='notice', title=title, source_text=title + '\n' + body,
                   generation_evidence=evidence,
                   constraints={'max_chars': 50, 'sentence_count': (1, 2),
                                'required_source_facts': notice_required_anchors(evidence)})
    correct = '교직과정 이수자는 10월 15일 14시부터 15시까지 글로벌플라자에서 적성·인성검사를 받아요.'
    swapped = '교직과정 이수자는 10월 15일 15시부터 16시까지 다른 장소에서 적성·인성검사를 받아요.'

    assert not _script_errors(correct, segment)
    assert _script_errors(swapped, segment)
