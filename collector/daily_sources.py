"""대구 날씨·생협 식당·공식 학사일정을 수집한다."""
import argparse
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from bs4 import BeautifulSoup

from collector.http import Client, FetchError
from collector.knu_cms import ParseError
from collector.store import SEOUL, load_collection_report, save_collection_report

ROOT = Path(__file__).resolve().parents[1]
MEAL_TABLE = 'table.tstyle_me'
MEAL_DATES = '.week_t'
MEAL_ITEMS = 'ul.menu_im > li'
SCHEDULE_MONTHS = 'dl'
SCHEDULE_ITEMS = 'dd.list li'
SCHEDULE_DAY = 'span.day'
MEAL_SOURCES = {
    'meal-46': 'GP감꽃식당', 'meal-35': '정보센터식당',
    'meal-85': '공학관교직원식당(외부업체)', 'meal-86': '공학관학생식당(외부업체)',
    'meal-bokji': '복지관 교직원식당', 'meal-37': '카페테리아 첨성',
}
MEAL_SHOP_IDS = {'meal-bokji': '36'}
SCHEDULE_URL = 'https://www.knu.ac.kr/wbbs/wbbs/user/yearSchedule/index.action?menu_idx=43&vo.search_year='
# Open-Meteo 지명 검색의 KR/Daegu 결과. 캠퍼스 관측값이 아니라 대구 대표 지역 예보다.
WEATHER_LOCATION = dict(latitude=35.87028, longitude=128.59111)
WEATHER_CODES = dict(zip(
    [0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 97, 99],
    ['맑음', '대체로 맑음', '부분적으로 흐림', '흐림', '안개', '착빙 안개', '약한 이슬비', '이슬비', '강한 이슬비',
     '약한 어는 이슬비', '강한 어는 이슬비', '약한 비', '비', '강한 비', '약한 어는 비', '강한 어는 비',
     '약한 눈', '눈', '강한 눈', '싸락눈', '약한 소나기', '소나기', '강한 소나기', '약한 눈 소나기',
     '강한 눈 소나기', '뇌우', '약한 우박을 동반한 뇌우', '강한 뇌우', '강한 우박을 동반한 뇌우']))
HOURS = re.compile(r'(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d\s*[~～]\s*(?:[01]?\d|2[0-3]):[0-5]\d(?!\d)')
PRICE = re.compile(r'[￦₩]\s*(\d[\d,]*)|(?<![\d,])(\d[\d,]*)\s*원')
PERIOD = re.compile(r'(?<![\d.])(?:(\d{4})\.)?(\d{1,2})\.(\d{1,2})\.?\s*[~～]\s*(?:(\d{4})\.)?(\d{1,2})\.(\d{1,2})\.?')


def parse_weather(payload, day):
    try:
        daily, units = payload['daily'], payload['daily_units']
        if payload['utc_offset_seconds'] != 32400 or daily['time'] != [day.isoformat()]:
            raise ParseError('날씨 응답 날짜·한국 시간대 불일치')
        values = {}
        for name, unit in [('weather_code', 'wmo code'), ('temperature_2m_min', '°C'),
                           ('temperature_2m_max', '°C'), ('precipitation_probability_max', '%')]:
            if units[name] != unit or not isinstance(daily[name], list) or len(daily[name]) != 1:
                raise ParseError('날씨 단위·배열 불일치: ' + name)
            v = daily[name][0]
            if type(v) not in (int, float) or not math.isfinite(v):
                raise ParseError('날씨 값 누락·자료형 오류: ' + name)
            values[name] = v
        code = values['weather_code']
        if type(code) is not int or code not in WEATHER_CODES:
            raise ParseError('알 수 없는 날씨 코드')
        lo, hi, prob = (values[k] for k in ['temperature_2m_min', 'temperature_2m_max', 'precipitation_probability_max'])
        if lo > hi or not 0 <= prob <= 100:
            raise ParseError('날씨 값 범위 오류')
        return dict(summary=WEATHER_CODES[code], temp_min=lo, temp_max=hi, rain_prob=prob)
    except (KeyError, TypeError) as exc:
        raise ParseError('날씨 JSON 구조 변경') from exc


