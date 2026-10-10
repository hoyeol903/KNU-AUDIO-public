"""python -m briefing.build --input data/raw/YYYY-MM-DD/items.json --text-only"""
import argparse
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import yaml
from mutagen.mp3 import MP3

from collector.store import SEOUL, load_collection_report, save_daily_items, save_json
from briefing.content import create_segments, digest
from briefing.failure_notice import cell
from briefing.open_tts import qwen_spoken_text
from briefing.qwen_tts import (QwenTTS, VOICES, VOICE_NAMES, MODE, MODEL as QWEN_MODEL, CACHE_VERSION,
                               CACHE_PROFILE, gpu_count)
from briefing.slm import Ollama, generate_segments

ROOT = Path(__file__).resolve().parents[1]


class AudioBatchComplete(Exception):
    """이번 묶음의 음성을 저장했고 다음 실행에서 이어간다."""



class ProgressRecorder:
    """Writes compact, resumable run diagnostics without recording script text."""
    def __init__(self, path):
        self.path = Path(path)
        self.started = time.monotonic()
        self.started_at = datetime.now(SEOUL).isoformat(timespec='seconds')
        self.active = None
        self.events = []

    def update(self, stage, status, unit=None, completed=None, total=None):
        now = time.monotonic()
        if status == 'started':
            self.active = (stage, unit, now)
        active_elapsed = (round(now - self.active[2], 2)
                          if self.active and self.active[:2] == (stage, unit) and status != 'started' else None)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        peak_rss = int(usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024))
        event = dict(at=datetime.now(SEOUL).isoformat(timespec='seconds'), stage=stage, status=status,
                     unit=unit, completed=completed, total=total,
                     elapsedSeconds=round(now - self.started, 2), unitElapsedSeconds=active_elapsed,
                     cpuUserSeconds=round(usage.ru_utime, 2), cpuSystemSeconds=round(usage.ru_stime, 2),
                     peakMemoryBytes=peak_rss)
        self.events.append(event)
        save_json(dict(startedAt=self.started_at, updatedAt=event['at'], status=status,
                       stage=stage, completed=completed, total=total, events=self.events), self.path)
        print('브리핑 진행: ' + json.dumps(event, ensure_ascii=False), flush=True)
        if status in {'completed', 'failed', 'interrupted', 'skipped'} and self.active and self.active[:2] == (stage, unit):
            self.active = None


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding='utf-8'))


def validate_config(config, events):
    if 'fixed_message' in config and (not isinstance(config['fixed_message'], str)
                                     or not 1 <= len(config['fixed_message'].strip()) <= 2000):
        raise ValueError('고정 멘트는 1~2000자의 문장이어야 합니다.')
    for key in ('greeting', 'outro', 'weather_region', 'model'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f'설정 누락: {key}')
    for key, minimum, maximum in [('umbrella_rain_percent', 0, 100), ('jacket_below_celsius', -30, 40),
                                   ('tempo', .5, 2), ('event_horizon_days', 1, 365), ('max_events', 1, 10)]:
        if type(config.get(key)) not in (int, float) or not minimum <= config[key] <= maximum:
            raise ValueError(f'잘못된 설정: {key}')
    for key in ('greeting_templates', 'outro_variants'):
        if key in config and (not isinstance(config[key], list) or len(config[key]) != 3
                              or any(not isinstance(value, str) or not value.strip() for value in config[key])):
            raise ValueError(f'{key}에는 비어 있지 않은 문장 3개가 필요합니다')
    for template in config.get('greeting_templates', []):
        if template.count('{name}') != 1 or '{' in template.replace('{name}', '') or '}' in template.replace('{name}', ''):
            raise ValueError('이름 인사에는 {name} 자리표시자 하나만 필요합니다')
    if config['model'] != QWEN_MODEL:
        raise ValueError(f'model은 {QWEN_MODEL}로 설정하세요')
    if config.get('tts', {}).get('device', 'auto') not in {'auto', 'cpu', 'cuda:0'}:
        raise ValueError('tts.device는 auto, cpu, cuda:0 중 하나여야 합니다')
    voices = config.get('voices', list(VOICES))
    if not voices or set(voices) - set(VOICES):
        raise ValueError('voices는 female, male 중에서 하나 이상 고르세요')
    instructions = config.get('tts', {}).get('instructions', {})
    if not isinstance(instructions, dict) or set(instructions) - set(VOICES):
        raise ValueError('tts.instructions는 female/male 화자별 문장 설정이어야 합니다')
    if any(not isinstance(value, str) for value in instructions.values()):
        raise ValueError('tts.instructions의 값은 문자열이어야 합니다')
    if 'female' in voices and not instructions.get('female', '').strip():
        raise ValueError('여성 Sohee 화자의 tts.instructions.female 문장을 설정하세요')
    if not isinstance(events, list):
        raise ValueError('events.yaml은 행사 목록이어야 합니다')
    for event in events:
        if set(event) != {'title', 'date', 'source_url'} or not event['title'].strip():
            raise ValueError('행사는 title/date/source_url이 필요합니다')
        date.fromisoformat(event['date'])
        if not event['source_url'].startswith('https://'):
            raise ValueError('행사의 공식 출처 https URL이 필요합니다')
    if not 0 <= config['bgm']['volume'] <= .3:
        raise ValueError('배경음악 기본 음량은 0~0.3으로 설정하세요')
    slm = config.get('slm', {})
    if not isinstance(slm.get('model'), str) or not slm['model'].strip():
        raise ValueError('slm.model을 설정하세요')
    if type(slm.get('timeout_seconds')) is not int or not 1 <= slm['timeout_seconds'] <= 3600:
        raise ValueError('slm.timeout_seconds는 1~3600초로 설정하세요')


