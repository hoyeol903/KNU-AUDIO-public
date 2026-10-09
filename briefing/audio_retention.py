"""게시 음성을 마지막 사용일 기준 최근 14일치 보관한다."""
from datetime import date, timedelta
import json
from pathlib import Path

from collector.store import save_json

RETENTION_DAYS = 14


def retain_audio(output, day, current_files, *, records=None, previous=None):
    output = Path(output)
    today = date.fromisoformat(day)
    cutoff = today - timedelta(days=RETENTION_DAYS - 1)
    ledger_path = output / 'audio-retention.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}

    def remember(name, used):
        if not isinstance(name, str) or Path(name).name != name or Path(name).suffix.lower() != '.mp3':
            return
        used = date.fromisoformat(used).isoformat()
        ledger[name] = max(ledger.get(name, used), used)

    # 첫 적용 시 기존 게시 기록으로 날짜를 복원한다. 기록 없는 파일은 14일 유예한다.
    if not ledger_path.exists() and records:
        for path in Path(records).glob('briefing-kaggle-*.json'):
            record = json.loads(path.read_text(encoding='utf-8'))
            if record.get('verified') and record.get('input_date'):
                for name in record.get('app_file_sha256', {}):
                    remember(name, record['input_date'])
    if previous and previous.get('date'):
        for segment in previous.get('segments', []):
            remember(segment.get('audio'), previous['date'])
    for path in output.glob('*.mp3'):
        if path.is_file() and path.name not in ledger:
            remember(path.name, day)
    for name in current_files:
        remember(name, day)
    current_files = set(current_files)
    expired = []
    for path in output.glob('*.mp3'):
        if path.is_file() and path.name not in current_files and date.fromisoformat(ledger[path.name]) < cutoff:
            expired.append(path)
    expired_names = {path.name for path in expired}
    kept = {name: used for name, used in ledger.items()
            if Path(name).name == name and (output / name).is_file() and name not in expired_names}
    save_json(kept, ledger_path)
    for path in expired:
        path.unlink()
    return [path.name for path in expired]
