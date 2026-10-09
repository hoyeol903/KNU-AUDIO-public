"""Download and verify the 30 selected original tracks from Incompetech."""
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from mutagen.mp3 import MP3

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'assets' / 'bgm'
TRACKS = [
    ('Easy Lemon', 'USUAN1200076'), ('Bossa Antigua', 'USUAN1700069'),
    ('Casa Bossa Nova', 'USUAN1600012'), ('Airport Lounge', 'USUAN1100806'),
    ('Friday Morning', 'USUAN1100224'), ('Moonstone', 'USUAN1100145'),
    ('Midsummer Sky', 'USUAN1100158'), ('Luminous Rain', 'USUAN1100169'),
    ('Continue Life', 'USUAN1100282'), ('Sapphire Isle', 'USUAN1100087'),
    ('Daybreak', 'USUAN1100266'), ('White', 'USUAN1100010'),
    ('Meditation Impromptu 01', 'USUAN1100163'),
    ('Meditation Impromptu 02', 'USUAN1100162'),
    ('Meditation Impromptu 03', 'USUAN1100161'),
    ('Comfortable Mystery', 'USUAN1100287'),
    ('Comfortable Mystery 2', 'USUAN1100537'), ('Fresh Air', 'USUAN1500084'),
    ('Summer Day', 'USUAN1200083'), ('Groove Grove', 'USUAN1200054'),
    ('Thinking of You', 'USUAN1100637'),
    ('On the Passing of Time', 'USUAN1100520'), ('Reawakening', 'USUAN1400017'),
    ('Winter Reflections', 'USUAN1100580'), ('Calmant', 'USUAN1100859'),
    ('Awaiting Return', 'USUAN1100318'), ('Starry', 'USUAN1100062'),
    ('Winter Chimes', 'USUAN1100009'), ('Pride', 'USUAN1100106'),
    ('Healing', 'USUAN1200048'),
]
LICENSE = 'https://creativecommons.org/licenses/by/4.0/'


def get(url):
    request = Request(url, headers={'User-Agent': 'KNU-AUDIO/1.0'})
    with urlopen(request, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f'{url}: HTTP {response.status}')
        return response.read(), response.headers.get_content_type()


def duration(path):
    audio = MP3(path)
    if not audio.info.length or audio.info.length < 10 or not audio.info.sample_rate:
        raise ValueError(f'Invalid or undecodable MP3: {path.name}')
    return round(audio.info.length, 3)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    raw, content_type = get('https://incompetech.com/music/royalty-free/pieces.json')
    if content_type != 'application/json':
        raise RuntimeError(f'Unexpected catalog Content-Type: {content_type}')
    pieces = json.loads(raw)
    by_isrc = {piece.get('isrc'): piece for piece in pieces}
    result = []
    time.sleep(1.05)
    for index, (title, isrc) in enumerate(TRACKS):
        piece = by_isrc.get(isrc)
        if not piece or piece.get('title') != title or piece.get('isrc') != isrc:
            raise RuntimeError(f'Official catalog mismatch: {title} ({isrc})')
        source = f'https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc={isrc}'
        download = 'https://incompetech.com/music/royalty-free/mp3-royaltyfree/' + quote(piece['filename'])
        path = DEST / (title + '.mp3')
        temp = path.with_name(path.name + '.tmp')
        if path.exists():
            seconds = duration(path)
            content = path.read_bytes()
        else:
            try:
                content, mime = get(download)
                if mime not in ('audio/mpeg', 'application/octet-stream'):
                    raise RuntimeError(f'{title}: unexpected Content-Type {mime}')
                if not (content.startswith(b'ID3') or (len(content) > 1 and content[0] == 0xff and content[1] & 0xe0 == 0xe0)):
                    raise RuntimeError(f'{title}: MP3 signature missing')
                temp.write_bytes(content)
                seconds = duration(temp)
                os.replace(temp, path)
            except Exception:
                temp.unlink(missing_ok=True)
                raise
        credit = f'"{title}" Kevin MacLeod (incompetech.com) — Licensed under Creative Commons: By Attribution 4.0 License ({LICENSE})'
        result.append({'file': path.name, 'title': title, 'artist': 'Kevin MacLeod',
                       'source_url': source, 'download_url': download, 'isrc': isrc,
                       'license': 'CC BY 4.0', 'license_url': LICENSE,
                       'attribution': credit, 'changes': '없음',
                       'sha256': hashlib.sha256(content).hexdigest(),
                       'duration_sec': seconds})
        print(f'{index + 1}/{len(TRACKS)} {title}: verified {seconds:.1f}s', flush=True)
        if index < len(TRACKS) - 1:
            time.sleep(1.05)
    temp_catalog = DEST / 'catalog.json.tmp'
    temp_catalog.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temp_catalog, DEST / 'catalog.json')
    print(f'Completed {len(result)} tracks ({sum((DEST / row["file"]).stat().st_size for row in result):,} bytes)')


if __name__ == '__main__':
    main()
