"""구간 분리 및 규칙 검수용 기준 문장. 동적 최종 대본은 slm.py가 생성한다."""
from datetime import date
import hashlib
import re
import json
import unicodedata
from difflib import SequenceMatcher
from briefing.review import PHONE
from collector.deadlines import extract_deadline

NOTICE_STYLES = (
    '1안: 차분한 설명형으로 핵심부터 말하고 자연스러운 해요체로 끝내세요.',
    '2안: 친근한 안내형으로 학생에게 편하게 건네듯 자연스러운 해요체로 말하세요.',
    '3안: 맑고 생기 있는 아침 라디오 말투로, 과장 없이 자연스러운 해요체로 말하세요.',
)


def daily_variant(value):
    """Rotate 1→2→3 by calendar day, reproducibly within each date."""
    return (date.fromisoformat(value).toordinal() - 1) % len(NOTICE_STYLES)


def notice_topic(title):
    """Extract a compact, source-title topic for short summaries and fallback checks."""
    text = re.sub(r'\([^)]*\)|（[^）]*）', ' ', title or '')
    text = text.translate(str.maketrans({'[':' ', ']':' ', '【':' ', '】':' ', '『':' ', '』':' ', '「':' ', '」':' '}))
    text = text.lstrip()
    text = re.sub(r'^(?:안내|공지)\s+', '', text)
    text = re.sub(r'제\s*\d+\s*회|20\d{2}\s*(?:학년도?|년)|\d+\s*학기|\d+\s*차', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' -:：')
    text = re.sub(r'(?:안내|시행|신청|모집|참가|개최|행사|무료\s*참관\s*혜택)(?:\s*안내)?\s*$', '', text).strip(' -:：')
    matches = list(re.finditer(
        r'([가-힣A-Za-z· ]{1,28}?(?:적성\s*(?:및|·)\s*인성검사|산업전|체험교육|어학연수|경진대회|단체이용|워크숍|설명회))',
        text))
    match = matches[-1] if matches else None
    if match:
        phrase = re.sub(r'^(?:안내|학생|학년도|학기)\s+', '', match.group(1)).strip()
        phrase = re.sub(r'^제\s*\d+\s*회\s*', '', phrase)
        phrase = re.sub(r'\s*및\s*', '·', phrase)
        phrase = re.sub(r'\s+', ' ', phrase)
        if phrase.startswith('교직 '):
            phrase = phrase[len('교직 '):]
        if phrase.endswith('산업전'):
            phrase = '로봇산업전' if '로봇산업전' in phrase else re.search(r'[가-힣]{1,4}산업전$', phrase).group(0)
        elif phrase.endswith('어학연수'):
            phrase = '해외어학연수' if '해외어학연수' in phrase else phrase.split()[-1]
        else:
            phrase = ' '.join(phrase.split()[-3:])
        return phrase
    compact = re.sub(r'(?:신청|모집|참가|개최|시행|안내|행사|프로그램)\s*$', '', text).strip(' -:：')
    phrase = ' '.join(compact.split()[-3:])
    if re.sub(r'\s+', '', phrase) in {'공통', '모집', '신청', '안내', '공지', '프로그램', '학생'}:
        return None
    return phrase or None

