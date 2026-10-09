"""구간 분리 및 규칙 검수용 기준 문장. 동적 최종 대본은 slm.py가 생성한다."""
from datetime import date
import hashlib
import re
import json
import unicodedata
from difflib import SequenceMatcher
from briefing.review import PHONE
from collector.deadlines import extract_deadline


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def notice_text(notice):
    """중복 비교용 사본만 정리한다. 수집 원문과 모델 입력은 그대로 둔다."""
    title = unicodedata.normalize('NFC', notice['title'])
    title = re.sub(r'^\s*(?:(?:\[(?:안내|공지|공통|교직|대학원|학부|재안내)\])|[★☆■□●○◆◇※*])\s*', '', title)
    while re.match(r'^\s*(?:\[(?:안내|공지|공통|교직|대학원|학부|재안내)\]|[★☆■□●○◆◇※*])', title):
        title = re.sub(r'^\s*(?:\[(?:안내|공지|공통|교직|대학원|학부|재안내)\]|[★☆■□●○◆◇※*])\s*', '', title)
    body = unicodedata.normalize('NFC', notice.get('body') or '')
    body = re.sub(r'(?:첨부\s*파일\s*중\s*)?(?:PDF|이미지)\s*미리보기', '', body, flags=re.I)
    body = re.sub(r'\[붙임\s*참조\]', '', body)
    lines, attachments = [], False
    for line in body.splitlines():
        numbered = bool(re.match(r'^\s*\d+[.)]\s+', line))
        line = re.sub(r'^\s*(?:[★☆■□●○◆◇※]\s*|[*-]\s+|\d+[.)]\s+)', '', line).strip()
        if not line or line in ('끝.', '끝', '안녕하세요.', '안녕하세요'):
            continue
        if re.match(r'^(?:붙임|첨부)(?:파일)?\s*[:：]?', line) and re.search(r'\d+\s*부[.\s]*(?:끝[.]?)?$', line):
            attachments = True
            continue
        if attachments and numbered and re.search(r'\d+\s*부[.\s]*(?:끝[.]?)?$', line):
            continue
        attachments = False
        if re.match(r'^문의(?:처)?\s*[:：]', line) and (PHONE.search(line) or '@' in line) and not re.search(r'마감|기간|까지|신청|접수', line):
            continue
        lines.append(re.sub(r'\s+', ' ', line))
    return re.sub(r'\s+', ' ', title).strip(), '\n'.join(lines)


def notice_key(notice):
    title, body = notice_text(notice)
    if not body.strip() or ('[개인정보 가림]' in body and re.search(r'명단|이수현황|선발.*(?:결과|공고)', title)):
        return 'id:' + notice['id']
    return 'content:' + digest(json.dumps([title, re.sub(r'\s+', ' ', body), notice.get('deadline')], ensure_ascii=False))


def same_notice(left, right):
    # 명단을 가린 뒤 같아진 학과별 결과는 공통 공지로 묶지 않는다.
    if notice_key(left).startswith('id:') or notice_key(right).startswith('id:'):
        return False
    a_title, a = notice_text(left)
    b_title, b = notice_text(right)
    if not a or not b or a_title != b_title or left.get('deadline') != right.get('deadline'):
        return False
    # 숫자는 순서·횟수까지 보존한다. 표기/단위 차이도 보수적으로 별개로 둔다.
    if re.findall(r'\d[\d,.]*', a) != re.findall(r'\d[\d,.]*', b):
        return False
    protected = r'대상|자격|장소|제외|불가|미이수|명단|학과|전공|필수|선착순|확정|예정|취소|가능|않|없|한정|재학생|휴학생|졸업|대학원생|학부생|신입생|편입생|기간|마감|일시|신청|접수|제출'
    guards = lambda text: [line for line in text.splitlines() if re.search(protected, line)]
    if guards(a) != guards(b):
        return False
    a, b = re.sub(r'\s+', '', a), re.sub(r'\s+', '', b)
    if a == b:
        return True
    # ponytail: 같은 제목·숫자·조건의 100자 이상 본문만 90% 비교; 의미 판별은 하지 않는다.
    return min(len(a), len(b)) >= 100 and min(SequenceMatcher(None, a, b, autojunk=False).ratio(),
                                            SequenceMatcher(None, b, a, autojunk=False).ratio()) >= .9


