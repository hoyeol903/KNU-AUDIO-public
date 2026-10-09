from briefing.review import review, revision_feedback
from briefing.content import NOTICE_STYLES, daily_variant
from briefing.slm import fit_length, generate_segments, normalize_notice_endings, _script_payload


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


def test_formal_sentence_endings_become_haeyo_only_at_sentence_ends_of_notices():
    script, changes = normalize_notice_endings('설명회가 개최됩니다. 신청은 10월 12일까지 가능합니다', notice())
    assert script == '설명회가 개최돼요. 신청은 10월 12일까지 가능해요' and len(changes) == 2
    # 문장 중간, 명사형 종결, 공지가 아닌 구간은 그대로 둔다.
    assert normalize_notice_endings('진행됩니다만 일정은 바뀔 수 있어요.', notice())[0] == '진행됩니다만 일정은 바뀔 수 있어요.'
    assert normalize_notice_endings('행사 안내입니다.', notice())[0] == '행사 안내입니다.'
    assert normalize_notice_endings('행사가 열립니다.', dict(notice(), kind='weather'))[0] == '행사가 열립니다.'


def test_generated_notice_is_normalized_before_review_and_reported(tmp_path):
    class Provider:
        def identity(self): return 'test:1'
        def generate(self, payload, errors): return '장학금 신청이 진행됩니다.'
    result = generate_segments([notice()], Provider(), tmp_path, tmp_path / 'review.json')
    assert result[0]['script'] == '장학금 신청이 진행돼요.'
    import json
    assert json.loads((tmp_path / 'review.json').read_text())['segments'][0]['ending_normalizations'] == ['진행됩니다→진행돼요']


def test_notice_style_rotates_daily_and_reaches_the_model():
    assert [daily_variant(day) for day in ('2026-10-09', '2026-10-10', '2026-10-11', '2026-10-12')] in (
        [0, 1, 2, 0], [1, 2, 0, 1], [2, 0, 1, 2])
    assert daily_variant('2026-10-09') == daily_variant('2026-10-09')
    assert _script_payload(dict(notice(), style_instruction=NOTICE_STYLES[1]))['style_instruction'] == NOTICE_STYLES[1]
    assert 'style_instruction' not in _script_payload(notice())