def notice_fact_hints(body):
    """Keep complete original lines that label an action, audience, date, time or place."""
    if not body:
        return []
    source_lines = [re.sub(r'\s+', ' ', raw).strip() for raw in body.splitlines()]
    rows, seen = [], set()
    for index, line in enumerate(source_lines):
        if not line or len(line) > 300 or re.search(r'https?://|붙임|첨부파일|다운로드|\.pdf\b|\b1부\b|면접|확정 공고|승인서|기타사항', line, re.I):
            continue
        previous = source_lines[index - 1] if index else ''
        score = 0
        if '제외' in line and not re.search(r'대상|자격', line):
            continue
        is_target_label = bool(re.search(r'(?:이용)?대상|지원\s*자격|지원자격|참가\s*자격|신청\s*자격', line)) and not re.search(r'면접|확정', line)
        is_application_label = bool(re.search(r'(?:신청|지원|접수|모집)\s*(?:기간|일정|마감|방법)|등록\s*방법', line))
        if is_target_label:
            score = 11
        elif re.search(r'사전등록', line):
            score = 15
        elif re.search(r'(?:신청|지원|접수|모집).*(?:기간|마감|까지)|(?:기간|마감|까지).*(?:신청|지원|접수|모집)', line) and re.search(r'\d', line):
            score = 15
        elif is_application_label:
            score = 10
        elif re.search(r'(?:신청|접수).*(?:방법|공문|메일|온라인)|(?:방법|공문|메일|온라인).*(?:신청|접수)', line):
            score = 9
        elif re.search(r'20\d{2}', line) and re.search(r'에서|장소|개최|운영', line):
            score = 8
        elif re.search(r'대상|지원 자격|참가 자격', previous) and re.match(r'[-•▶\d가-하]', line):
            score = 8
        if is_application_label and re.fullmatch(r'.{1,24}(?:기간|일정|마감)\s*[:：]?', line):
            # Pair a standalone application heading with its next complete source line.
            following = source_lines[index + 1] if index + 1 < len(source_lines) else ''
            if following and len(following) <= 300 and not re.search(r'https?://|붙임|첨부파일|다운로드|\.pdf\b', following, re.I):
                rows.append((16, index + 1, following))
        if is_target_label and re.fullmatch(r'.{1,24}(?:대상|자격)\s*[:：]?', line):
            following = source_lines[index + 1] if index + 1 < len(source_lines) else ''
            if following and len(following) <= 300 and not re.search(r'https?://|붙임|첨부파일|다운로드|\.pdf\b', following, re.I):
                rows.append((12, index + 1, following))
        if score and line not in seen:
            rows.append((score, index, line))
            seen.add(line)
    ordered = []
    for _, _, line in sorted(rows, key=lambda row: (-row[0], row[1])):
        if line not in ordered:
            ordered.append(line)
        if len(ordered) == 8:
            break
    return ordered

