"""Select private YouTube music and publish only speech mixed with music."""
import argparse
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'assets/bgm/catalog.json'
SOURCE = ROOT / '.cache/youtube-bgm/music'
RECIPE = 'youtube-speech-mix-v1-volume-0.1'


def save_json(value, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def select_track(day, catalog_path=CATALOG):
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('date must be YYYY-MM-DD')
    catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    if not isinstance(catalog, list) or not catalog:
        raise ValueError('BGM catalog must be a nonempty list')
    names = set()
    for track in catalog:
        filename = Path(track.get('file', ''))
        if (not filename.name or filename.parent != Path('.') or filename.suffix != '.mp3'
                or filename.name in names or not track.get('title') or not track.get('artist')
                or track.get('license') != 'YouTube 오디오 보관함 라이선스'
                or track.get('attribution_required') is not False
                or len(track.get('sha256', '')) != 64
                or any(c not in '0123456789abcdef' for c in track.get('sha256', ''))):
            raise ValueError('Invalid YouTube BGM catalog entry')
        names.add(filename.name)
    tracks = sorted(catalog, key=lambda row: row['file'])
    digest = hashlib.sha256((day + '\n' + '\n'.join(t['file'] for t in tracks)).encode()).digest()
    return tracks[int.from_bytes(digest, 'big') % len(tracks)]


def safe_audio(directory, filename):
    if not isinstance(filename, str):
        raise ValueError('Speech filename must be a string')
    relative = Path(filename)
    path = Path(directory) / relative
    if (not relative.name or relative.parent != Path('.') or relative.suffix != '.mp3'
            or path.is_symlink() or not path.is_file()):
        raise ValueError('Speech must be a regular local MP3 file')
    return path


def mix_speech(speech, music, target):
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg is required to mix speech with YouTube music')
    temporary = Path(target).with_name(Path(target).stem + '.tmp.mp3')
    try:
        subprocess.run(['ffmpeg', '-y', '-nostdin', '-loglevel', 'error', '-i', str(speech),
                        '-stream_loop', '-1', '-i', str(music), '-filter_complex',
                        '[1:a]volume=0.1[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]',
                        '-map', '[mix]', '-codec:a', 'libmp3lame', '-b:a', '128k', str(temporary)], check=True)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def export(output=ROOT / 'output/app/data/bgm', *, source_dir=None, day=None,
           catalog_path=CATALOG, briefing_dir=None, require_source=False, mixer=mix_speech):
    output = Path(output)
    briefing_dir = Path(briefing_dir) if briefing_dir else output.parent / 'briefing'
    source_dir = Path(source_dir or os.environ.get('KNUA_BGM_SOURCE_DIR') or SOURCE)
    day = day or datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    track = select_track(day, catalog_path)
    music = source_dir / track['file']
    # Raw music must never be copied into the publicly served directory, even on fallback.
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob('*.mp3'):
        old.unlink()
    app_path = briefing_dir / 'segments.json'
    app = json.loads(app_path.read_text(encoding='utf-8')) if app_path.is_file() else None
    if not music.is_file():
        if require_source:
            raise FileNotFoundError('Private YouTube BGM source is missing; no raw-music fallback is allowed')
        existing = app.get('bgm') if app else None
        metadata = existing if existing and existing.get('mode') == 'mixed' else dict(
            date=day, mode='mixed', audio=None, status='awaiting-private-source', title=None)
        save_json(metadata, output / 'track.json')
        return metadata
    if music.is_symlink() or hashlib.sha256(music.read_bytes()).hexdigest() != track['sha256']:
        raise ValueError('Private BGM source hash mismatch or symlink')
    if not app or not app.get('segments'):
        if require_source:
            raise ValueError('Cannot publish music without a spoken briefing')
        metadata = dict(date=day, mode='mixed', audio=None, status='awaiting-speech', title=None)
        save_json(metadata, output / 'track.json')
        return metadata
    metadata = dict(date=day, mode='mixed', audio=None, status='ready', title=track['title'],
                    artist=track['artist'], source_url=track['source_url'], license=track['license'],
                    license_url=track['license_url'], attribution='저작자 표시 필요 없음',
                    changes='크누아 브리핑 음성과 혼합 · 음악 음량 10%', track_id=track['id'], volume=0.1)
    kept = set()
    sources = []
    for segment in app['segments']:
        if not isinstance(segment.get('script'), str) or not segment['script'].strip():
            raise ValueError('BGM requires a nonempty spoken script in every segment')
        sources.append(safe_audio(briefing_dir, segment.get('audio', '')))
    for segment, speech in zip(app['segments'], sources):
        signature = hashlib.sha256(speech.read_bytes()).hexdigest() + '|' + track['sha256'] + '|' + RECIPE
        name = 'mix-' + hashlib.sha256(signature.encode()).hexdigest() + '.mp3'
        target = briefing_dir / name
        if not target.is_file():
            mixer(speech, music, target)
        segment['audio_bgm'] = name
        kept.add(name)
    app['bgm'] = metadata
    save_json(app, app_path)
    save_json(metadata, output / 'track.json')
    for old in briefing_dir.glob('mix-*.mp3'):
        if old.name not in kept:
            old.unlink()
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/app/data/bgm')
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--date')
    parser.add_argument('--require-source', action='store_true')
    args = parser.parse_args()
    export(args.output, source_dir=args.source_dir, day=args.date, require_source=args.require_source)


if __name__ == '__main__':
    main()
