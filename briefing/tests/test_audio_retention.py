import json
from briefing.audio_retention import retain_audio


def test_fourteen_days_and_shared_audio(tmp_path):
    for name in ['old.mp3', 'boundary.mp3', 'current.mp3', 'shared.mp3', 'unknown.mp3']:
        (tmp_path / name).write_bytes(b'audio')
    (tmp_path / 'audio-retention.json').write_text(json.dumps({'old.mp3':'2026-09-26','boundary.mp3':'2026-09-27','current.mp3':'2026-09-01','shared.mp3':'2026-09-01'}))
    (tmp_path / 'keep.json').write_text('{}')
    deleted = retain_audio(tmp_path, '2026-10-10', ['current.mp3','shared.mp3'])
    assert deleted == ['old.mp3']
    assert (tmp_path / 'boundary.mp3').exists()  # 오늘 포함 14일째
    assert (tmp_path / 'keep.json').exists()
    assert json.loads((tmp_path / 'audio-retention.json').read_text())['shared.mp3'] == '2026-10-10'
    retain_audio(tmp_path, '2026-10-24', ['current.mp3'])
    assert not (tmp_path / 'unknown.mp3').exists()
    assert not (tmp_path / 'shared.mp3').exists()
    assert (tmp_path / 'current.mp3').exists()


def test_initial_existing_records_and_previous_manifest(tmp_path):
    output = tmp_path / 'audio'; output.mkdir()
    records = tmp_path / 'records'; records.mkdir()
    for name in ['old.mp3','previous.mp3','unknown.mp3','new.mp3']:
        (output / name).write_bytes(b'audio')
    (records / 'briefing-kaggle-2026-09-01.json').write_text(json.dumps({'verified':True,'input_date':'2026-09-01','app_file_sha256':{'old.mp3':'hash','segments.json':'hash'}}))
    retain_audio(output,'2026-10-10',['new.mp3'],records=records,previous={'date':'2026-10-09','segments':[{'audio':'previous.mp3'}]})
    assert not (output / 'old.mp3').exists()
    ledger=json.loads((output / 'audio-retention.json').read_text())
    assert ledger['previous.mp3']=='2026-10-09'
    assert ledger['unknown.mp3']=='2026-10-10'