def notice_generation_evidence(body, title=''):
    """Group a few complete source lines by purpose; this is not a truth parser."""
    lines = [re.sub(r'\s+', ' ', line).strip() for line in (body or '').splitlines()]
    cutoff = None
    submission = None
    target_values = []
    method_values = []
    event_values = []
    caveats = []
    required_documents_line = None
    target_pattern = re.compile(r'(?:이용|신청|지원|참가)?대상(?:자)?\s*[:：]\s*([^\n]+)|(?:지원|참가|신청)\s*자격\s*[:：]\s*([^\n]+)')
    for index, line in enumerate(lines):
        if not line:
            continue
        clean_line = re.sub(r'\s*\[?붙임\s*\d+.*$', '', line).strip()
        clean_line = re.sub(r'https?://\S+|www\.\S+', '', clean_line).strip()
        if not clean_line:
            continue
        stripped = re.sub(r'^(?:\s*(?:▶|•|[*\-–—]|\d+[.)]|[가-하][.)])\s*)+', '', clean_line).strip()
        following = lines[index + 1] if index + 1 < len(lines) else ''
        if cutoff is None and re.fullmatch(r'(?:신청|지원|접수|모집)\s*(?:기간|마감)\s*[:：]?', stripped) and re.search(r'\d', following):
            cutoff = clean_line + ' ' + following
        elif cutoff is None and re.search(r'사전등록|(?:신청|지원|접수|모집)\s*(?:기간|마감)', clean_line) and re.search(r'\d', clean_line):
            cutoff = clean_line

        matches = target_pattern.search(clean_line)
        if matches:
            value = next((item for item in matches.groups() if item), '').strip()
            if value:
                target_values.append((clean_line, value))
            elif re.fullmatch(r'(?:이용|신청|지원|참가)?대상(?:자)?\s*[:：]?|(?:지원|참가|신청)\s*자격\s*[:：]?', stripped):
                matches = None
        if not matches and re.fullmatch(r'(?:이용|신청|지원|참가)?대상(?:자)?\s*[:：]?|(?:지원|참가|신청)\s*자격\s*[:：]?', stripped) and index + 1 < len(lines):
            following_lines = []
            for candidate in lines[index + 1:index + 4]:
                candidate_label = re.sub(r'^(?:\s*(?:▶|•|[*\-–—]|\d+[.)]|[가-하][.)])\s*)+', '', candidate).strip()
                if (re.match(r'^\s*(?:▶|[가-하][.)])', candidate)
                        or re.fullmatch(r'.*(?:기간|방법|일시|장소)\s*[:：]?', candidate_label)):
                    break
                if candidate:
                    following_lines.append(candidate)
                if len(following_lines) == 2:
                    break
            if following_lines:
                target_values.append((clean_line + ' ' + ' '.join(following_lines), ' '.join(following_lines)))
        elif '대상으로' in clean_line:
            value = re.split(r'(?:을|를)\s*대상으로', clean_line)[0]
            target_values.append((clean_line, value))

        is_method = re.search(r'(?:신청|지원|접수|등록|제출)\s*방법|통합정보시스템|구글폼|공문으로\s*접수|신청서\s*메일', clean_line)
        if not is_method and method_values and '이메일' in ' '.join(method_values) and re.search(r'또는\s*(?:링크|QR)', clean_line):
            is_method = True
        method_heading = re.fullmatch(r'(?:신청|지원|접수|등록|제출)\s*방법\s*[:：]?', stripped)
        if is_method and not method_heading and not re.search(r'하지\s*않|불가|\b1부\b|붙임', clean_line):
            method_values.append(re.sub(r'\s*\[?붙임\s*\d+.*$', '', clean_line).strip())
        if re.search(r'(?:검사|행사|연수|운영)\s*(?:일시|기간|장소)|(?:검사|행사|연수)\s*장소|대구\s*엑스코|글로벌플라자', clean_line):
            event_values.append(clean_line)
        if (required_documents_line is None
                and re.search(r'제출\s*서류', clean_line)
                and re.search(r'필수\s*제출|제출\s*서류.{0,100}필수|필수.{0,100}제출\s*서류', clean_line)):
            required_documents_line = clean_line
        if re.search(r'조기\s*종료|신청\s*기간.{0,12}상이|등록횟수에\s*따라|휴학생\s*제외|모두\s*제출|양쪽.*제출|'
                     r'대구\s*청년\s*연구자|팀원\s*중\s*\d+%|석사\s*재학생\s*이상|'
                     r'주민등록상\s*주소지가\s*대구|대구광역시\s*거주|'
                     r'참가팀\s*구성|팀원.{0,15}(?:\d+%|절반)|대구.*(?:주민등록|거주)|석사.*(?:재학|이상)|'
                     r'개인\s*신청\s*시|팀\s*신청\s*시|대표자.{0,20}(?:자격|요건)|창업\s*\d+년\s*이내|만\s*\d+세\s*이하', clean_line):
            caveats.append(clean_line)

    # A compact “신청마감” heading can omit the actual submission time and destination.
    # Prefer a same-date, explicit submit instruction only when it includes a clock time
    # and a concrete office; unrelated event or later follow-up dates are not substituted.
    if cutoff:
        date_pattern = re.compile(
            r'(?<!\d)(?:20\d{2}\s*(?:년|[./-])\s*)?(\d{1,2})\s*(?:월|[./-])\s*(\d{1,2})\s*일?')
        cutoff_dates = {(int(month), int(day)) for month, day in date_pattern.findall(cutoff)}
        if cutoff_dates:
            mandatory_docs = bool(re.search(r'필수\s*제출|필수\s*제출서류|제출서류.{0,60}필수', body or ''))
            for line in lines:
                clean_line = re.sub(r'https?://\S+|www\.\S+', '', line).strip()
                line_dates = {(int(month), int(day)) for month, day in date_pattern.findall(clean_line)}
                if not (cutoff_dates & line_dates):
                    continue
                if not re.search(r'\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?\s*까지', clean_line):
                    continue
                if not re.search(r'(?:제출|접수|신청)', clean_line):
                    continue
                place_match = re.search(
                    r'(?P<place>(?:[가-힣A-Za-z0-9·]{1,10}(?:학부|학과|대학|본부)\s*)?(?:학부|학과)?사무실|'
                    r'[가-힣A-Za-z0-9·]{2,12}(?:행정실|지원센터|센터))\s*(?:로|으로)\s*(?:제출|접수)',
                    clean_line)
                if not place_match:
                    continue
                place = re.sub(r'\s+', '', place_match.group('place'))
                documents_named = bool(re.search(r'제출\s*서류', clean_line))
                action_match = re.search(r'(제출|접수|신청)', clean_line)
                submission = dict(line=clean_line, place=place,
                                  required_documents=documents_named and mandatory_docs,
                                  documents_named=documents_named,
                                  action=action_match.group(1) if action_match else '제출')
                cutoff = clean_line
                break

    target = target_values[0][0] if target_values else None
    audience_values = [value for _, value in target_values if value]
    method = ' '.join(dict.fromkeys(method_values)) or None
    event = ' '.join(dict.fromkeys(event_values[:2])) or None
    lines_out = []
    for line in (cutoff, target, method, event, required_documents_line, *caveats):
        if line and line not in lines_out:
            lines_out.append(line)
    intent = 'event' if re.search(r'시행|행사|개최|일정|일시', title) and not re.search(r'신청|모집|접수|지원', title) else 'application'
    return {
        'intent': intent,
        'topic': notice_topic(title),
        'cutoff': cutoff,
        'audience': target,
        'audience_values': audience_values,
        'method': method,
        'event': event,
        'caveats': caveats,
        'submission': submission,
        'required_documents': bool(required_documents_line),
        'required_documents_line': required_documents_line,
        'lines': lines_out[:6],
    }

