"""필수 KNU CMS 목록·대표 상세 1건 검증. 공지 DB에는 저장하지 않는다."""
from datetime import datetime
from pathlib import Path
import time

import yaml

from collector.http import Client, FetchError
from collector.knu_cms import ParseError, parse_list, parse_detail, next_page, to_notice
from collector.run import ROOT, board_id_for
from collector.store import SEOUL, save_collection_report
from collector.privacy import redact_text

FIXTURES = ROOT / 'collector/tests/fixtures/knu-cms/expansion'


def main():
    stamp = datetime.now(SEOUL).strftime('%Y%m%dT%H%M%S%f')
    report_path = ROOT / 'data/runs' / (stamp + '-knu-cms-validation.json')
    folder = FIXTURES / stamp
    channels = yaml.safe_load((ROOT / 'data/channels.yaml').read_text(encoding='utf-8'))
    targets = [c for c in channels if c['template'] == 'knu-cms' and c['classification'] == 'required' and c['collection_enabled']]
    report = dict(started_at=datetime.now(SEOUL).isoformat(), channels=[], request_count=0)
    folder.mkdir(parents=True, exist_ok=True)
    # 한 연결만 사용. 별칭 호스트도 같은 서버일 수 있어 모든 요청 사이 1초를 보장한다.
    with Client() as client:
        for index, channel in enumerate(targets, 1):
            entry = dict(channel_id=channel['id'], name=channel['name'], source_url=channel['source_url'],
                         status='failed', errors=[], files={})
            try:
                board = board_id_for(channel)
                time.sleep(1)
                html, url = client.get(channel['source_url'])
                file = folder / (channel['id'] + '-list.html')
                file.write_text(redact_text(html), encoding='utf-8')
                entry['files']['list'] = dict(path=str(file.relative_to(ROOT)), url=url)
                items = parse_list(html, url)
                entry.update(source_board_id=board, listed=len(items), next_url=next_page(html, url) if items else None)
                if items:
                    # 가장 최근 날짜가 확인된 글. 고정된 오래된 글만 검증하는 것을 피한다.
                    item = max(items, key=lambda item: item['posted_at'] or '')
                    time.sleep(1)
                    html, url = client.get(item['url'])
                    file = folder / (channel['id'] + '-detail.html')
                    file.write_text(redact_text(html), encoding='utf-8')
                    entry['files']['detail'] = dict(path=str(file.relative_to(ROOT)), url=url)
                    detail = parse_detail(html, url)
                    to_notice(item, detail, board_id=board, channel_ids=[channel['id']])
                    entry.update(status='verified', sample_post_id=detail['source_post_id'], body_status=detail['body_status'])
                else:
                    entry['status'] = 'empty'
            except (FetchError, ParseError, ValueError) as exc:
                entry['errors'].append(str(exc))
            entry['checked_at'] = datetime.now(SEOUL).isoformat()
            report['channels'].append(entry)
            report['request_count'] = client.request_count
            save_collection_report(report, report_path)
            print(f"{index}/{len(targets)} {entry['status']} {entry['name']} {'; '.join(entry['errors'])}", flush=True)
    report['finished_at'] = datetime.now(SEOUL).isoformat()
    save_collection_report(report, report_path)
    save_collection_report(report, ROOT / 'data/knu-cms-validation.json')
    save_collection_report(report, FIXTURES / 'metadata.json')


if __name__ == '__main__':
    main()
