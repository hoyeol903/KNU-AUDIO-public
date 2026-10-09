import json

from tools.daily_bgm import export


def test_daily_selection_copy_prune_and_empty(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'site' / 'data' / 'bgm'
    source.mkdir()
    (source / 'A.mp3').write_bytes(b'audio-a')
    (source / 'B.mp3').write_bytes(b'audio-b')
    one = export(output, source_dir=source, day='2026-10-06')
    assert export(output, source_dir=source, day='2026-10-06') == one
    assert one['audio'] in [p.name for p in output.glob('*.mp3')]
    assert len(list(output.glob('*.mp3'))) == 1
    (output / 'old.mp3').write_bytes(b'old')
    for path in source.glob('*.mp3'):
        path.unlink()
    empty = export(output, source_dir=source, day='2026-10-07')
    assert empty['audio'] is None
    assert not list(output.glob('*.mp3'))
    assert json.loads((output / 'track.json').read_text()) == empty


def test_rejects_symlinks_and_invalid_dates(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'output'
    source.mkdir()
    (source / 'real.mp3').write_bytes(b'audio')
    (source / 'linked.mp3').symlink_to(source / 'real.mp3')
    try:
        export(output, source_dir=source, day='2026-10-06')
        assert False, 'symlink must be rejected'
    except ValueError:
        pass
    (source / 'linked.mp3').unlink()
    try:
        export(output, source_dir=source, day='2026-99-99')
        assert False, 'invalid calendar date must be rejected'
    except ValueError:
        pass
