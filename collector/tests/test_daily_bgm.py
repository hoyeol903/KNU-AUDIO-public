import hashlib
import json
import pytest
from tools.daily_bgm import export, select_track


def fixture(tmp_path):
    source = tmp_path / 'private'
    briefing = tmp_path / 'site/data/briefing'
    source.mkdir(); briefing.mkdir(parents=True)
    music = b'private original'
    (source / 'yt-01.mp3').write_bytes(music)
    catalog = tmp_path / 'catalog.json'
    catalog.write_text(json.dumps([dict(id='yt-01', file='yt-01.mp3', title='Morning', artist='Artist',
        source_url='https://www.youtube.com/audiolibrary', license='YouTube 오디오 보관함 라이선스',
        license_url='https://support.google.com/youtube/answer/3376882', attribution_required=False,
        sha256=hashlib.sha256(music).hexdigest())]))
    (briefing / 'voice.mp3').write_bytes(b'spoken voice')
    (briefing / 'segments.json').write_text(json.dumps({'segments': [dict(script='학교 소식을 안내합니다.', audio='voice.mp3')]}))
    return dict(output=briefing.parent / 'bgm', source_dir=source, briefing_dir=briefing,
                catalog_path=catalog, day='2026-10-09', require_source=True)


def test_only_mixed_content_is_published_and_cached(tmp_path):
    args = fixture(tmp_path)
    calls = []
    def mixer(voice, music, target):
        calls.append(target); target.write_bytes(voice.read_bytes() + b' mixed ' + music.read_bytes())
    args['output'].mkdir(); (args['output'] / 'old.mp3').write_bytes(b'old original')
    old = args['briefing_dir'] / 'mix-obsolete.mp3'; old.write_bytes(b'obsolete')
    metadata = export(**args, mixer=mixer)
    app = json.loads((args['briefing_dir'] / 'segments.json').read_text())
    assert metadata['status'] == 'ready' and metadata['audio'] is None
    assert app['bgm'] == metadata and app['segments'][0]['audio'] == 'voice.mp3'
    assert (args['briefing_dir'] / app['segments'][0]['audio_bgm']).read_bytes().startswith(b'spoken voice mixed ')
    assert not list(args['output'].glob('*.mp3')) and not old.exists()
    assert (args['briefing_dir'] / 'voice.mp3').read_bytes() == b'spoken voice'
    assert export(**args, mixer=mixer) == metadata and len(calls) == 1


def test_missing_private_source_never_publishes_music(tmp_path):
    args = fixture(tmp_path); (args['source_dir'] / 'yt-01.mp3').unlink()
    with pytest.raises(FileNotFoundError): export(**args)
    args['require_source'] = False
    assert export(**args)['status'] == 'awaiting-private-source'
    assert not list(args['output'].glob('*.mp3'))


@pytest.mark.parametrize('change', ['hash', 'symlink', 'empty-script', 'escape', 'no-voice'])
def test_invalid_input_does_not_replace_briefing(tmp_path, change):
    args = fixture(tmp_path); path = args['briefing_dir'] / 'segments.json'
    if change == 'hash': (args['source_dir'] / 'yt-01.mp3').write_bytes(b'changed')
    elif change == 'symlink':
        original = args['source_dir'] / 'yt-01.mp3'; original.rename(args['source_dir'] / 'original.mp3')
        original.symlink_to(args['source_dir'] / 'original.mp3')
    else:
        app = json.loads(path.read_text())
        if change == 'empty-script': app['segments'][0]['script'] = ''
        if change == 'escape': app['segments'][0]['audio'] = '../voice.mp3'
        if change == 'no-voice': app['segments'] = []
        path.write_text(json.dumps(app))
    before = path.read_bytes()
    with pytest.raises(ValueError): export(**args)
    assert path.read_bytes() == before


def test_invalid_date_and_catalog(tmp_path):
    args = fixture(tmp_path)
    with pytest.raises(ValueError): select_track('2026-99-99', args['catalog_path'])
    catalog = json.loads(args['catalog_path'].read_text()); catalog[0]['attribution_required'] = True
    args['catalog_path'].write_text(json.dumps(catalog))
    with pytest.raises(ValueError): select_track(args['day'], args['catalog_path'])