def spoken_date(value):
    day = date.fromisoformat(value)
    return f'{day.month}월 {day.day}일'


def deadline_action(body, deadline):
    """Return a clearly labeled action attached to this date in the source body."""
    if not body or not deadline:
        return None
    year, month, day = deadline.split('-')
    date_pattern = re.compile(
        rf'(?<!\d){year}\s*(?:년|[./-])\s*{int(month)}\s*(?:월|[./-])\s*(?<!\d){int(day)}(?!\d)\s*일?'
    )
    for line in body.splitlines():
        match = date_pattern.search(line)
        if not match:
            continue
        prefix = line[:match.start()]
        if ':' not in prefix:
            continue
        label = prefix.rsplit(':', 1)[0].strip()
        label = re.sub(r'^(?:[가-힣]|\d+)[.)]\s*', '', label)
        label = re.sub(r'^[\s\-–—*\d.)]+', '', label).strip()
        if 2 <= len(label) <= 40:
            return label
    return None


def weather_script(weather, config, variant=0):
    """수치 대신 확인된 일일 예보로 생활 조언을 정한다. 시간대 예보는 추측하지 않는다."""
    choice = variant % 3
    if all(weather.get(k) is None for k in ('summary', 'temp_min', 'temp_max', 'rain_prob')):
        return '날씨 정보를 확인하지 못했어요. 출발 전에 최신 예보를 확인해 주세요.'
    summary = weather.get('summary')
    rain, low, high = (weather.get(k) for k in ('rain_prob', 'temp_min', 'temp_max'))
    rain_names = {'약한 이슬비', '이슬비', '강한 이슬비', '약한 어는 이슬비', '강한 어는 이슬비',
                  '약한 비', '비', '강한 비', '약한 어는 비', '강한 어는 비',
                  '약한 소나기', '소나기', '강한 소나기', '뇌우', '약한 우박 뇌우', '강한 우박 뇌우'}
    wet = summary in rain_names or (rain is not None and rain >= config['umbrella_rain_percent'])
    snowy = summary in {'약한 눈', '눈', '강한 눈', '약한 눈 소나기', '강한 눈 소나기', '눈 알갱이'}
    lines = []
    if snowy:
        lines.append('눈 예보가 있으니 따뜻하게 입고, 미끄러운 길을 조심하세요.')
    elif wet:
        lines.append(('비가 올 수 있으니 우산을 챙기고, 길이 미끄러울 수 있어 조심하세요.',
                      '우산을 가방에 넣어 두면 좋을 것 같아요. 비 오는 길에서는 천천히 걸어 주세요.',
                      '비 소식이 있어요. 우산을 준비하고 발걸음도 조심해 주세요.')[choice])
    if low is not None and low <= config['jacket_below_celsius']:
        lines.append(('아침엔 선선하니 얇은 겉옷 하나 챙기세요.',
                      '등굣길에는 겉옷 하나 걸치면 좋을 날씨예요.',
                      '아침 공기가 쌀쌀할 수 있으니 편하게 걸칠 겉옷을 준비해 주세요.')[choice])
    if low is not None and high is not None and high - low >= 10:
        lines.append(('일교차가 큰 날씨라 입고 벗기 편한 옷이 좋을 것 같아요.',
                      '낮과 아침의 온도 차이가 커서 옷차림을 조절하면 좋을 것 같아요.',
                      '일교차가 크니 낮에는 겉옷을 벗을 수 있게 준비해 보세요.')[choice])
    if not wet and not snowy and rain is not None and rain <= 20 and summary in {'맑음', '대체로 맑음'} and high is not None and 18 <= high <= 26:
        lines.append(('낮엔 바깥바람 쐬기 좋을 것 같아요.',
                      '맑고 낮에는 비교적 온화한 예보라 쉬는 시간에 바깥바람을 쐬어도 좋을 것 같아요.',
                      '낮에는 비교적 온화한 날씨라 짧게 산책하며 기분을 바꿔 봐도 좋을 것 같아요.')[choice])
    elif high is not None and high >= 28:
        lines.append('낮에는 더울 수 있으니 가볍게 입고 물도 챙겨 주세요.')
    if not lines:
        lines.append('출발 전 최신 예보를 확인하고 편한 옷차림으로 준비해 주세요.')
    return ' '.join(lines)


