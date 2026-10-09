import json
from copy import deepcopy
from unittest.mock import Mock

from briefing import build as b, app_export
from briefing.content import notice_key


def test_only_exact_normalized_content_is_shared():
    row = dict(id='a:1', title='[안내] 모집', body='대상: 재학생\n신청: 학교 홈페이지', deadline=None)
    copy = dict(row, id='b:2', title='모집', body='대상: 재학생  신청: 학교 홈페이지')
    assert notice_key(row) == notice_key(copy)
    for field, value in [('body', '대상: 휴학생 신청: 학교 홈페이지'), ('title', '다른 모집'), ('deadline', '2026-10-10')]:
        assert notice_key(row) != notice_key(dict(copy, **{field: value}))
    assert notice_key(dict(row, body=None)) != notice_key(dict(copy, body=None))


def test_duplicate_sources_generate_one_script_audio_and_keep_all_links(tmp_path, monkeypatch):
    data = json.loads((b.ROOT/'data/raw/2026-10-03/items.json').read_text())
    selected = [c for c in data['channels'] if c['notices']][:2]
    for c in data['channels']:
        c['meals'] = []
        c['notices'] = c['notices'][:1] if c in selected else []
    for i, c in enumerate(selected):
        n = c['notices'][0]
        n.update(title=('[안내] ' if i == 0 else '') + '공통 모집', body='재학생을 모집합니다. 신청은 학교 홈페이지에서 합니다.',
                 deadline=None, dday=None, reason='new')
    before = deepcopy(data)
    path = tmp_path/'items.json'; path.write_text(json.dumps(data))
    slm = Mock(); slm.identity.return_value='test'
    slm.generate.return_value='재학생을 모집해요.'
    tts = Mock(); tts.synthesize.side_effect=lambda script, *a: script.encode()
    monkeypatch.setattr(b, 'audio_info', lambda raw: 1.0)
    b.build(path, output=tmp_path/'dist', cache=tmp_path/'cache', allow_archive=True, client=tts, slm_client=slm)
    calls = [call for call in slm.generate.call_args_list if call.args[0]['kind'] == 'notice']
    assert len(calls) == 1
    manifest=json.loads((tmp_path/'dist/manifest.json').read_text())
    notices=[s for s in manifest['segments'] if s['kind']=='notice']
    assert len(notices)==1 and len(notices[0]['notice_refs'])==2
    assert set(notices[0]['channel_ids']) == {c['channel_id'] for c in selected}
    assert sum(call.args[0]=='재학생을 모집해요.' for call in tts.synthesize.call_args_list)==1
    assert data==before and json.loads(path.read_text())==before
    rows=app_export.export(tmp_path/'dist', tmp_path/'app', items_path=path, concat=lambda parts, target: target.write_bytes(b'joined'))
    shared=[s for s in rows if s.get('kind')=='notice']
    assert len(shared)==1
    assert {c['url'] for c in shared[0]['items']}=={c['notices'][0]['url'] for c in selected}
    assert {c['postId'] for c in shared[0]['items']}=={c['notices'][0]['id'] for c in selected}


def test_board_decorations_preview_contacts_and_attachment_lists_are_ignored():
    from briefing.content import same_notice
    row = dict(id='a:1', title='[공지][교직] ■ 모집', body='대상: 재학생\n신청: 학교 홈페이지\n첨부파일중 이미지 미리보기\n붙임 1. 관련 공문 1부.\n2. 신청서 1부.', deadline=None)
    other = dict(row, id='b:2', title='모집', body='대상: 재학생\n신청: 학교 홈페이지\n문의처: 사무실 053-950-1234')
    assert notice_key(row) == notice_key(other)
    assert same_notice(row, other)
    assert notice_key(dict(row, title='[필수] 모집')) != notice_key(other)
    assert notice_key(dict(row, body='신청금액: -100원')) != notice_key(dict(other, body='신청금액: 100원'))


def test_near_identical_wording_can_merge_but_important_changes_cannot():
    from briefing.content import same_notice
    core = '다양한 경험을 공유하는 교내 프로그램을 소개해요. ' * 8
    row = dict(id='a:1', title='프로그램 안내', body=core+'\n안내합니다.\n대상: 재학생\n장소: 대구\n기간: 10월 8일~10월 9일', deadline=None)
    other = dict(row, id='b:2', body=row['body'].replace('안내합니다.', '안내드립니다.'))
    assert same_notice(row, other)
    for old, new in [('재학생','휴학생'), ('대구','서울'), ('10월 8일','10월 9일'), ('대상: 재학생','대상: 재학생 제외')]:
        assert not same_notice(row, dict(other, body=other['body'].replace(old,new)))
    assert not same_notice(row, dict(other, body=other['body']+'\n추가 조건: 신청 불가'))
    assert not same_notice(dict(row, body='안내합니다.'), dict(other, body='안내드립니다.'))


def test_today_duplicates_merge_without_merging_department_rosters():
    from briefing.content import create_segments
    data = json.loads((b.ROOT/'data/raw/2026-10-08/items.json').read_text())
    original = deepcopy(data)
    rows, _ = create_segments(data, [], b.read_yaml(b.ROOT/'config/briefing.yaml'), [])
    notices=[s for s in rows if s['kind']=='notice']
    common=[s for s in notices if '전국 지역인재 7급' in s['title']]
    assert len(common)==1 and len(common[0]['notice_refs'])==9
    rosters=[s for s in notices if '안전교육(정기/신규)' in s['title']]
    assert len(rosters)==2
    assert len(notices)==42
    assert sum(len(s['notice_refs']) for s in notices)==62
    assert data==original


def test_redacted_department_rosters_remain_separate():
    from briefing.content import same_notice
    row = dict(id='a:1', title='안전교육 이수현황', body='교육기간: 11월 30일까지\n[개인정보 가림]', deadline=None)
    other = dict(row, id='b:2')
    assert notice_key(row) != notice_key(other)
    assert not same_notice(row, other)