@contextmanager
def writer_lock(cache):
    cache.mkdir(parents=True, exist_ok=True)
    lock = cache / '.build-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError('다른 음성 생성이 진행 중입니다. 중단된 실행이라면 프로세스 종료 확인 후 .cache/briefing/.build-lock을 삭제하세요.') from None
    try:
        yield
    finally:
        lock.rmdir()


def audio_info(raw):
    try:
        info = MP3(io.BytesIO(raw)).info
        if info.length <= 0:
            raise ValueError()
        return round(info.length, 3)
    except Exception:
        raise ValueError('유효한 MP3 음성이 아닙니다. 기존 배포 파일을 유지합니다.') from None


def atomic_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def audio_key(script, voice, config):
    role = next((name for name, speaker in VOICES.items() if speaker == voice), None)
    instructions = config.get('tts', {}).get('instructions', {})
    return digest(json.dumps(dict(provider=CACHE_VERSION, text=qwen_spoken_text(script), voice=voice,
                                 model=config['model'], tempo=config['tempo'], format='mp3', language='Korean',
                                 instruct=instructions.get(role, ''), generation=CACHE_PROFILE), sort_keys=True))


def start_gpu_helper(shard, config, cache, budget):
    """두 번째 GPU만 보이는 별도 프로세스로 음성 일부를 만든다. 시드가 같아 결과는 GPU와 무관하다."""
    spec = Path(cache) / 'gpu-helper.json'
    spec.write_text(json.dumps(dict(
        jobs=[dict(script=job['script'], voice=job['voice'], path=str(job['path'])) for job in shard],
        model=config['model'], tempo=config['tempo'], instructions=config.get('tts', {}).get('instructions', {}),
        budget=budget), ensure_ascii=False), encoding='utf-8')
    print(f'두 번째 GPU에서 음성 {len(shard)}개를 함께 만듭니다.', flush=True)
    return subprocess.Popen([sys.executable, '-m', 'briefing.audio_shard', str(spec)], cwd=ROOT,
                            env=dict(os.environ, CUDA_VISIBLE_DEVICES='1'))


def prepare_bgm(config):
    bgm = config['bgm']
    if not bgm.get('file'):
        return None
    path = (ROOT / bgm['file']).resolve()
    if not path.is_relative_to(ROOT / 'assets') or path.suffix.lower() not in {'.mp3', '.wav'}:
        raise ValueError('허락받은 음악 파일은 assets/ 안의 MP3 또는 WAV로 설정하세요')
    if not bgm.get('license_note') or not bgm.get('attribution'):
        raise ValueError('배경음악 license_note와 attribution을 입력하세요')
    raw = path.read_bytes()
    if path.suffix.lower() == '.mp3':
        audio_info(raw)
    else:
        import wave
        with wave.open(io.BytesIO(raw)) as wav:
            if wav.getnframes() <= 0:
                raise ValueError('빈 WAV 파일')
    return dict(path='audio/bgm-' + hashlib.sha256(raw).hexdigest() + path.suffix.lower(), raw=raw,
                attribution=bgm['attribution'], source_url=bgm['source_url'], volume=bgm['volume'])


