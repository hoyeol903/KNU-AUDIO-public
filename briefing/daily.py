"""Hosted workflow helpers: stable daily input, publication verification."""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tempfile

from briefing.qwen_tts import MODE, VOICES
from briefing.build import ROOT, build
from collector.store import SEOUL, load_collection_report, save_daily_items, save_json


def today():
    return datetime.now(SEOUL).date().isoformat()


def validate_input(path, expected):
    data = load_collection_report(path)
    with tempfile.TemporaryDirectory() as td:
        save_daily_items(data, Path(td) / 'validated.json')
    if data['date'] != expected:
        raise ValueError('수집 자료 날짜가 오늘과 다릅니다. 이전 자료를 오늘 것으로 배포하지 않습니다.')
    if not data['channels']:
        raise ValueError('수집 채널이 하나도 없어 배포를 중단합니다.')
    if (data['errors'] and not any(v is not None for v in data['weather'].values())
            and not data['schedule']
            and not any(c['notices'] or c['meals'] for c in data['channels'])):
        raise ValueError('수집 오류가 있고 안내할 자료도 없어 기존 배포를 유지합니다.')
    return data


def collect_day(*, root=ROOT, day=None, all_departments=True, runner=subprocess.run):
    day = day or today()
    path = root / 'data/raw' / day / 'items.json'
    # 일일 수집은 신규 공지 판단 기준을 갱신한다. 재시도에서 다시 수집하면
    # 직전 실행의 신규 공지가 사라질 수 있으므로 저장된 오늘 입력을 재사용한다.
    if path.exists():
        data = validate_input(path, day)
        reused = True
    else:
        command = [sys.executable, '-m', 'briefing.collect']
        if all_departments:
            command.append('--all-supported')
        result = runner(command, cwd=root, check=False)
        if result.returncode not in (0, 1):
            raise RuntimeError(f'수집 프로세스 비정상 종료: {result.returncode}')
        if not path.exists():
            raise RuntimeError('수집 결과 파일이 없습니다. 기존 웹사이트를 유지합니다.')
        data = validate_input(path, day)
        if result.returncode == 1 and not data['errors']:
            raise RuntimeError('수집이 실패했지만 입력에 오류 기록이 없어 배포를 중단합니다.')
        reused = False
    # 식당 미운영/일부 채널 오류는 기존 화면의 수집 상태에 명시한다.
    report = dict(date=day, reused=reused, errors=data['errors'], input=str(path))
    save_json(report, root / 'output/daily-collection.json')
    print(f"{'저장 자료 재사용' if reused else '수집 완료'}: {path}", flush=True)
    if data['errors']:
        print(f"::warning::일부 자료 미수집 {len(data['errors'])}건. 화면에 수집 상태를 표시합니다.")
    return path


def verify_publication(folder, expected):
    from mutagen.mp3 import MP3
    folder = Path(folder).resolve()
    manifest = load_collection_report(folder / 'manifest.json')
    if manifest['date'] != expected or manifest['mode'] != MODE:
        raise ValueError('오늘의 음성 생성 완료본이 아닙니다.')
    if not manifest['segments']:
        raise ValueError('빈 음성 목록입니다.')
    if not manifest['voices'] or set(manifest['voices']) - set(VOICES):
        raise ValueError('알 수 없는 음성 화자이거나 화자가 없습니다.')
    for segment in manifest['segments']:
        if segment.get('generation') == 'slm' and not (segment.get('review', {}).get('passed') or
                segment.get('review', {}).get('status') == 'revision-unchecked'):
            raise ValueError('검수를 통과하지 않은 대본입니다.')
        for voice in manifest['voices']:
            path = (folder / segment['audio'][voice]['url']).resolve()
            if not path.is_relative_to(folder / 'audio') or not path.is_file() or MP3(path).info.length <= 0:
                raise ValueError('유효한 음성 파일이 없습니다.')
    for filename in ('index.html', 'app.mjs', 'continuous-audio.mjs', 'playlist.mjs', 'playback-speed.mjs', 'style.css'):
        if not (folder / filename).is_file():
            raise ValueError(f'재생 화면 파일 누락: {filename}')
    if manifest.get('bgm'):
        path = (folder / manifest['bgm']['path']).resolve()
        if not path.is_relative_to(folder / 'audio') or not path.is_file():
            raise ValueError('배경음악 파일이 없습니다.')
    print(f'배포 검증 완료: {expected}, {len(manifest["segments"])}개 음성')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['collect', 'build', 'verify'])
    parser.add_argument('--default-departments', action='store_true')
    args = parser.parse_args()
    if args.stage == 'collect':
        collect_day(all_departments=not args.default_departments)
    elif args.stage == 'build':
        path = ROOT / 'data/raw' / today() / 'items.json'
        validate_input(path, today())
        build(path)
    else:
        verify_publication(ROOT / 'dist', today())


if __name__ == '__main__':
    main()
