import json
from pathlib import Path
from tools.daily_bgm import select_track


def test_public_catalog_has_30_no_attribution_tracks_without_raw_music():
    root = Path(__file__).resolve().parents[2]
    catalog = root / 'assets/bgm/catalog.json'
    rows = json.loads(catalog.read_text())
    assert len(rows) == 30
    assert len({row['file'] for row in rows}) == 30
    assert all(row['attribution_required'] is False and row['distribution'] == 'speech-mix-only' for row in rows)
    assert all(row['mood'] == '밝음' and row['duration_sec'] > 0 for row in rows)
    assert not list(catalog.parent.glob('*.mp3'))
    chosen = select_track('2026-10-09', catalog)
    assert chosen == select_track('2026-10-09', catalog)
    assert chosen in rows
