"""관리자가 저장한 고정 멘트를 다음 브리핑의 설정 스냅샷에 반영한다."""
import json
from pathlib import Path
import re
import tempfile

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://knua-community-api.knua-public-pr73.workers.dev/api/community/fixed-message'


def validate_message(value):
    if (not isinstance(value, str) or not 1 <= len(value.strip()) <= 500
            or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value)):
        raise ValueError('고정 멘트는 1~500자의 문장이어야 합니다.')
    return value.strip()


def sync_config(root=ROOT, *, get=requests.get, report=print):
    root = Path(root)
    path = root / 'config/briefing.yaml'
    config = yaml.safe_load(path.read_text(encoding='utf-8'))
    try:
        with get(ENDPOINT, timeout=(5, 15), stream=True) as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_content(1024):
                raw.extend(chunk)
                if len(raw) > 8192:
                    raise ValueError('고정 멘트 응답이 너무 큽니다.')
            value = validate_message(json.loads(raw)['text'])
        report('관리자 고정 멘트를 다음 브리핑에 반영합니다.')
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        # 서버 일시 장애가 이미 적용한 멘트를 옛 기본값으로 되돌리지 않게 한다.
        published = root / 'output/app/data/briefing/segments.json'
        value = config.get('fixed_message')
        if published.exists():
            data = json.loads(published.read_text(encoding='utf-8'))
            message = next((s for s in data['segments'] if s.get('channel_id', s.get('id')) == 'message'), None)
            if message:
                value = validate_message(message['script'])
        value = validate_message(value)
        report(f'::warning::관리자 멘트를 읽지 못했습니다 ({type(exc).__name__}). 마지막 적용 멘트를 유지합니다.')
    config['fixed_message'] = value
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            yaml.safe_dump(config, stream, allow_unicode=True, sort_keys=False)
            stream.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return value


if __name__ == '__main__':
    sync_config()
