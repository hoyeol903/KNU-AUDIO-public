"""Conservative notice-only cleanup for model input; stored source remains untouched."""
import html
import re
import unicodedata

NOISE_LINE = re.compile(r'^\s*(?:붙임|첨부(?:파일)?|다운로드|미리보기|파일명|조회수|이전글|다음글)\b', re.I)
URL = re.compile(r'https?://\S+|www\.\S+', re.I)


def without_parentheses(text):
    """Drop all content in nested ASCII/fullwidth parentheses, preserving line breaks."""
    text = text.translate(str.maketrans({'（': '(', '）': ')'}))
    output, depth = [], 0
    for char in text:
        if char == '\n':
            if depth:
                depth = 0
            output.append(char)
        elif char == '(':
            depth += 1
        elif char == ')':
            if depth:
                depth -= 1
        elif depth == 0:
            output.append(char)
    return re.sub(r'[ \t]{2,}', ' ', ''.join(output)).strip()


def clean_notice_text(text):
    """Remove parentheticals, markup, URLs and obvious attachment lines for SLM input only."""
    text = unicodedata.normalize('NFC', html.unescape(str(text or '')))
    text = without_parentheses(text)
    text = re.sub(r'<[^>]*>', ' ', text)
    text = URL.sub('', text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r'[ \t]+', ' ', line).strip()
        if not line or NOISE_LINE.match(line):
            continue
        lines.append(line)
    return '\n'.join(lines)
