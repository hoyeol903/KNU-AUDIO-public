from briefing.build import ROOT, read_yaml
from briefing.content import weather_script, create_segments
from briefing.review import review
from briefing.samples import create_samples
from collector.store import load_collection_report


def test_weather_advice_stays_grounded_without_speaking_numbers():
    config = read_yaml(ROOT / 'config/briefing.yaml')
    for weather in [dict(summary='맑음', temp_min=11, temp_max=23, rain_prob=0),
                    dict(summary='비', temp_min=20, temp_max=24, rain_prob=80),
                    dict(summary=None, temp_min=None, temp_max=None, rain_prob=None)]:
        script = weather_script(weather, config)
        segment = dict(kind='weather', required=[script], reference=script, source_text=script,
                       constraints=dict(max_chars=240, feedback_only=True))
        assert not review(script, segment)
        assert review(script + ' 최고 기온은 23도예요.', segment)
        assert not review(script + ' 오후에는 피크닉을 즐겨 보세요.', segment)  # 문맥 타당성은 판정하지 않는다.
        if weather['summary'] == '비':
            assert '우산' in script and '산책' not in script
        elif weather['summary'] == '맑음':
            assert '겉옷' in script and '일교차' in script and '바깥바람' in script


def test_weather_recommendations_use_calm_preferred_phrasing():
    config = read_yaml(ROOT / 'config/briefing.yaml')
    weather = dict(summary='맑음', temp_min=12.8, temp_max=22.6, rain_prob=0)
    scripts = [weather_script(weather, config, variant) for variant in range(3)]
    assert all('좋겠어요' not in script and '편하겠어요' not in script for script in scripts)
    assert all('좋을 것 같아요' in script for script in scripts)
    assert scripts[0] == '아침엔 선선하니 얇은 겉옷 하나 챙기세요. 낮엔 바깥바람 쐬기 좋을 것 같아요.'
    assert scripts[0].count('좋을 것 같아요') == 1


def test_three_preview_styles_keep_truth_and_do_not_call_tts(tmp_path):
    config = read_yaml(ROOT / 'config/briefing.yaml')
    data = load_collection_report(ROOT / 'data/raw/2026-10-06/items.json')
    class Fake:
        def identity(self): return 'fake'
        def generate(self, payload, errors):
            return payload['reference'] + (' 안내예요.' if payload['kind'] == 'notice' else '')
    result = create_samples(data, [], config, [], provider=Fake(), report_dir=tmp_path / 'reports')
    assert len(result['samples']) == 3 and result['date'] == data['date']
    greetings, endings = set(), set()
    for draft in result['samples']:
        rows = draft['segments']
        assert rows[0]['script'] == config['greeting']
        assert '{name}' not in draft['script']
        assert '함께해 주셔서 고마워' not in draft['script']
        greetings.add(rows[0]['script']); endings.add(rows[-1]['script'])
    assert greetings == {config['greeting']}
    assert endings == {'오늘도 좋은 하루 보내세요!'}
    # 운영 생성은 같은 날 같은 변형으로 캐시를 재사용한다.
    first = create_segments(data, [], config, [])[0]
    second = create_segments(data, [], config, [])[0]
    assert [s['script'] for s in first] == [s['script'] for s in second]


def test_preview_keeps_unchecked_revised_notice(tmp_path):
    config = read_yaml(ROOT / 'config/briefing.yaml')
    data = load_collection_report(ROOT / 'data/raw/2026-10-06/items.json')
    class OneBad:
        def identity(self): return 'fake'
        def generate(self, payload, errors):
            if payload['kind'] == 'notice': return '원문에 없는 999999원입니다.'
            return '오늘의 안내입니다.'
    result = create_samples(data, [], config, [], provider=OneBad(), report_dir=tmp_path / 'reports')
    assert result['status'] == 'passed' and not result['skipped_notices']
    assert any(row['kind'] == 'notice' and row['script'] == '원문에 없는 999999원입니다.' for sample in result['samples'] for row in sample['segments'])
