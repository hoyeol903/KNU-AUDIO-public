import json

import pytest

from briefing import app_export


def audio(name, sec):
    return dict(female=dict(url='audio/f-' + name + '.mp3', duration_sec=sec), male=dict(url='audio/m-' + name + '.mp3', duration_sec=sec))


def segment(kind, title, script, name, sec, channels=(), **extra):
    return dict(kind=kind, title=title, script=script, channel_ids=list(channels), audio=audio(name, sec), **extra)


def sample(tmp_path):
    notice = lambda n, reason: dict(id='board:' + n, channel_id='ch-a', source='A', title='★[공통] 공지 ' + n, url='https://example.com/' + n,
                                    posted_at='2026-10-01', deadline=None, dday=None, body='본문', reason=reason)
    items = dict(date='2026-10-01', collected_at='2026-10-01T05:00:00+09:00',
                 weather=dict(summary='맑음', temp_min=11.1, temp_max=22.7, rain_prob=1), schedule=[], errors=[],
                 channels=[dict(channel_id='ch-a', notices=[notice('1', 'new'), notice('2', 'reminder')], meals=[]),
                           dict(channel_id='ch-quiet', notices=[], meals=[]),
                           dict(channel_id='meal-46', notices=[], meals=[dict(place='식당', time=None, menu=['육개장', '김치'])])])
    segments = [segment('greeting', '아침 인사', '안녕하세요.', 'hi', 2), segment('weather', '날씨', '맑아요.', 'w', 3),
                segment('notice', '★[공통] 공지 1', '첫 공지.', 'n1', 4, ['ch-a'], url='https://example.com/1'),
                segment('notice', '★[공통] 공지 2', '둘째 공지.', 'n2', 5, ['ch-a'], url='https://example.com/2'),
                segment('meal', '식당', '육개장.', 'meal', 6, ['meal-46']),
                segment('empty_notices', '공지 안내', '없어요.', 'e', 1), segment('events', '일정', '없어요.', 'ev', 1),
                segment('outro', '마무리 인사', '좋은 하루.', 'bye', 2)]
    manifest = dict(date='2026-10-01', voices=dict(female=dict(name='여자', ready=True), male=dict(name='남자', ready=True)),
                    channels=[dict(id='ch-a', name='가학과 · 공지사항'), dict(id='meal-46', name='GP감꽃 식당')], segments=segments)
    dist = tmp_path / 'dist'
    (dist / 'audio').mkdir(parents=True)
    for row in segments:
        for voice in row['audio'].values():
            (dist / voice['url']).write_bytes(voice['url'].encode())
    (dist / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    path = tmp_path / 'items.json'
    path.write_text(json.dumps(items), encoding='utf-8')
    return dist, path, manifest, items


def test_groups_segments_the_way_the_app_plays_them(tmp_path):
    dist, items_path, manifest, items = sample(tmp_path)
    joined = []
    def concat(parts, target):
        joined.append([p.name for p in parts]); target.write_bytes(b'+'.join(p.read_bytes() for p in parts))
    output = tmp_path / 'briefing'
    output.mkdir()
    (output / 'old.mp3').write_bytes(b'yesterday')
    app_export.export(dist, output, items_path=items_path, concat=concat)

    data = json.loads((output / 'segments.json').read_text())
    rows = data['segments']
    assert data['date'] == '2026-10-01'
    assert [row['channel_id'] for row in rows] == ['intro', 'ch-a', 'meal-46', 'empty', 'outro']  # 소식 없는 채널의 구간은 없다
    assert [row['duration_sec'] for row in rows] == [5, 9, 6, 1, 2]
    assert rows[3]['script'] == '없어요.' and rows[3]['items'] == []
    assert rows[0]['script'] == '안녕하세요. 맑아요.' and rows[0]['items'][0]['section'] == '날씨'
    assert rows[1]['title'] == '가학과 · 공지사항 소식'
    assert rows[1]['cues'] == [dict(text='첫 공지.', start_sec=0, end_sec=4), dict(text='둘째 공지.', start_sec=4, end_sec=9)]
    assert all(' '.join(cue['text'] for cue in row['cues']) == row['script'] for row in rows)
    assert all(row['cues'][-1]['end_sec'] == row['duration_sec'] for row in rows)
    assert [(c['section'], c['title'], c['postId'], c['dday']) for c in rows[1]['items']] == [
        ('소식', '★[공통] 공지 1', 'board:1', None), ('소식', '★[공통] 공지 2', 'board:2', None)]
    manifest['segments'][3]['deadline_verified'] = True
    assert app_export.app_segments(manifest, items, 'female')[1]['items'][1]['section'] == '마감 임박'
    assert rows[2]['items'][0]['detail'] == '육개장 · 김치'
    assert joined == [['f-hi.mp3', 'f-w.mp3'], ['f-n1.mp3', 'f-n2.mp3']]  # 한 구간에 음성이 여럿일 때만 잇는다
    assert rows[2]['audio'] == 'f-meal.mp3' and (output / 'f-meal.mp3').read_bytes() == b'audio/f-meal.mp3'
    assert all((output / row['audio']).is_file() for row in rows)
    assert not (output / 'old.mp3').exists() and len(list(output.iterdir())) == 6


def test_missing_notice_audio_or_other_date_stops_export(tmp_path):
    dist, items_path, manifest, items = sample(tmp_path)
    manifest['segments'] = [s for s in manifest['segments'] if s['title'] != '★[공통] 공지 2']
    with pytest.raises(ValueError, match='찾지 못했'):
        app_export.app_segments(manifest, items, 'female')
    with pytest.raises(ValueError, match='없는 목소리'):
        app_export.app_segments(manifest, items, 'child')
    items['date'] = '2026-10-02'
    items_path.write_text(json.dumps(items), encoding='utf-8')
    with pytest.raises(ValueError, match='날짜'):
        app_export.export(dist, tmp_path / 'out', items_path=items_path)
    assert not (tmp_path / 'out').exists()


def test_declared_skips_only_matching_notice_and_all_skipped_keeps_fallback(tmp_path):
    _, _, manifest, items = sample(tmp_path)
    manifest['segments'] = [s for s in manifest['segments'] if s['title'] != '★[공통] 공지 2']
    manifest['skipped_notices'] = [dict(notice_id='board:2', title='★[공통] 공지 2',
                                        url='https://example.com/2', channel_ids=['ch-a'])]
    rows = app_export.app_segments(manifest, items, 'female')
    board = next(row for row in rows if row['channel_id'] == 'ch-a')
    assert [card['postId'] for card in board['items']] == ['board:1']
    manifest['skipped_notices'].append(dict(notice_id='board:1', title='★[공통] 공지 1',
                                            url='https://example.com/1', channel_ids=['ch-a']))
    manifest['segments'] = [s for s in manifest['segments'] if s['kind'] != 'notice']
    rows = app_export.app_segments(manifest, items, 'female')
    assert all(row['channel_id'] != 'ch-a' for row in rows)
    assert {'empty', 'outro'} <= {row['channel_id'] for row in rows}
    manifest['skipped_notices'][0]['url'] = 'https://wrong.example/2'
    with pytest.raises(ValueError, match='찾지 못했'):
        app_export.app_segments(manifest, items, 'female')


def test_personal_greeting_is_separate_and_legacy_intro_is_preserved(tmp_path):
    _, _, manifest, items = sample(tmp_path)
    manifest['segments'][0]['personal_template'] = '안녕하세요, {name}님. 좋은 아침이에요!'
    rows = app_export.app_segments(manifest, items, 'female')
    assert [r['id'] for r in rows[:2]] == ['greeting', 'intro']
    assert rows[0]['personal_template'] == '안녕하세요, {name}님. 좋은 아침이에요!'
    assert rows[0]['parts'] == ['audio/f-hi.mp3']  # 기기 음성이 없으면 기본 인사를 재생
    assert rows[1]['script'] == '맑아요.'
    assert rows[1]['parts'] == ['audio/f-w.mp3']  # 두 번 인사하지 않는다
