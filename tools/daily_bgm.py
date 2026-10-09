"""하루에 한 곡을 정해 정적 앱에 복사한다."""
import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets' / 'bgm'


def export(output=ROOT / 'output/app/data/bgm', *, source_dir=SOURCE, day=None):
    source_dir, output = Path(source_dir), Path(output)
    day = day or datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('date must be YYYY-MM-DD')
    tracks = sorted(source_dir.glob('*.mp3')) if source_dir.exists() else []
    if any(path.is_symlink() or not path.is_file() for path in tracks):
        raise ValueError('BGM source must contain regular, non-symlink MP3 files')
    output.mkdir(parents=True, exist_ok=True)
    selected = None
    catalog = None
    catalog_path = source_dir / 'catalog.json'
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        if not isinstance(catalog, list):
            raise ValueError('BGM catalog must be a list')
        catalog = {entry.get('file'): entry for entry in catalog if isinstance(entry, dict)}
    if tracks:
        digest = hashlib.sha256((day + '\n' + '\n'.join(path.name for path in tracks)).encode()).digest()
        selected = tracks[int.from_bytes(digest, 'big') % len(tracks)]
        content_hash = hashlib.sha256(selected.read_bytes()).hexdigest()
        track = catalog.get(selected.name) if catalog is not None else None
        if catalog is not None and (track is None or track.get('sha256') != content_hash):
            raise ValueError(f'BGM catalog entry missing or hash mismatch: {selected.name}')
        if catalog is not None and (any(not isinstance(track.get(key), str) or not track[key] for key in
                ('title', 'artist', 'source_url', 'license', 'license_url', 'attribution', 'changes', 'isrc')) or
                not track['source_url'].startswith(('http://', 'https://')) or
                not track['license_url'].startswith(('http://', 'https://'))):
            raise ValueError(f'BGM catalog metadata incomplete or URL invalid: {selected.name}')
        filename = content_hash + '.mp3'
        temp = output / (filename + '.tmp')
        shutil.copyfile(selected, temp)
        temp.replace(output / filename)
    metadata = {'date': day, 'audio': filename if selected else None,
                'title': track['title'] if selected and catalog is not None else selected.stem if selected else None,
                'volume': 0.1}
    if selected and catalog is not None:
        metadata.update({key: track[key] for key in ('artist', 'source_url', 'license', 'license_url', 'attribution', 'changes', 'isrc')})
    temp_json = output / 'track.json.tmp'
    temp_json.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temp_json.replace(output / 'track.json')
    for path in output.glob('*.mp3'):
        if path.name != (filename if selected else None):
            path.unlink()
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/app/data/bgm')
    parser.add_argument('--date')
    args = parser.parse_args()
    export(args.output, day=args.date)


if __name__ == '__main__':
    main()
