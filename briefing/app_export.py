"""python -m briefing.app_export: 생성한 브리핑(dist/)을 앱 화면이 읽는 자리와 형식으로 옮긴다.

앱(tools/knua-app.html)은 output/app/data/briefing/segments.json 한 장을 읽고, 구간을
intro → 오늘 소식이 있는 내 게시판(하나도 없으면 empty) → 내 식당 → outro 순서로 이어 재생한다. 구간 하나에 음성 파일은 하나다.
공지는 공지별 파일을 공유하고 식단과 공통 안내는 필요한 단위로 묶는다. 이전 게시판별 출력도 지원한다.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

from collector.store import load_collection_report, save_json

ROOT = Path(__file__).resolve().parents[1]


def ffmpeg_concat(sources, target):
    """같은 설정으로 만든 MP3를 다시 인코딩하지 않고 잇는다."""
    if not shutil.which('ffmpeg'):
        raise RuntimeError('한 게시판에 공지가 여러 개면 음성을 이어 붙여야 합니다. FFmpeg를 설치하세요.')
    with tempfile.TemporaryDirectory() as folder:
        listing = Path(folder) / 'parts.txt'
        listing.write_text(''.join(f"file '{Path(source).resolve()}'\n" for source in sources), encoding='utf-8')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                        '-c', 'copy', str(target)], check=True)


def app_segments(manifest, items, voice):
    """앱 구간 목록. 각 구간의 parts는 이어 붙일 음성 주소다. 못 찾은 공지가 있으면 조용히 빼지 않고 멈춘다."""
    if voice not in manifest['voices']:
        raise ValueError(f'없는 목소리: {voice}')
    source = manifest['segments']
    skipped = manifest.get('skipped_notices', [])
    failures = {f['segment_id']: f for f in manifest.get('audio_failures', [])}
    names = {channel['id']: channel['name'] for channel in manifest['channels']}

    def merged(segment_id, title, parts, cards):
        cues, elapsed = [], 0
        for part in parts:
            end = elapsed + part['audio'][voice]['duration_sec']
            cues.append(dict(text=part['script'], start_sec=round(elapsed, 3), end_sec=round(end, 3)))
            elapsed = end
        return dict(id=segment_id, channel_id=segment_id, title=title, script=' '.join(part['script'] for part in parts),
                    duration_sec=round(elapsed, 3), cues=cues,
                    parts=[part['audio'][voice]['url'] for part in parts], items=cards)

    def card(section, title, detail, url=None, post_id=None):
        # 남은 일수는 화면이 오늘 날짜로 계산하므로 싣지 않는다.
        return dict(section=section, title=title, detail=detail, url=url, dday=None, postId=post_id)

    weather = items['weather']
    intro = [s for s in source if s['kind'] in {'greeting', 'weather'}] + [s for s in source if s['kind'] == 'events' and s.get('events')]
    result = []
    if intro:
        result += [merged('intro', '인사·날씨', intro, [] if weather['summary'] is None else [card(
        '날씨', weather['summary'], f"최저 {weather['temp_min']}° / 최고 {weather['temp_max']}° · 비 올 확률 {weather['rain_prob']}%")])]
    # 새 형식은 공지별 음성을 공유한다. 옛 manifest는 게시판 단위로 내보내 호환한다.
    individual = any(s.get('notice_refs') for s in source if s['kind'] == 'notice')
    emitted = set()
    for channel in items['channels']:
        channel_id, name = channel['channel_id'], names.get(channel['channel_id'], channel['channel_id'])
        parts, cards = [], []
        for notice in channel['notices']:
            found = [s for s in source if s['kind'] == 'notice' and channel_id in s['channel_ids']
                     and (any(r['channel_id'] == channel_id and r['postId'] == notice['id'] and r['url'] == notice['url'] and r['title'] == notice['title'] for r in s.get('notice_refs', []))
                          if s.get('notice_refs') else s['url'] == notice['url'] and s['title'] == notice['title'])]
            if len(found) != 1:
                declared = [s for s in skipped if s.get('notice_id') == notice['id']
                            and channel_id in s.get('channel_ids', [])
                            and s.get('url') == notice['url'] and s.get('title') == notice['title']]
                if not found and len(declared) == 1:
                    continue
                raise ValueError(f"{name}: 공지의 음성 구간을 찾지 못했습니다: {notice['title']}")
            if individual:
                part = found[0]
                if part['id'] not in emitted:
                    refs = part['notice_refs']
                    shared_cards = []
                    for ref in refs:
                        section = '마감 임박' if ref['reason'] == 'reminder' and part.get('deadline_verified') else '소식'
                        entry = card(section, ref['title'], names.get(ref['channel_id'], ref['channel_id']) +
                                     (' · ' + ref['posted_at'] if ref['posted_at'] else ''), ref['url'], ref['postId'])
                        entry['channel_id'] = ref['channel_id']
                        shared_cards.append(entry)
                    row = merged(part['id'], part['title'], [part], shared_cards)
                    row.update(kind='notice', channel_ids=part['channel_ids'], notice_refs=refs)
                    result.append(row)
                    emitted.add(part['id'])
                continue
            parts.append(found[0])
            section = '마감 임박' if notice['reason'] == 'reminder' and found[0].get('deadline_verified') else '소식'
            cards.append(card(section, notice['title'],
                              name + (' · ' + notice['posted_at'] if notice['posted_at'] else ''), notice['url'], notice['id']))
        if parts:
            result.append(merged(channel_id, name + ' 소식', parts, cards))
        if channel['meals']:
            meals = [s for s in source if s['kind'] == 'meal' and s['channel_ids'] == [channel_id]]
            lost = [f for f in failures.values() if f['kind'] == 'meal' and f['channel_ids'] == [channel_id]]
            if len(meals) + len(lost) != len(channel['meals']):
                raise ValueError(f'{name}: 식단의 음성 구간 수가 자료와 다릅니다')
            if meals:
                result.append(merged(channel_id, name, meals, [card('학식', name, s['script']) for s in meals] if lost else [card('학식', name, ' · '.join(channel['meals'][0]['menu']))]))
    # 내 게시판에 오늘 소식이 하나도 없는 사람에게 앱이 대신 들려주는 구간.
    for sid, title, kind in [('empty', '공지 안내', 'empty_notices'), ('outro', '마무리', 'outro')]:
        parts = [s for s in source if s['kind'] == kind]
        if parts:
            result.append(merged(sid, title, parts, []))
    return result


def export(dist=ROOT / 'dist', output=ROOT / 'output/app/data/briefing', *, voice='female', items_path=None, concat=ffmpeg_concat):
    dist, output = Path(dist), Path(output)
    manifest = load_collection_report(dist / 'manifest.json')
    if not all(manifest['voices'][v]['ready'] for v in manifest['voices']):
        raise ValueError('음성이 없는 대본 미리보기입니다. 음성 생성을 마친 dist를 지정하세요.')
    items = load_collection_report(items_path or ROOT / 'data/raw' / manifest['date'] / 'items.json')
    if items['date'] != manifest['date']:
        raise ValueError('브리핑과 수집 자료의 날짜가 다릅니다')
    segments = app_segments(manifest, items, voice)
    output.mkdir(parents=True, exist_ok=True)
    kept = set()
    for segment in segments:
        parts = [dist / url for url in segment.pop('parts')]
        if not parts:
            raise ValueError(f"{segment['title']}: 음성이 없습니다")
        # 파일 이름은 내용에서 정해 같은 구간은 다시 만들지 않는다.
        name = parts[0].name if len(parts) == 1 else hashlib.sha256('|'.join(p.name for p in parts).encode()).hexdigest() + parts[0].suffix
        target = output / name
        if not target.exists():
            temporary = output / (name + '.tmp' + parts[0].suffix)
            shutil.copyfile(parts[0], temporary) if len(parts) == 1 else concat(parts, temporary)
            temporary.replace(target)
        segment['audio'] = name
        kept.add(name)
    # 화면은 segments.json을 마지막에 바꿔야 새 음성과 함께 본다. 지난 음성은 그 뒤에 지운다.
    save_json(dict(date=manifest['date'], voice=manifest['voices'][voice]['name'], segments=segments), output / 'segments.json')
    for path in output.iterdir():
        if path.is_file() and path.name not in kept and path.name != 'segments.json':
            path.unlink()
    print(f"앱용 브리핑 내보냄: {output} · {manifest['date']} · 구간 {len(segments)}개")
    return segments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/app/data/briefing')
    parser.add_argument('--voice', default='female', help='앱은 한 목소리만 쓴다 (female 또는 male)')
    args = parser.parse_args()
    try:
        export(args.dist, args.output, voice=args.voice)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