def build(input_path, *, text_only=False, plan=False, output=None, cache=None, allow_archive=False,
          client=None, slm_client=None, progress=None, audio_batch_size=None, audio_batch_seconds=None,
          failed_audio=None):
    if progress:
        progress.update('build', 'started', 'initialize')
    config = read_yaml(ROOT / 'config/briefing.yaml')
    events = read_yaml(ROOT / 'config/events.yaml')
    validate_config(config, events)
    data = load_collection_report(input_path)
    # 기존 수집기 계약을 변경하지 않고 검증한다.
    with tempfile.TemporaryDirectory() as td:
        save_daily_items(data, Path(td) / 'validated.json')
    if not (text_only or plan or allow_archive) and data['date'] != datetime.now(SEOUL).date().isoformat():
        raise ValueError('오늘 자료가 아닙니다. 시험용 과거 자료는 --allow-archive를 명시하세요.')
    catalog = read_yaml(ROOT / 'data/channels.yaml')
    departments = read_yaml(ROOT / 'data/departments.yaml')
    segments, warnings = create_segments(data, catalog, config, events)
    bgm = prepare_bgm(config)
    # 목소리마다 음성을 따로 만들므로 시간이 그만큼 든다. config의 voices로 만들 목소리를 고른다.
    voices = {role: VOICES[role] for role in config.get('voices', list(VOICES))}
    cache = Path(cache or ROOT / '.cache/briefing')
    output = Path(output or ROOT / ('preview' if text_only else 'dist'))
    if text_only and output.resolve() == (ROOT / 'dist').resolve():
        raise ValueError('대본 미리보기는 배포 dist에 덮어쓸 수 없습니다')
    with writer_lock(cache):
        if plan:
            report = dict(mode='plan', segments=len(segments), slm_segments=sum(s['generation'] == 'slm' for s in segments))
            print(json.dumps(report, ensure_ascii=False))
            if progress:
                progress.update('plan', 'completed', 'segments', len(segments), len(segments))
            return report
        if progress:
            progress.update('scripts', 'started', 'all', 0, len(segments))
        total_segments = len(segments)
        segments = generate_segments(segments, slm_client or Ollama(config['slm']), cache, ROOT / 'output/review.json',
                                     progress=progress)
        skipped_notices = [s['_skip_notice'] for s in segments if s.get('_skip_notice')]
        for skipped in skipped_notices:
            for channel_id in skipped['channel_ids']:
                warnings.append(dict(source=channel_id, message=f"공지 요약 검수 실패로 제외됨: {skipped['title']}"))
        segments = [s for s in segments if not s.get('_skip_notice')]
        if progress:
            progress.update('scripts', 'completed', total_segments, total_segments)
        for segment in segments:
            segment['spoken_script'] = qwen_spoken_text(segment['script'])
        jobs = {}
        for segment in segments:
            for role, voice in voices.items():
                key = audio_key(segment['script'], voice, config)
                jobs.setdefault((role, key), dict(script=segment['script'], voice=voice, path=cache / (key + '.mp3')))
        failed_audio = failed_audio if failed_audio is not None else {}
        missing = []
        for identity, job in jobs.items():
            if ':'.join(identity) in failed_audio:
                continue
            if job['path'].exists():
                audio_info(job['path'].read_bytes())
            else:
                missing.append(identity)
        report = dict(status='partial' if skipped_notices else 'passed', date=data['date'],
                      segments=len(segments), unique_requests=len(jobs),
                      cached=sum(job['path'].exists() for job in jobs.values()), new_requests=len(missing),
                      new_characters=sum(len(jobs[k]['script']) for k in missing),
                      mode='text-only' if text_only else MODE, warnings=warnings,
                      skipped_notices=skipped_notices, audio_failures=[f for rows in failed_audio.values() for f in rows],
                      deadline_checks=[s['deadline_verification'] for s in segments
                                       if s.get('deadline_verification')])
        print(json.dumps({k: v for k, v in report.items()
                          if k not in {'warnings', 'deadline_checks', 'skipped_notices'}}, ensure_ascii=False))
        save_json(report, ROOT / 'output/briefing-report.json')
        if not text_only:
            failed = {tuple(key.split(':', 1)) for key in failed_audio}
            if failed:
                report['status'] = 'partial'
            provider = client or QwenTTS(device=config.get('tts', {}).get('device', 'auto'),
                                         instructions=config.get('tts', {}).get('instructions', {}))
            # 지원 모델/화자와 인코더를 검증한다.
            for index, (role, voice) in enumerate(voices.items(), 1):
                if progress:
                    progress.update('voice-check', 'started', role, index - 1, len(voices))
                try:
                    provider.verify(voice, role, config['model'])
                except BaseException:
                    if progress:
                        progress.update('voice-check', 'failed', role, index - 1, len(voices))
                    raise
                if progress:
                    progress.update('voice-check', 'completed', role, index, len(voices))
            audio_started = time.monotonic()
            # GPU가 두 장이면 절반을 두 번째 GPU의 보조 프로세스에 맡긴다. 보조가 못 만든 음성은 아래 반복문이 이어서 처리한다.
            helper, shard = None, []
            if (client is None and len(missing) > 1 and config.get('tts', {}).get('device', 'auto') != 'cpu'
                    and gpu_count() > 1):
                shard = missing[1::2]
                helper = start_gpu_helper([jobs[key] for key in shard], config, cache, audio_batch_seconds)

            def pending():
                yield from (missing[0::2] if helper else missing)
                if helper:
                    helper.wait()
                    yield from (key for key in shard if not jobs[key]['path'].exists())
            try:
                for index, identity in enumerate(pending(), 1):
                    # 시간 기준 묶음은 한 개 이상 만든 뒤에만 끊어, 느린 음성 하나로 진행이 멈추지 않게 한다.
                    if (audio_batch_size is not None and index > audio_batch_size
                            or audio_batch_seconds is not None and index > 1
                            and time.monotonic() - audio_started >= audio_batch_seconds):
                        raise AudioBatchComplete()
                    job = jobs[identity]
                    unit = f'{index}/{len(missing)}:{identity[0]}'
                    if progress:
                        progress.update('audio', 'started', unit, index - 1, len(missing))
                    try:
                        raw = provider.synthesize(job['script'], job['voice'], config['model'], config['tempo'])
                        audio_info(raw)
                        atomic_bytes(job['path'], raw)
                    except Exception as exc:
                        failed.add(identity)
                        affected = [s for s in segments if audio_key(s['script'], voices[identity[0]], config) == identity[1]]
                        entries = []
                        for segment in affected:
                            entries.append(dict(
                                segment_id=segment['id'], kind=segment['kind'], title=segment['title'],
                                channel_ids=segment['channel_ids'], notice_refs=segment.get('notice_refs', []),
                                voice=identity[0], error_type=type(exc).__name__, message=cell(exc),
                                retry='대본을 짧게 나눈 뒤 재실행' if '길이 상한' in str(exc) else '원인 확인 후 재실행'))
                        failed_audio[':'.join(identity)] = entries
                        report['audio_failures'].extend(entries)
                        report['status'] = 'partial'
                        save_json(report, ROOT / 'output/briefing-report.json')
                        if progress:
                            progress.update('audio', 'failed', unit, index, len(missing))
                        continue
                    if progress:
                        progress.update('audio', 'completed', unit, index, len(missing))
            finally:
                # 묶음 시간이 차거나 오류로 나가도 보조가 만들던 음성까지 저장된 뒤 checkpoint를 남긴다.
                if helper:
                    helper.wait()
            retained = []
            for segment in segments:
                if any((role, audio_key(segment['script'], voice, config)) in failed for role, voice in voices.items()):
                    refs = segment.get('notice_refs') or [dict(postId=segment.get('notice_id'), title=segment['title'],
                                                               url=segment.get('url'), channel_id=c) for c in segment['channel_ids']]
                    if segment['kind'] == 'notice':
                        skipped_notices.extend(dict(notice_id=r['postId'], title=r['title'], url=r['url'],
                                                    channel_ids=[r['channel_id']], reason='audio-failed') for r in refs)
                    for cid in segment['channel_ids']:
                        warnings.append(dict(source=cid, message=f"음성 생성 실패로 제외됨: {segment['title']}"))
                    continue
                retained.append(segment)
            segments = retained
            report['segments'] = len(segments)
            save_json(report, ROOT / 'output/briefing-report.json')
            if not segments:
                raise RuntimeError('모든 음성 생성이 실패했습니다. 기존 게시 결과를 유지합니다.')
            for segment in segments:
                for role, voice in voices.items():
                    key = audio_key(segment['script'], voice, config)
                    raw = (cache / (key + '.mp3')).read_bytes()
                    filename = hashlib.sha256(raw).hexdigest() + '.mp3'
                    segment['audio'][role] = dict(url='audio/' + filename, duration_sec=audio_info(raw))
                    atomic_bytes(output / 'audio' / filename, raw)
        present = {c['channel_id'] for c in data['channels']}
        offered = [c for c in catalog if c.get('classification') == 'required' and c['type'] == 'notice'
                   or c['type'] == 'meal' and c.get('collection_enabled')]
        # 입력에만 있는 새 채널도 선택 가능하게 보존한다.
        offered_ids = {c['id'] for c in offered}
        offered += [dict(id=cid, name=cid, type='notice', required='none') for cid in sorted(present - offered_ids)]
        channels = [dict(id=c['id'], name=c['name'], type=c['type'], required=c.get('required', 'none'),
                         department_ids=c.get('required_department_ids', []), available=c['id'] in present,
                         issues=[e['message'] for e in warnings if e['source'] == c['id']]) for c in offered]
        public_segments = [{k: v for k, v in s.items() if k not in {
            'source_text', 'reference', 'required', 'constraints', 'deadline_verification', 'notice_id', '_skip_notice'}} for s in segments]
        manifest = dict(schema_version=2, status=report['status'], date=data['date'], collected_at=data['collected_at'],
                        generated_at=datetime.now(SEOUL).isoformat(), mode=report['mode'],
                        voices={r: dict(name=VOICE_NAMES[r], speaker=voices[r], ready=not text_only) for r in voices},
                        tts=dict(provider='Qwen3-TTS', model=config['model']),
                        channels=channels, departments=[dict(id=d['id'], name=d['name'], college=d['college'],
                                                             child_department_ids=d.get('child_department_ids', []))
                                                        for d in departments if d.get('kind') == 'department'],
                        segments=public_segments, audio_failures=report['audio_failures'],
                        skipped_notices=[{k: v for k, v in s.items() if k != 'errors'} for s in skipped_notices],
                        warnings=warnings, bgm=None)
        if bgm:
            atomic_bytes(output / bgm['path'], bgm['raw'])
            manifest['bgm'] = {k: v for k, v in bgm.items() if k != 'raw'}
        for path in (ROOT / 'web/player').iterdir():
            if path.is_file():
                atomic_bytes(output / path.name, path.read_bytes())
        (output / '.nojekyll').touch()
        # 실패한 구간을 제외하고 완성된 음성 목록만 원자적으로 교체한다.
        save_json(manifest, output / 'manifest.json')
        save_json(report, ROOT / 'output/briefing-report.json')
        print(f'완료: {output}/index.html · HTTP 서버로 열어 주세요.')
        if progress:
            progress.update('build', 'completed', 'manifest', len(segments), len(segments))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--text-only', action='store_true')
    parser.add_argument('--plan', action='store_true', help='모델을 호출하지 않고 입력 구간 수만 확인')
    parser.add_argument('--allow-archive', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    progress = ProgressRecorder(ROOT / 'output/briefing-progress.json')
    old_handlers = {}

    def interrupted(signum, frame):
        progress.update('build', 'interrupted', signal.Signals(signum).name)
        raise SystemExit(128 + signum)

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            old_handlers[signum] = signal.signal(signum, interrupted)
        build(args.input, text_only=args.text_only, plan=args.plan, allow_archive=args.allow_archive,
              output=args.output, progress=progress)
    except KeyboardInterrupt:
        progress.update('build', 'interrupted', 'KeyboardInterrupt')
        raise
    except Exception as exc:
        progress.update('build', 'failed', type(exc).__name__)
        parser.exit(1, str(exc) + '\n')
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


if __name__ == '__main__':
    main()
