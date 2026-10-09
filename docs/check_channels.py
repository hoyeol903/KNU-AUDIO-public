"""채널 검토 산출물을 인터넷 없이 확인: python docs/check_channels.py"""
import json
from pathlib import Path
import yaml

root = Path(__file__).resolve().parents[1]
orgs = yaml.safe_load((root / 'data/departments.yaml').read_text())
channels = yaml.safe_load((root / 'data/channels.yaml').read_text())
org_by_id = {org['id']: org for org in orgs}
dept_ids = {org['id'] for org in orgs if org['kind'] == 'department'}
assert len(channels) == len({c['id'] for c in channels}), '채널 ID 중복'
for c in channels:
    assert set(c['organization_ids']) <= org_by_id.keys(), c['id']
    assert set(c['required_department_ids']) <= dept_ids, c['id']
    assert c['status'] in {'found', 'missing', 'unreachable', 'needs-check'}, c['id']
    if isinstance(c['required'], list):
        assert set(c['required']) == {org_by_id[i]['name'] for i in c['required_department_ids']}, c['id']
    else:
        assert c['required'] in {'all', 'none'}, c['id']
    if c['collection_enabled']:
        assert c['source_url'] and c['status'] == 'found' and c['classification'] != 'excluded', c['id']
    if c['evidence']:
        assert (root / c['evidence']).is_file(), c['id']
missing_orgs = {o['id'] for o in orgs if o['status'] != 'found'}
missing_channels = {i for c in channels if c['status'] == 'missing' for i in c['organization_ids']}
assert missing_orgs == missing_channels, '미확인 조직 누락'
review = json.loads((root / 'docs/channel-review-data.json').read_text())
assert review['channels'] == channels and review['organizations'] == orgs, '화면 데이터 불일치'
html = (root / 'docs/channel-review.html').read_text()
embedded = html.split('<script id="catalog" type="application/json">', 1)[1].split('</script>', 1)[0]
assert json.loads(embedded) == review, 'HTML 데이터 불일치'
print(f'검증 완료: 조직 {len(orgs)}개, 채널 {len(channels)}개, 주소 미확인 {len(missing_orgs)}개')
