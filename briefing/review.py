"""가벼운 결정론적 경계 검수. 사실의 의미 전체를 보증하지 않는다."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation

VERSION = 'rules-12-length'
TIME = re.compile(r'(?:(오전|오후|아침|저녁|밤|낮)\s*)?(\d{1,2})\s*(?::\s*(\d{2})|시(?:\s*(\d{1,2})\s*분)?)')
ISO_DATE = re.compile(r'(?<!\d)(\d{4})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})(?!\d)')
PHONE = re.compile(r'(?<!\d)(?:\+?82[-. ]?)?0\d{1,3}[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)')
MONEY = re.compile(r'(?<![\d.,])\d[\d,]*(?:\.\d+)?\s*(?:[백천만억]\s*(?:\d[\d,]*(?:\.\d+)?\s*)?)*원')
PII = (
    re.compile(r'(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'),
    PHONE,
    re.compile(r'(?:학번|학생번호)\s*[:：]?\s*\d{8,10}'),
    re.compile(r'(?<!\d)\d{6}\s*[-–]\s*[1-4]\d{6}(?!\d)'),
)
PROFANITY = re.compile(r'씨발(?:놈|년|새끼)?|시발(?:놈|년|새끼)|(?<![가-힣])시발(?!점)|개새끼|병신|지랄|좆(?:까|같)|씹(?:새끼|년|놈)')


def normalized(text):
    text = unicodedata.normalize('NFC', text).replace('\ufeff', '').replace('\u200b', '')
    return re.sub(r'\s+', ' ', text).strip()


def _numbers(text):
    values = set()
    def date_parts(match):
        return ' '.join(str(int(part)) for part in match.groups())
    rest = PHONE.sub(' ', text)
    def money_value(match):
        total, group = Decimal(0), Decimal(0)
        pending = ''
        for token in re.findall(r'\d[\d,]*(?:\.\d+)?|[백천만억]', match.group()):
            if token[0].isdigit():
                pending = token
            elif token in '백천':
                group += Decimal(pending.replace(',', '') or '1') * {'백': 100, '천': 1000}[token]
                pending = ''
            else:
                group += Decimal(pending.replace(',', '') or '0')
                total += group * {'만': 10000, '억': 100000000}[token]
                group, pending = Decimal(0), ''
        total += group + Decimal(pending.replace(',', '') or '0')
        values.add(('money', total.normalize()))
        return ' '
    rest = MONEY.sub(money_value, rest)
    rest = ISO_DATE.sub(date_parts, rest)
    rest = re.sub(r'([~∼〜～–—])\s*(\d{1,2})\.(\d{1,2})(?!\d)',
                  lambda m: m.group(1) + ' ' + str(int(m.group(2))) + ' ' + str(int(m.group(3))), rest)
    pieces = []
    cursor = 0
    previous_period = None
    for match in TIME.finditer(rest):
        pieces.append(rest[cursor:match.start()])
        meridiem, hour, minute, minute_word = match.groups()
        hour, minute = int(hour), int(minute or minute_word or 0)
        if not meridiem and re.fullmatch(r'\s*(?:부터|~|∼|〜|～|–|—|-)\s*', rest[cursor:match.start()]):
            meridiem = previous_period
        if meridiem and 1 <= hour <= 12:
            if meridiem in ('오후', '저녁', '낮'):
                hour = hour % 12 + 12
            elif meridiem == '밤':
                hour = 0 if hour == 12 else hour + 12
            else:
                hour %= 12
        previous_period = meridiem
        values.add(('time', hour, minute))
        cursor = match.end()
    pieces.append(rest[cursor:])
    rest = ''.join(pieces)
    # Numeric components are compared independent of zero-padding or date punctuation.
    for raw in re.findall(r'[-+]?\d[\d,]*(?:\.\d+)?', rest):
        try:
            number = Decimal(raw.replace(',', '')).normalize()
            if number == number.to_integral_value():
                values.add(('number', int(number)))
            else:
                values.add(('number', number))
        except InvalidOperation:
            continue
    return values



def redact(text):
    """Mask known contact/identifier/profanity patterns before model input or diagnostics."""
    for pattern in PII:
        text = pattern.sub('[개인정보 가림]', text)
    return PROFANITY.sub('[비속어 가림]', text)


def source_material(segment):
    source = '\n'.join(str(segment.get(key) or '') for key in ('source_text', 'reference'))
    amounts, unit = [], None
    for line in source.splitlines():
        if re.search(r'단위\s*[:：]\s*원', line):
            unit = line
            continue
        if unit and re.match(r'\s*\d+[).]\s*\S|\s*[가-하][.]\s*\S|.*단위\s*[:：]', line):
            unit = None
        if unit and re.fullmatch(r'\s*(?:\d{1,3}(?:,\d{3})+|\d{4,})\s*', line):
            amounts.append(dict(value=line.strip() + '원', evidence=unit + '\n' + line))
    # ponytail: only standalone table cells under an explicit won heading; complex tables need preserved HTML structure.
    return source, amounts


def comparison_source(segment):
    source, amounts = source_material(segment)
    return source + '\n' + '\n'.join(row['value'] for row in amounts)


def length_limit(segment):
    """강제할 대본 길이 상한(공백 포함 글자 수). 참고용 제한이나 제한이 없으면 None."""
    constraints = segment.get('constraints') or {}
    return None if constraints.get('feedback_only') else constraints.get('max_chars')


def revision_feedback(script, segment):
    """Give the existing generator concrete evidence; this is not an AI reviewer."""
    details = failure_details(script, segment)
    source, amounts = source_material(segment)
    missing = _numbers(redact(script)) - _numbers(comparison_source(segment)) if isinstance(script, str) else set()
    issues = []
    for kind, *parts in sorted(missing, key=str):
        pattern = TIME if kind == 'time' else MONEY if kind == 'money' else re.compile(r'[-+]?\d[\d,]*(?:\.\d+)?')
        candidates = []
        for match in pattern.finditer(source):
            quote = source[max(0, source.rfind('\n', 0, match.start()) + 1):source.find('\n', match.end()) if '\n' in source[match.end():] else len(source)]
            candidates.append(redact(quote))
        if kind == 'money':
            candidates.extend(redact(row['evidence']) for row in amounts)
        # Prefer explicit matching context labels; do not guess a replacement when ambiguous.
        script_quotes = []
        for match in pattern.finditer(script):
            if (kind, *parts) in _numbers(match.group()):
                script_quotes.append(redact(script[max(0, match.start()-50):match.end()+50]))
        labels = ('신청', '접수', '검사', '운영', '입실', '퇴실', '심사료', '사용료')
        relevant = [quote for quote in candidates if any(label in quote and any(label in q for q in script_quotes) for label in labels)]
        issues.append(dict(kind=kind, value=':'.join(format(v, 'f') if isinstance(v, Decimal) else str(v) for v in parts),
                           script_quotes=script_quotes, source_quotes=list(dict.fromkeys(relevant or candidates))[:12],
                           instruction='근거의 같은 항목 값을 사용하세요. 대응 값을 확정할 수 없으면 해당 표현을 생략하고 추측하지 마세요.'))
    limit = length_limit(segment)
    if limit and isinstance(script, str) and len(script) > limit:
        issues.append(dict(kind='길이', value=f'{len(script)}자', instruction=f'무엇을, 누가, 언제까지 해야 하는지만 남기고 공백 포함 {limit}자 이내로 줄이세요. 세부 일정·장소·조건 나열은 빼세요.'))
    for finding in details['findings']:
        if finding['rule'] in ('pii', 'profanity'):
            issues.append(dict(kind=finding.get('kind', '비속어'), instruction='가려진 연락처·식별정보 또는 비속어를 대본에서 삭제하세요.'))
    return dict(previous_script=details['script'], issues=issues,
                instruction='문제 부분만 수정하고 확인된 나머지 사실과 자연스러운 해요체를 유지하세요. 원문 근거 밖의 값을 만들지 마세요.')

def review(script, segment):
    if not isinstance(script, str) or not 1 <= len(script.strip()) <= 3500:
        return ['대본은 비어 있지 않고 3500자 이하여야 합니다.']
    errors = []
    source = comparison_source(segment)
    if set(_numbers(script)) - set(_numbers(source)):
        errors.append('원문 자료에 없는 숫자 값이 있습니다.')
    for pattern in PII:
        if pattern.search(script):
            errors.append('개인 연락처 또는 식별번호 형식이 포함되어 있습니다.')
            break
    if PROFANITY.search(script):
        errors.append('비속어 표현이 포함되어 있습니다.')
    if '[개인정보 가림]' in script or '[비속어 가림]' in script:
        errors.append('가림 표시는 방송하지 말고 해당 연락처·식별정보 표현을 삭제하세요.')
    limit = length_limit(segment)
    if limit and len(script.strip()) > limit:
        errors.append(f'대본이 {limit}자를 넘습니다.')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]|```|\[[^\]]*\]\(', script):
        errors.append('대본에 지원하지 않는 제어문자 또는 마크다운 형식이 있습니다.')
    return errors


def failure_details(script, segment):
    """Private diagnostics only: never retain raw contact/identifier matches."""
    if not isinstance(script, str):
        return dict(script=None, findings=[])
    safe = script
    findings = []
    for label, pattern in zip(('이메일', '전화번호 형식', '학번', '주민번호 형식'), PII):
        if pattern.search(safe):
            shapes = [re.sub(r'[\w]', 'X', match.group()) for match in pattern.finditer(safe)]
            findings.append(dict(rule='pii', kind=label, match='[가림]', shapes=shapes))
            safe = pattern.sub('[개인정보 가림]', safe)
    source = comparison_source(segment)
    missing = set(_numbers(safe)) - set(_numbers(source))
    for kind, *parts in sorted(missing, key=str):
        value = ':'.join(str(part) for part in parts)
        findings.append(dict(rule='number', kind=kind, match=value))
    if PROFANITY.search(safe):
        findings.append(dict(rule='profanity', match='[가림]'))
        safe = PROFANITY.sub('[비속어 가림]', safe)
    return dict(script=safe[:3500], findings=findings)
