from briefing.review import review, revision_feedback
from briefing.slm import fit_length, generate_segments, _script_payload


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