class Unpublished(ParseError):
    """표는 읽었지만 그 날짜 메뉴가 올라오지 않았다. 구조를 못 읽은 실패와 구분한다."""


def _meal_tables(html, place):
    soup = BeautifulSoup(html, 'html.parser')
    if place not in [h.get_text(' ', strip=True) for h in soup.select('h2')]:
        raise ParseError('요청한 식당 이름을 확인할 수 없습니다')
    tables = soup.select(MEAL_TABLE)
    if not tables:
        raise ParseError('주간 식단 표를 찾을 수 없습니다')
    return tables, [x.get_text(strip=True) for x in tables[0].select(MEAL_DATES)]


def _is_food(line):
    return bool(line) and not (re.search(r'[￦₩]|\d[\d,]*\s*원', line) or HOURS.search(line) or line in {'운영시간', '자율배식', '1식4찬'})


def _meal_column(tables, dates, col, place):
    """한 날짜의 메뉴. place·time·menu에 끼니(label)·가격(price)·대표 이름 줄 수(head)를 더한다."""
    meals, closed = [], False
    if len(tables) == 1:
        raise ParseError('날짜 표만 있고 식단 표가 없습니다')
    for table in tables[1:]:
        cells = table.select('tbody td')
        if len(cells) != len(dates) or not table.caption:
            raise ParseError('식단 표 열 수·식사 구분 변경')
        cell = cells[col]
        entries = cell.select(MEAL_ITEMS)
        if not entries:
            if cell.get_text(' ', strip=True) in {'휴무', '휴무일', '운영하지 않음'}:
                closed = True
                continue
            raise Unpublished(table.caption.get_text(strip=True) + ': 오늘 메뉴 미게시, 휴무 여부 미확인')
        for li in entries:
            text = li.get_text('\n', strip=True)
            if re.fullmatch(r'(휴무|휴무일|운영하지 않음)', text):
                closed = True
                continue
            hours = list(dict.fromkeys(HOURS.findall(text)))
            menu = [line for line in map(str.strip, text.splitlines()) if _is_food(line)]
            if not menu:
                raise ParseError('메뉴 항목이 있지만 음식 이름을 읽지 못했습니다')
            # 항목 바로 아래 글자는 대표 음식 이름, <p> 안은 곁들임이다. 순서가 다르면 구분하지 않는다.
            named = [line for node in li.children if isinstance(node, str) for line in [node.strip()] if _is_food(line)]
            price = PRICE.search(text)
            meals.append(dict(place=place, time=','.join(re.sub(r'\s', '', value) for value in hours) or None, menu=menu,
                              label=table.caption.get_text(strip=True), price=int((price[1] or price[2]).replace(',', '')) if price else None,
                              head=len(named) if named and menu[:len(named)] == named else 0))
    if not meals and not closed:
        raise Unpublished('오늘 메뉴 미게시: 휴무 여부는 확인할 수 없습니다')
    return meals


def parse_meals(html, day, place):
    tables, dates = _meal_tables(html, place)
    target = '(' + day.strftime('%m/%d') + ')'
    if dates.count(target) != 1:
        raise ParseError('요청 날짜의 식단 열을 확인할 수 없습니다')
    # items.json 계약의 식단은 place·time·menu뿐이다. 끼니·가격은 meal_week에만 싣는다.
    return [dict(place=meal['place'], time=meal['time'], menu=meal['menu'])
            for meal in _meal_column(tables, dates, dates.index(target), place)]


def parse_meal_week(html, day, place):
    """같은 주간 표의 모든 날짜를 추가 요청 없이 읽는다. 미게시·휴무는 empty, 그 날짜만 못 읽으면 failed."""
    tables, dates = _meal_tables(html, place)
    week = []
    for col, label in enumerate(dates):
        match = re.fullmatch(r'\((\d{2})/(\d{2})\)', label)
        if not match:
            raise ParseError('식단 표 날짜 표기 변경')
        # 표에는 연도가 없다. 요청 날짜와 가장 가까운 해로 읽어 연말·연초 주간을 처리한다.
        when = min((date(year, int(match[1]), int(match[2])) for year in (day.year - 1, day.year, day.year + 1)),
                   key=lambda value: abs(value - day))
        try:
            meals = _meal_column(tables, dates, col, place)
            status = 'ok' if meals else 'empty'
        except Unpublished:
            meals, status = [], 'empty'
        except ParseError:
            meals, status = [], 'failed'
        week.append(dict(date=when.isoformat(), status=status, meals=meals))
    return week