def create_segments(data, catalog, config, events, *, variant=None):
    day = date.fromisoformat(data['date'])
    # 날짜별로 말투를 바꾸되 같은 날 재실행에서는 캐시를 재사용한다.
    variant = int(digest(data['date'])[:8], 16) % 3 if variant is None else variant % 3
    segments = []
    warnings = list(data['errors'])

    def add(kind, title, script, channels=(), key=None, **extra):
        if not 1 <= len(script) <= 2000:
            raise ValueError(f'{title}: 대본은 1~2000자여야 합니다. 원문/설정을 확인하세요.')
        row = dict(id=digest(key or kind + script)[:24], kind=kind, title=title,
                   script=script, channel_ids=list(channels), audio={}, **extra)
        row['reference'] = script
        row['source_text'] = script
        row['required'] = [script]
        row['generation'] = 'fixed' if kind in {'greeting', 'outro', 'empty_notices', 'empty_meals'} else 'slm'
        segments.append(row)
        return row

    templates = config.get('greeting_templates', [])
    greeting = templates[variant % len(templates)] if templates else None
    row = add('greeting', '아침 인사', greeting.replace('{name}님. ', '') if greeting else config['greeting'])
    if greeting:
        row['personal_template'] = greeting
    row = add('weather', '날씨와 등교 안내', weather_script(data['weather'], config, variant))
    row['constraints'] = dict(max_chars=240, feedback_only=True)
    seen = {}
    grouped = {}
    names = {c['id']: c['name'] for c in catalog}
    for channel in data['channels']:
        cid = channel['channel_id']
        for notice in channel['notices']:
            nid = notice['id']
            ref = dict(channel_id=cid, postId=nid, title=notice['title'], url=notice['url'],
                       posted_at=notice['posted_at'], deadline=notice['deadline'], reason=notice['reason'])
            if nid in seen:
                previous, segment = seen[nid]
                if any(previous.get(k) != notice.get(k) for k in ('title', 'body', 'deadline')):
                    raise ValueError(f'공유 공지 내용 충돌: {nid}')
                if cid not in segment['channel_ids']:
                    segment['channel_ids'].append(cid)
                segment['notice_refs'].append(ref)
                continue
            key = notice_key(notice)
            if key not in grouped:
                key = next((candidate for candidate, prior in grouped.items()
                            if same_notice(prior[0], notice)), key)
            if key in grouped:
                segment = grouped[key][1]
                if cid not in segment['channel_ids']:
                    segment['channel_ids'].append(cid)
                segment['notice_refs'].append(ref)
                seen[nid] = notice, segment
                continue
            deadline_check = None
            deadline = notice['deadline']
            if deadline:
                parsed = extract_deadline(notice['title'], notice['body'] or '')
                metadata_evidence = any(any(word in line for word in ('게시일', '작성일', '등록일', '공고일'))
                                        for line in parsed['evidence'])
                verified = (parsed['status'] == 'found' and parsed['deadline'] == deadline
                            and not metadata_evidence)
                reason = parsed['reason']
                if metadata_evidence:
                    reason = '게시일·작성일 등 날짜와 함께 있어 마감 근거로 확정하지 않았습니다.'
                elif parsed['status'] == 'found' and parsed['deadline'] != deadline:
                    reason = f"원문 마감일 {parsed['deadline']}과 저장 마감일 {deadline}이 다릅니다."
                elif not verified and not reason:
                    reason = '원문에서 명시적 마감 근거를 찾지 못했습니다.'
                deadline_check = dict(notice_id=nid, title=notice['title'], url=notice['url'],
                                      posted_at=notice['posted_at'], deadline=deadline,
                                      parsed_deadline=parsed['deadline'], status=parsed['status'],
                                      verified=verified, evidence=parsed['evidence'], reason=reason)
                if not verified:
                    warnings.append(dict(source=cid, message=f"마감일을 원문에서 확인하지 못했습니다: {notice['title']}"))
                    deadline = None
                else:
                    deadline = parsed['deadline']
            action = deadline_action(notice.get('body'), deadline) if deadline else None
            # 완성 대본은 SLM이 작성한다. 검증된 날짜만 필수 문구로 전달한다.
            required = []
            deadline_phrase = (f"{spoken_date(deadline)}까지" if action else
                               f"{spoken_date(deadline)} 마감") if deadline else ''
            if deadline_phrase:
                required.append(deadline_phrase)
                if deadline == data['date']:
                    required.append('오늘')
            if action:
                required.append(action)
            if not notice['body']:
                required.append('제목만')
            reference = notice['title'] + (' ' + (action + ' ' if action else '') + deadline_phrase if deadline_phrase else '')
            if deadline == data['date']:
                reference += ' 오늘' if action else ' 오늘 마감'
            if not notice['body']:
                reference += ' 제목만 안내; 본문 미확인'
            segment = add('notice', notice['title'], reference, [cid], 'notice:' + key,
                          url=notice['url'], dday=(date.fromisoformat(deadline) - day).days if deadline else None,
                          source=notice['source'], notice_id=nid, deadline_verified=bool(deadline),
                          deadline_verification=deadline_check)
            segment['reference'] = reference
            segment['source_text'] = notice['title'] + '\n' + (notice['body'] or '')
            segment['required'] = required
            segment['generation'] = 'slm'
            common = {'학년도', '학기', '공통', '공지', '안내', '결과', '실시', '모집', '신청', '학생', '프로그램'}
            terms = [t for t in re.findall(r'[가-힣A-Za-z]{2,}', notice['title']) if t not in common]
            if not deadline:
                terms = [t for t in terms if not any(w in t for w in ('마감', '기한', '임박'))]
            segment['constraints'] = dict(max_chars=140, one_sentence=True, topic_terms=terms,
                                          no_contacts=True, title_only=not bool(notice['body']),
                                          deadline_unverified=not bool(deadline),
                                          verified_deadline=deadline_phrase or None,
                                          verified_today=bool(deadline and deadline == data['date']),
                                          deadline_action=action)
            segment['notice_refs'] = [ref]
            grouped[key] = notice, segment
            seen[nid] = notice, segment
        for i, meal in enumerate(channel['meals']):
            text = f"{meal['place']} 학식 메뉴입니다. {', '.join(meal['menu'])}."
            if meal['time']:
                text += f" 안내된 식사 시간은 {meal['time']}입니다."
            add('meal', meal['place'], text, [cid], f'meal:{cid}:{i}')
        if cid in names and not channel['meals'] and any(c['id'] == cid and c['type'] == 'meal' for c in catalog):
            row = add('meal', names[cid], f'{names[cid]}의 오늘 메뉴는 확인하지 못했어요. 식당 안내를 확인해 주세요.', [cid])
            row['generation'] = 'fixed'

    add('empty_notices', '공지 안내', '선택한 채널에서 이번에 안내할 공지는 없어요. 채널의 수집 상태도 확인해 주세요.')
    add('empty_meals', '학식 안내', '오늘은 선택한 학식 안내가 없어요. 식당을 선택하면 준비된 메뉴 안내를 들을 수 있어요.')
    upcoming = []
    # 수집 일정 가운데 시험·축제만 자동 포함. 대학원 전용 일정은 공통 방송에서 제외.
    for event in data['schedule']:
        if any(w in event['title'] for w in config['event_keywords']) and '대학원' not in event['title']:
            upcoming.append(dict(title=event['title'], date=event['start'], source_url=None))
    upcoming.extend(events)
    event_lines, event_items, event_keys = [], [], set()
    for event in sorted(upcoming, key=lambda e: (e['date'], e['title'])):
        start = date.fromisoformat(event['date'])
        remain = (start - day).days
        identity = (event['title'], event['date'])
        if identity in event_keys or not 0 <= remain <= config['event_horizon_days']:
            continue
        event_keys.add(identity)
        event_lines.append(f"{event['title']}이 오늘 시작돼요." if remain == 0 else f"{event['title']}까지 {remain}일 남았어요.")
        event_items.append(dict(event, dday=remain))
        if len(event_lines) >= config['max_events']:
            break
    text = '학교 주요 일정도 확인해 볼까요? ' + ' '.join(event_lines) if event_lines else '현재 확인된 시험·축제의 예정일 안내는 없어요. 공식 학사일정도 함께 확인해 주세요.'
    row = add('events', '학교 이벤트 D-day', text, events=event_items)
    if not event_items:
        row['generation'] = 'fixed'
    outros = config.get('outro_variants', [])
    add('outro', '마무리 인사', outros[variant % len(outros)] if outros else config['outro'])
    return segments, warnings
