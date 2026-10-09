"""build가 띄우는 보조 프로세스: 넘겨받은 음성을 자기 GPU에서 만들어 캐시에 저장한다."""
import json
from pathlib import Path
import sys
import time

from briefing.build import atomic_bytes, audio_info
from briefing.qwen_tts import QwenTTS


def run(spec_path, *, provider=None, clock=time.monotonic):
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    provider = provider or QwenTTS(instructions=spec['instructions'])
    started, done = clock(), 0
    for job in spec['jobs']:
        if spec['budget'] is not None and clock() - started >= spec['budget']:
            break
        path = Path(job['path'])
        if path.exists():
            continue
        try:
            raw = provider.synthesize(job['script'], job['voice'], spec['model'], spec['tempo'])
            audio_info(raw)
            atomic_bytes(path, raw)
            done += 1
        except Exception as exc:
            # 실패 기록과 구간 제외는 build가 같은 음성을 다시 시도하면서 처리한다.
            print(f'보조 GPU 음성 실패, 주 프로세스가 다시 시도합니다: {type(exc).__name__}', flush=True)
    print(f'보조 GPU 음성 {done}/{len(spec["jobs"])}개 저장.', flush=True)
    return done


if __name__ == '__main__':
    run(sys.argv[1])
