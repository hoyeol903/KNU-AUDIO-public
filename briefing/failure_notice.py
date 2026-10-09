"""Kaggle 산출물의 실패 목록을 기존 GitHub 메일 알림용 글로 만든다."""
import json
import os
from pathlib import Path
import re


def cell(value):
    value = re.sub(r'(?i)(?:Bearer\s+|KGAT_)[A-Za-z0-9._-]+', '[토큰 숨김]', str(value))
    return value.replace('|', '/').replace('\n', ' ')[:700]


def render(folder, generation, publication, publish_requested, owner, run_url, failure_stage='Kaggle 실행'):
    reports = list(Path(folder).rglob('briefing-report.json'))
    report = json.loads(reports[0].read_text()) if reports else {}
    failures = report.get('audio_failures', [])
    skipped = report.get('skipped_notices', [])
    if generation == 'success' and (not publish_requested or publication == 'success') and not failures and not skipped:
        return ''
    lines = [f'@{owner} 브리핑 실행 결과', '', f'실행 기록: {run_url}', '',
             f'- 음성 작업: {generation}', f'- 사이트 게시: {publication if publish_requested else "요청하지 않음"}']
    if failures:
        lines += ['', '실패한 음성은 제외하고 나머지를 생성했습니다.', '',
                  '| 실패한 항목 | 게시판 | 원인 | 재실행 여부 |', '|---|---|---|---|']
        seen = set()
        for f in failures:
            if f['segment_id'] in seen:
                continue
            seen.add(f['segment_id'])
            lines.append('| ' + ' | '.join(map(cell, [f['title'], ', '.join(f['channel_ids']),
                          f['error_type'] + ': ' + f['message'], f['retry']])) + ' |')
    for s in skipped:
        if s.get('reason') != 'audio-failed':
            lines.append(f"- 대본 제외: {cell(s['title'])} — {cell(s.get('errors', []))}. 대본 확인 후 재실행.")
    resumes = list(Path(folder).rglob('resume.json'))
    if generation != 'success' and resumes:
        resume = json.loads(resumes[0].read_text())
        lines += ['',
                  '저장된 묶음: ' + cell(resume['kernel_id']),
                  '같은 실행의 Re-run failed jobs를 누르면 저장된 묶음부터 자동으로 이어갑니다.',
                  '새 실행이라면 resume_kernel에 위 커널 ID를 입력하세요.']
    if generation != 'success':
        lines += ['', f'실패 단계: {failure_stage}. 실행 기록과 진단 파일을 확인한 뒤 재실행하세요.',
                  '인증 실패라면 GitHub Secrets의 KAGGLE_API_TOKEN을 확인하세요. 사용량 초과 여부는 Kaggle quota로 별도 확인해야 합니다.']
    if publish_requested and generation == 'success' and publication != 'success':
        lines += ['', '사이트 게시에 실패했습니다. 생성 결과는 artifact에 보관되어 있으니 게시 단계부터 재실행하세요.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    Path('briefing-notice.md').write_text(render(
        '.cache/kaggle', os.environ['GENERATION_RESULT'], os.environ['PUBLICATION_RESULT'],
        os.environ.get('PUBLISH_REQUESTED') == 'true', os.environ['GH_OWNER'], os.environ['RUN_URL'], os.environ.get('FAILURE_STAGE', 'Kaggle 실행')), encoding='utf-8')