def notice_required_anchors(evidence):
    """Build conservative omission checks for explicit cutoff dates/times and source conditions."""
    cutoff = evidence.get('cutoff') or ''
    dates = re.findall(r'(?<!\d)(?:\d{4}\s*[./-]\s*)?(\d{1,2})\s*(?:월|[./-])\s*(\d{1,2})\s*일?', cutoff)
    if dates:
        cutoff_day = str(int(dates[-1][1]))
    else:
        days = re.findall(r'(?<!\d)(\d{1,2})\s*일', cutoff)
        cutoff_day = str(int(days[-1])) if days else None
    variable_period = bool(evidence.get('intent') == 'application' and any(
        re.search(r'등록횟수에\s*따라|신청\s*기간.{0,12}상이|신청기간.{0,12}다르', item)
        for item in evidence.get('caveats', [])))
    cutoff_times = []
    for meridiem, hour, minute, minute_word in re.findall(
            r'(오전|오후|아침|저녁|밤|낮)?\s*(\d{1,2})\s*(?::\s*(\d{2})|시(?:\s*(\d{1,2})\s*분)?)', cutoff):
        hour, minute = int(hour), int(minute or minute_word or 0)
        if meridiem and 1 <= hour <= 12:
            if meridiem in ('오후', '저녁', '낮'):
                hour = hour % 12 + 12
            elif meridiem == '밤':
                hour = 0 if hour == 12 else hour + 12
            else:
                hour %= 12
        item = [hour, minute]
        if item not in cutoff_times:
            cutoff_times.append(item)
    if cutoff_times and not variable_period:
        # For an application window, the closing time is the short-script anchor.
        cutoff_times = cutoff_times[-1:]
    cutoff_date_parts = [(int(month), int(day)) for month, day in re.findall(
        r'(?<!\d)(?:20\d{2}\s*(?:년|[./-])\s*)?(\d{1,2})\s*(?:월|[./-])\s*(\d{1,2})\s*일?', cutoff)]
    range_match = re.search(r'(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일?\s*[~∼〜～–—-]\s*(\d{1,2})\s*일', cutoff)
    if range_match:
        month, start_day, end_day = map(int, range_match.groups())
        cutoff_date_parts = [(month, start_day), (month, end_day)]

    event = evidence.get('event') or ''
    event_days = []
    for match in re.finditer(r'(?<!\d)(?:\d{4}\s*[./-]\s*)?(\d{1,2})\s*(?:월|[./-])\s*(\d{1,2})\s*일?', event):
        event_days.append(str(int(match.group(2))))
    if not event_days:
        event_days = [str(int(day)) for day in re.findall(r'(?<!\d)(\d{1,2})\s*일', event)]
    event_times = []
    if evidence.get('intent') == 'event':
        for meridiem, hour, minute, minute_word in re.findall(
                r'(오전|오후|아침|저녁|밤|낮)?\s*(\d{1,2})\s*(?::\s*(\d{2})|시(?:\s*(\d{1,2})\s*분)?)', event):
            hour, minute = int(hour), int(minute or minute_word or 0)
            if meridiem and 1 <= hour <= 12:
                hour = hour % 12 + 12 if meridiem in ('오후', '저녁', '낮') else (0 if hour == 12 else hour + 12) if meridiem == '밤' else hour % 12
            item = [hour, minute]
            if item not in event_times:
                event_times.append(item)
        event_days += [str(int(day)) for day in re.findall(r'(?<!\d)(\d{1,2})\s*(?=\s*\([^)]*[월화수목금토일]\))', event)
                       if str(int(day)) not in event_days]
        event_days += [str(int(day)) for day in re.findall(
            r'(?:월\s*\d{1,2}\s*일?|(?<![:\d])\d{1,2}\s*일)\s*[~∼〜～–—-]\s*(\d{1,2})\s*일?', event)
                       if str(int(day)) not in event_days]

    audience_values = list(dict.fromkeys(evidence.get('audience_values') or []))
    audience = audience_values[0] if len(audience_values) == 1 else ''
    neutral_audience = (not audience or bool(re.search(
        r'제외|포함|복수전공|부전공|타학과|및|또는|총\s*선발|최대|조건에\s*따라', audience)))
    audience_terms = []
    for term in re.findall(r'[가-힣A-Za-z]{2,}', audience):
        if term in {'대상', '이용대상', '지원자격', '참가자격', '신청자격', '관련', '전공', '본교', '학생', '포함', '가능', '신청', '지원', '휴학생', '제외', '및', '또는', '검사', '인원', '대학'}:
            continue
        term = re.sub(r'(?:은|는|이|가|을|를|들|에|에서)$', '', term)
        if term not in audience_terms:
            audience_terms.append(term)
    audience_terms = audience_terms[:2] if not neutral_audience else []
    audience_qualifiers = ['선착순'] if re.search(r'선착순', (evidence.get('audience') or '') + ' ' + cutoff) else []

    method = evidence.get('method') or ''
    method_groups = []
    method_routes = []
    method_must_include = []
    route_qualifiers = []
    if evidence.get('intent') == 'event' and '사전등록' not in cutoff:
        method_groups = []
    elif (('대학 및 학과행사' in method or '대학·학과행사' in method)
          and '공문' in method and '동아리행사' in method and '메일' in method):
        method_routes = [['대학', '공문'], ['동아리', '메일']]
        if '대학에서 취합' in method:
            route_qualifiers = [['대학', '취합']]
    elif '통합정보시스템' in method:
        method_groups.append(['통합정보시스템', '통합정보'])
    elif '구글폼' in method and '이메일' in method:
        method_groups.extend([['구글폼'], ['이메일']])
    elif '공문으로 접수' in method and '메일' in method:
        method_groups.extend([['공문'], ['메일']])
    elif '이메일' in method and '링크' in method and '또는' in method:
        method_groups.append(['이메일', '링크'])
    elif '사전등록' in method:
        method_groups.append(['사전등록', '등록'])

    if '링크' in method and '개별' in method and ('사전등록' in method or '등록방법' in method):
        method_must_include.extend(['링크', '개별'])
    if '이메일' in method and '링크' in method and '또는' in method:
        method_must_include.extend(['이메일', '링크'])
    method_must_include = list(dict.fromkeys(method_must_include))

    required_caveats = []
    for caveat in (evidence.get('caveats', []) if evidence.get('intent') != 'event' else []):
        if '조기 종료' in caveat:
            if ['조기 종료', '조기 마감', '조기마감'] not in required_caveats:
                required_caveats.append(['조기 종료', '조기 마감', '조기마감'])
        if '등록횟수에 따라' in caveat or '신청 기간' in caveat and '상이' in caveat:
            if ['등록횟수', '등록 횟수'] not in required_caveats:
                required_caveats.append(['등록횟수', '등록 횟수'])
        if '모두 제출' in caveat or '양쪽' in caveat:
            if ['모두 제출', '둘 다 제출', '모두 신청'] not in required_caveats:
                required_caveats.append(['모두 제출', '둘 다 제출', '모두 신청'])
        if '휴학생 제외' in caveat and not neutral_audience:
            if ['휴학생 제외'] not in required_caveats:
                required_caveats.append(['휴학생 제외'])
        if '대구 청년 연구자' in caveat:
            required_caveats.append(['대구 청년 연구자', '청년 연구자'])
        member_share = re.search(r'팀원\s*중\s*(\d+)%', caveat)
        if member_share:
            amount = member_share.group(1)
            required_caveats.append([f'팀원 중 {amount}%', f'팀원 {amount}% 이상', f'{amount}% 이상'])
        if '석사 재학생 이상' in caveat:
            required_caveats.append(['석사 재학생 이상', '석사 이상'])
        if '주소지가 대구' in caveat or '대구광역시 거주' in caveat:
            required_caveats.append(['주소지가 대구', '대구광역시 거주', '대구 거주'])
        if '개인 신청 시' in caveat:
            required_caveats.append(['개인 신청', '개인으로 신청'])
        if '팀 신청 시' in caveat:
            required_caveats.append(['팀 신청', '팀으로 신청'])
        age_limit = re.search(r'만\s*(\d+)\s*세\s*이하', caveat)
        if age_limit:
            required_caveats.append([f'{age_limit.group(1)}세 이하', f'만 {age_limit.group(1)}세'])
        company_years = re.search(r'창업\s*(\d+)\s*년\s*이내', caveat)
        if company_years:
            required_caveats.append([f'창업 {company_years.group(1)}년 이내'])
        if '대표자' in caveat:
            required_caveats.append(['대표자'])

    place_terms = []
    for term in re.findall(r'[가-힣A-Za-z0-9· ]{2,24}(?:플라자|엑스코|센터|회관)', event):
        term = term.strip()
        if term not in place_terms:
            place_terms.append(term)

    if variable_period and ['신청 기간 상이', '등록횟수별'] not in required_caveats:
        required_caveats.append(['신청 기간 상이', '등록횟수별'])
    preserve_cutoff = bool(cutoff and not variable_period and (evidence.get('intent') != 'event' or '사전등록' in cutoff))
    free_offer = bool(re.search(r'무료', cutoff) and evidence.get('intent') == 'event')
    submission = evidence.get('submission') or {}
    return dict(deadline_day=cutoff_day if evidence.get('intent') != 'event' else (event_days[0] if event_days else None),
                deadline_times=cutoff_times if evidence.get('intent') != 'event' else event_times or cutoff_times,
                cutoff_day=cutoff_day if preserve_cutoff else None,
                cutoff_times=cutoff_times if preserve_cutoff else [],
                must_preserve_cutoff=preserve_cutoff,
                audience_terms=audience_terms, neutral_audience=neutral_audience,
                audience_qualifiers=audience_qualifiers, variable_period=variable_period,
                cutoff_date_parts=cutoff_date_parts if variable_period else [],
                method_groups=method_groups, method_routes=method_routes,
                method_must_include=method_must_include, method_route_qualifiers=route_qualifiers,
                free_offer=free_offer,
                submission_place=submission.get('place'),
                submission_documents=bool(evidence.get('required_documents') or submission.get('required_documents')),
                topic=evidence.get('topic'),
                caveat_groups=required_caveats,
                event_days=event_days if evidence.get('intent') == 'event' else [],
                event_times=event_times if evidence.get('intent') == 'event' else [],
                place_terms=place_terms if evidence.get('intent') == 'event' else [],
                intent=evidence.get('intent', 'application'))

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
    variant = daily_variant(data['date']) if variant is None else variant % len(NOTICE_STYLES)
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
    # Names are displayed in the profile UI only. The briefing greeting stays on
    # the same generated Sohee voice as every other audio segment.
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
            segment['style_instruction'] = NOTICE_STYLES[variant]
            segment['constraints'] = dict(sentence_count=(1, 2), topic_terms=terms,
                                          no_contacts=True, title_only=not bool(notice['body']),
                                          deadline_unverified=not bool(deadline),
                                          verified_deadline=deadline_phrase or None,
                                          verified_today=bool(deadline and deadline == data['date']),
                                          deadline_action=action,
                                          required_action=bool(action and re.search(r'신청|접수|지원|등록|제출', action)))
            evidence = notice_generation_evidence(notice.get('body') or '', notice['title'])
            segment['fact_hints'] = notice_fact_hints(notice.get('body') or '')
            segment['generation_evidence'] = evidence
            segment['constraints']['required_source_facts'] = notice_required_anchors(evidence)
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
