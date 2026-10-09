"""검증된 학과 채널 전체 수집 연결. 기존 수집기 CLI/저장 규칙을 그대로 사용한다."""
import argparse
import subprocess
import sys
from briefing.build import ROOT, read_yaml
from collector.run import select_channels
from collector.store import load_collection_report


def supported_ids():
    catalog = read_yaml(ROOT / 'data/channels.yaml')
    validation = load_collection_report(ROOT / 'data/knu-cms-validation.json')
    supported, excluded = [], []
    for channel in catalog:
        if channel['type'] != 'notice' or channel.get('classification') != 'required':
            continue
        try:
            select_channels(catalog, requested=[channel['id']], validation=validation)
        except ValueError:
            excluded.append(channel['id'])
        else:
            supported.append(channel['id'])
    return supported, excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-supported', action='store_true')
    parser.add_argument('--skip-meals', action='store_true')
    parser.add_argument('--list-only', action='store_true')
    args = parser.parse_args()
    command = [sys.executable, '-m', 'collector.run', '--write-items', '--collect-extras']
    if args.all_supported:
        supported, excluded = supported_ids()
        if not supported:
            parser.error('검증된 수집 채널이 없습니다')
        print(f'검증된 채널 {len(supported)}개. 제외된 미지원 채널: {excluded}', flush=True)
        for cid in supported:
            command.extend(['--channel-id', cid])
    if args.skip_meals:
        command.append('--skip-meals')
    if args.list_only:
        return 0
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
