"""공개 저장 자료에서 불필요한 식별정보만 가린다. 날짜·마감·조건은 유지한다."""
import re

MASK = '[개인정보 가림]'
ROSTER_ID = re.compile(r'(?<![\d*])(?:19|20)[\d*]{8}(?![\d*])')
PASSWORD = re.compile(r'((?:비밀번호|암호|PW\b)\s*[:：=]?\s*)[A-Za-z0-9_-]{3,}', re.I)
ROSTER_HEADER = re.compile(r'(?m)^\s*(?:연번|번호|학위과정|과정구분|단과대학|소속|성명|학번)\s*$')
TAGS = r'(?:\s|<[^>]*>)*'
STUDENT = re.compile(r'(학\s*번' + TAGS + r'[:：]?' + TAGS + r')(\d{8,12})(?!\d)')
NAME = re.compile(r'성\s*명' + TAGS + r'[:：]' + TAGS + r'([가-힣]{2,5})')
MOBILE = re.compile(r'(?<!\d)010[- .]?\d{4}[- .]?\d{4}(?!\d)')
RESIDENT = re.compile(r'(주민\s*등록\s*번호' + TAGS + r'[:：]?' + TAGS + r')\d{6}[- ]?[1-4]\d{6}(?!\d)')


def redact_text(text):
    if not isinstance(text, str):
        return text
    # 명단은 일부만 가린 식별자도 재공개하지 않는다.
    if '학번' in text and ROSTER_ID.search(text) and '<' not in text:
        header = ROSTER_HEADER.search(text)
        if header:
            text = text[:header.start()] + MASK
    if STUDENT.search(text):
        for name in NAME.findall(text):
            text = re.sub(r'(?<![가-힣])' + re.escape(name) + r'(?![가-힣])', MASK, text)
    if '학번' in text:
        text = ROSTER_ID.sub(MASK, text)
    text = STUDENT.sub(lambda m: m[1] + MASK, text)
    text = RESIDENT.sub(lambda m: m[1] + MASK, text)
    text = PASSWORD.sub(lambda m: m[1] + MASK, text)
    return MOBILE.sub(MASK, text)


def redact(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        result = {key: redact(item) for key, item in value.items()}
        title, body = result.get('title', ''), result.get('body')
        if isinstance(body, str) and (re.search(r'명단|선발.*(?:결과|공고)', title) or '대표학생' in body):
            names = re.findall(r'(?m)^(?:\d학년\s+)?([가-힣]{3})(?:\(\d+건\))?$', body)
            if len(names) >= 2:
                for name in names:
                    body = re.sub(r'(?<![가-힣])' + re.escape(name) + r'(?![가-힣])', MASK, body)
                result['body'] = body
        return result
    return value