def parse_schedule(html, year):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for dl in soup.select(SCHEDULE_MONTHS):
        dt = dl.find('dt')
        if not dt:
            continue
        month = re.fullmatch(r'\s*(\d{4})년\s*(\d{1,2})월\s*', dt.get_text(' ', strip=True))
        if not month:
            continue
        y, m = map(int, month.groups())
        if y != year:
            raise ParseError('학사일정 요청 연도와 본문 연도가 다릅니다')
        for li in dl.select(SCHEDULE_ITEMS):
            span = li.select_one(SCHEDULE_DAY)
            match = re.fullmatch(r'(\d{2})\.(\d{2})\([월화수목금토일]\)', span.get_text(strip=True)) if span else None
            if not match or int(match[1]) != m:
                raise ParseError('학사일정 시작 날짜 구조 변경')
            start = date(y, m, int(match[2]))
            span.decompose()
            title = li.get_text(' ', strip=True)
            if not title:
                raise ParseError('학사일정 제목 누락')
            end = None
            periods = list(PERIOD.finditer(title))
            if len(periods) > 1:
                raise ParseError('여러 일정 기간: 원문 확인 필요')
            if periods:
                sy, sm, sd, ey, em, ed = periods[0].groups()
                if date(int(sy or y), int(sm), int(sd)) != start:
                    raise ParseError('학사일정 시작일과 설명의 기간 불일치')
                end = date(int(ey or y), int(em), int(ed))
                if end < start:
                    raise ParseError('학사일정 종료 연도 미확인')
            elif '~' in title or '～' in title:
                raise ParseError('학사일정 기간을 읽지 못했습니다')
            # 종료일이 원문에 없으면 단일 시작 날짜로 종료를 추정하지 않는다.
            rows.append(dict(title=title, start=start.isoformat(), end=end.isoformat() if end else None))
    if not rows:
        raise ParseError('학사일정 목록을 찾지 못했습니다')
    return rows


