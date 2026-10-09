from briefing.review import review, revision_feedback
from briefing.content import NOTICE_STYLES, daily_variant
from briefing.slm import Ollama, fit_length, generate_segments, normalize_notice_endings, _script_payload


def notice(limit=40, **extra):
    return dict(id='n', kind='notice', title='장학금 신청', source_text='장학금 신청\n10월 12일까지 신청', reference='장학금 신청',
                generation='slm', constraints=dict(max_chars=limit, **extra))


def test_review_rejects_scripts_over_the_notice_limit_only():
    long = '장학금 신청은 십이일까지예요. ' * 5
    assert any('40자' in error for error in review(long, notice()))
    assert not review('장학금 신청이 열렸어요.', notice())
    assert not review(long, notice(feedback_only=True))
    assert not review(long, dict(notice(), constraints={}))


def test_model_is_told_the_limit_and_how_to_shorten():
    assert _script_payload(notice())['max_chars'] == 40
    assert 'max_chars' not in _script_payload(dict(notice(), constraints={}))
    issue = revision_feedback('가' * 80, notice())['issues'][0]
    assert issue['kind'] == '길이' and '40자' in issue['instruction']


def test_fit_length_keeps_leading_sentences_or_falls_back_to_title():
    assert fit_length('신청이 열렸어요. 마감은 곧이에요. ' + '자세한 내용은 길어요. ' * 5, notice()) == '신청이 열렸어요. 마감은 곧이에요. 자세한 내용은 길어요.'
    assert fit_length('가' * 80 + '.', notice()) == '장학금 신청 공지가 올라왔어요.'
    assert fit_length('짧아요.', notice()) == '짧아요.'


def test_long_first_draft_is_revised_then_trimmed(tmp_path):
    class Provider:
        calls = []
        def identity(self): return 'test:1'
        def generate(self, payload, errors):
            self.calls.append((payload, errors))
            return '장학금 신청이 열렸어요. ' + '설명이 계속 이어져요. ' * 10
    provider = Provider()
    result = generate_segments([notice()], provider, tmp_path, tmp_path / 'review.json')
    assert len(provider.calls) == 2 and any('40자' in e for e in provider.calls[1][1])
    assert provider.calls[1][0]['revision']['issues'][0]['kind'] == '길이'
    assert len(result[0]['script']) <= 40 and result[0]['script'].startswith('장학금 신청이 열렸어요.')


def test_formal_sentence_endings_become_haeyo_only_at_sentence_ends():
    script, changes = normalize_notice_endings('설명회가 개최됩니다. 신청은 10월 12일까지 가능합니다')
    assert script == '설명회가 개최돼요. 신청은 10월 12일까지 가능해요' and len(changes) == 2
    for formal, casual in [('특강이 있습니다.', '특강이 있어요.'), ('마감은 10월 12일까지입니다.', '마감은 10월 12일까지예요.'),
                           ('학부생 대상 모집입니다.', '학부생 대상 모집이에요.'), ('바깥바람을 쐬는 것도 좋습니다.', '바깥바람을 쐬는 것도 좋아요.'),
                           ('서류를 준비해 주시기 바랍니다.', '서류를 준비해 주시기 바라요.'), ('행사가 열립니다!', '행사가 열려요!')]:
        assert normalize_notice_endings(formal)[0] == casual
    # 문장 중간, 한글이 아닌 글자 뒤의 "입니다", 목록에 없는 어미는 그대로 둔다.
    for kept in ('진행됩니다만 일정은 바뀔 수 있어요.', '신청은 KNUCUBE입니다.', '결과가 나옵니다.'):
        assert normalize_notice_endings(kept)[0] == kept


def test_generated_notice_is_normalized_before_review_and_reported(tmp_path):
    class Provider:
        def identity(self): return 'test:1'
        def generate(self, payload, errors): return '장학금 신청이 진행됩니다.'
    result = generate_segments([notice()], Provider(), tmp_path, tmp_path / 'review.json')
    assert result[0]['script'] == '장학금 신청이 진행돼요.'
    import json
    assert json.loads((tmp_path / 'review.json').read_text())['segments'][0]['ending_normalizations'] == ['됩니다→돼요']


def test_notice_style_rotates_daily_and_reaches_the_model():
    assert [daily_variant(day) for day in ('2026-10-09', '2026-10-10', '2026-10-11', '2026-10-12')] in (
        [0, 1, 2, 0], [1, 2, 0, 1], [2, 0, 1, 2])
    assert daily_variant('2026-10-09') == daily_variant('2026-10-09')
    assert _script_payload(dict(notice(), style_instruction=NOTICE_STYLES[1]))['style_instruction'] == NOTICE_STYLES[1]
    assert 'style_instruction' not in _script_payload(notice())


def test_prompt_states_the_character_limit_as_a_number():
    sent = {}
    class Session:
        def post(self, url, json, timeout):
            sent.update(json)
            class Response:
                def raise_for_status(self): pass
                def json(self): return dict(done=True, response='{"script": "장학금 신청이 열렸어요."}')
            return Response()
    client = Ollama(dict(model='m'), session=Session())
    client.generate(_script_payload(notice(140)), [])
    assert sent['prompt'].startswith('대본은 공백 포함 140자 이내로 쓰세요.') and sent['prompt'].rstrip().endswith('140자 이내여야 합니다.')
    client.generate(_script_payload(dict(notice(), constraints={})), [])
    assert '자 이내' not in sent['prompt']


def test_extension_numbers_are_contacts_but_year_ranges_are_not():
    from briefing.review import redact
    assert any('연락처' in error for error in review('논문을 제출하세요. 문의: 950-2237', dict(notice(200), source_text='문의 950-2237')))
    assert '950-2237' not in redact('문의: 950-2237, 053)950-6742')
    assert not review('2026-2027 겨울 프로그램이 열려요.', dict(notice(200), source_text='2026-2027 겨울 프로그램'))
    assert '2026-2027' in redact('2026-2027 겨울 프로그램')

