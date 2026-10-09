"""게시된 자료로 대본 3가지만 미리보기. 공개 음성/검수 결과는 덮어쓰지 않는다."""
import argparse
from copy import deepcopy
from pathlib import Path
import random
import tempfile

from briefing.build import ROOT, read_yaml, validate_config
from briefing.content import create_segments
from briefing.slm import Ollama, generate_segments
from collector.store import load_collection_report, save_json


def sample_material(data, channel=None, max_notices=2):
    """원문을 자르지 않고 공지 개수만 줄인다. 학과별 최종 재생목록을 대신하지 않는다."""
    result = deepcopy(data)
    selected, seen, count = [], set(), 0
    for row in result['channels']:
        if channel and row['channel_id'] != channel:
            continue
        notices = []
        for notice in row['notices']:
            key = (notice['url'], notice['title'])
            if key not in seen and count < max_notices:
                notices.append(notice)
                seen.add(key)
                count += 1
        if notices or row['meals']:
            selected.append(dict(row, notices=notices, meals=row['meals'][:1]))
    result['channels'] = selected
    return result


def create_samples(data, catalog, config, events, *, channel=None, provider=None, report_dir=None):
    material = sample_material(data, channel)
    report_dir = Path(report_dir or ROOT / 'preview/morning-reviews')
    variants = list(range(3))
    random.SystemRandom().shuffle(variants)
    drafts = []
    skipped_notices = {}
    provider = provider or Ollama(dict(config['slm'], temperature=0.55))
    # 미리보기는 별도 캐시에서 새로 생성하여 운영 결과와 섞지 않는다.
    with tempfile.TemporaryDirectory() as temporary:
        for index, variant in enumerate(variants, 1):
            segments, _ = create_segments(material, catalog, config, events, variant=variant)
            segments = [s for s in segments if s['kind'] not in {'empty_notices', 'empty_meals'}
                        and (s['kind'] != 'events' or s['events'])]
            if not any(s['kind'] == 'meal' for s in segments):
                segments.insert(-1, dict(id='sample-meals', kind='empty_meals', title='학식 안내',
                    script='오늘 수집 자료에 학식 메뉴가 없어 메뉴 안내는 건너뛸게요.', generation='fixed'))
            folder = Path(temporary) / str(index)
            folder.mkdir()
            print(f'미리보기 {index}/3 대본 생성 중…', flush=True)
            generate_segments(segments, provider, folder, report_dir / f'sample-{index}.json')
            for segment in segments:
                if segment.get('_skip_notice'):
                    skipped_rows = segment['_skip_notice'] if isinstance(segment['_skip_notice'], list) else [segment['_skip_notice']]
                    for skipped in skipped_rows:
                        skipped_notices[skipped['notice_id']] = dict(skipped)
            segments = [s for s in segments if not s.get('_skip_notice')]
            rows = [dict(kind=s['kind'], script=s['script'],
                         title=s['title'], url=s.get('url')) for s in segments]
            drafts.append(dict(number=index, variant=variant, segments=rows, script='\n'.join(r['script'] for r in rows)))
    return dict(date=data['date'], scope='미리보기: 공지 최대 2개, 식당별 메뉴 최대 1개',
                channel=channel, status='partial' if skipped_notices else 'passed',
                skipped_notices=list(skipped_notices.values()), samples=drafts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--channel', help='한 게시판만 미리보기 (생략하면 공지 최대 2개)')
    parser.add_argument('--output', type=Path, default=ROOT / 'preview/morning-samples.json')
    args = parser.parse_args()
    config, events = read_yaml(ROOT / 'config/briefing.yaml'), read_yaml(ROOT / 'config/events.yaml')
    validate_config(config, events)
    result = create_samples(load_collection_report(args.input), read_yaml(ROOT / 'data/channels.yaml'),
                            config, events, channel=args.channel,
                            report_dir=ROOT / 'preview/morning-reviews')
    save_json(result, args.output)
    markdown = f"# {result['date']} 아침 대본 미리보기\n\n{result['scope']}\n"
    for sample in result['samples']:
        markdown += f"\n## 대본 {sample['number']}\n\n{sample['script']}\n"
    args.output.with_suffix('.md').write_text(markdown, encoding='utf-8')
    print(f'미리보기 3개 생성 ({result["status"]}): {args.output.with_suffix(".md")}')


if __name__ == '__main__':
    main()