def collect(client, day, *, fixtures=None, include_extras=True, include_meals=True):
    requests_before = getattr(client, 'request_count', 0)
    result = dict(date=day.isoformat(), collected_at=datetime.now(SEOUL).isoformat(),
                  weather=dict(summary=None, temp_min=None, temp_max=None, rain_prob=None),
                  channels=[], schedule=[], schedule_year=[], errors=[], sources=[], meal_week={})
    if fixtures:
        fixtures.mkdir(parents=True, exist_ok=True)
    params = dict(WEATHER_LOCATION, daily='weather_code,temperature_2m_min,temperature_2m_max,precipitation_probability_max',
                  timezone='Asia/Seoul', start_date=day.isoformat(), end_date=day.isoformat())
    sources = []
    if include_extras:
        sources.append(('weather', 'https://api.open-meteo.com/v1/forecast?' + urlencode(params)))
    if include_meals:
        sources.extend((key, 'https://coop.knu.ac.kr/sub03/sub01_01.html?' + urlencode(dict(
            shop_sqno=MEAL_SHOP_IDS.get(key, key.removeprefix('meal-')), selDate=day.isoformat()))) for key in MEAL_SOURCES)
    if include_extras:
        sources.extend(('schedule', SCHEDULE_URL + str(y)) for y in sorted({day.year, (day + timedelta(days=3)).year}))
    for key, url in sources:
        channel = None
        if key in MEAL_SOURCES:
            channel = dict(channel_id=key, notices=[], meals=[])
            result['channels'].append(channel)
        try:
            raw, final = client.get_json(url) if key == 'weather' else client.get(url)
            if channel is not None:
                final_parts = urlsplit(final)
                if (final_parts.scheme not in {'http', 'https'}
                        or final_parts.hostname != 'coop.knu.ac.kr'
                        or final_parts.path != '/sub03/sub01_01.html'):
                    raise FetchError(f'식당 원문과 다른 주소로 이동했습니다: {final}')
            if fixtures:
                name = key + ('-' + url.rsplit('=', 1)[1] if key == 'schedule' else '')
                if key == 'weather':
                    save_collection_report(raw, fixtures / (name + '.json'))
                else:
                    (fixtures / (name + '.html')).write_text(raw, encoding='utf-8')
            result['sources'].append(dict(source=key, url=final, checked_at=datetime.now(SEOUL).isoformat()))
            if key == 'weather':
                result['weather'] = parse_weather(raw, day)
            elif channel is not None:
                try:
                    result['meal_week'][key] = parse_meal_week(raw, day, MEAL_SOURCES[key])
                except ParseError:
                    pass  # 주간 표를 못 읽은 이유는 아래 오늘 식단 오류로 남는다.
                channel['meals'] = parse_meals(raw, day, MEAL_SOURCES[key])
            else:
                for row in parse_schedule(raw, int(url.rsplit('=', 1)[1])):
                    # 앱 달력용: 받은 해의 학사일정 전체를 그대로 둔다. 브리핑 입력은 아래 가까운 일정만 쓴다.
                    result['schedule_year'].append(row)
                    start = date.fromisoformat(row['start'])
                    end = date.fromisoformat(row['end']) if row['end'] else start
                    if day <= start <= day + timedelta(days=3) or start <= day <= end:
                        result['schedule'].append(dict(row, dday=(start-day).days))
        except (FetchError, ValueError, TypeError) as exc:
            result['errors'].append(dict(source=key, message=str(exc)))
    result['schedule'].sort(key=lambda r: (r['start'], r['title']))
    result['schedule_year'].sort(key=lambda r: (r['start'], r['title']))
    result['collected_at'] = datetime.now(SEOUL).isoformat()
    result['request_count'] = getattr(client, 'request_count', 0) - requests_before
    return result


def _source_group(source):
    if source in {'weather', 'schedule'}:
        return source
    if source in MEAL_SOURCES:
        return 'meals'
    return None


def merge_context(previous, fresh, *, include_extras=True, include_meals=True):
    if previous is None:
        return fresh
    if previous.get('date') != fresh.get('date'):
        raise ValueError('다른 날짜의 context는 병합할 수 없습니다')
    replaced = ({'weather', 'schedule'} if include_extras else set()) | ({'meals'} if include_meals else set())
    merged = dict(fresh)
    if not include_extras:
        merged['weather'] = previous['weather']
        merged['schedule'] = previous['schedule']
        merged['schedule_year'] = previous.get('schedule_year', [])
    if not include_meals:
        merged['channels'] = list(previous['channels']) + list(fresh['channels'])
        merged['meal_week'] = previous.get('meal_week', {})
    for key in ('sources', 'errors'):
        kept = [row for row in previous[key] if _source_group(row['source']) not in replaced]
        added = [row for row in fresh[key] if _source_group(row['source']) in replaced or _source_group(row['source']) is None]
        merged[key] = kept + added
    merged['request_count'] = fresh.get('request_count', 0)
    return merged


def save_context(fresh, path, *, include_extras=True, include_meals=True):
    path = Path(path)
    previous = load_collection_report(path) if path.exists() else None
    merged = merge_context(previous, fresh, include_extras=include_extras, include_meals=include_meals)
    save_collection_report(merged, path)
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, help='요청 원본을 저장할 폴더')
    parser.add_argument('--meals-only', action='store_true', help='식당 여섯 곳만 수집하고 같은 날짜의 날씨·일정은 보존')
    args = parser.parse_args()
    day = datetime.now(SEOUL).date()
    with Client() as client:
        fresh = collect(client, day, fixtures=args.fixtures, include_extras=not args.meals_only)
    path = ROOT / 'data/raw' / day.isoformat() / 'context.json'
    result = save_context(fresh, path, include_extras=not args.meals_only)
    print(f"{day}: 식단 {sum(len(c['meals']) for c in result['channels'])}개 / 일정 {len(result['schedule'])}개 / 오류 {len(fresh['errors'])}개")
    print(path)
    return 1 if fresh['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
