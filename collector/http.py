"""동기 HTTP 요청: 서버별 간격 1초, 요청별 추가 재시도 최대 2회."""
import time
from urllib.parse import urljoin, urlsplit

import requests

USER_AGENT = 'KNU-AUDIO/0.1 (Kyungpook National University student briefing; requests)'
TIMEOUT = (10, 30)
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


class Client:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT
        self.last_finished = {}
        self.request_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def get_json(self, url):
        return self.get(url, json_mode=True)

    def get(self, url, *, json_mode=False):
        redirects = 0
        while True:
            server = urlsplit(url).hostname
            if urlsplit(url).scheme not in {'http', 'https'} or not server:
                raise FetchError('HTTP(S) 주소가 아닙니다')
            if server.endswith('.knu.ac.kr') and urlsplit(url).path.startswith('/HOME/'):
                server = 'home.knu.ac.kr'  # 공식 CMS 별칭 호스트도 같은 간격을 공유한다.
            response = None
            for attempt in range(3):
                wait = self.last_finished.get(server, float('-inf')) + 1 - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                try:
                    self.request_count += 1
                    response = self.session.get(url, timeout=TIMEOUT, allow_redirects=False)
                except (requests.Timeout, requests.ConnectionError) as exc:
                    if attempt == 2:
                        raise FetchError(f'요청 실패: {url}: {exc}') from exc
                except requests.RequestException as exc:
                    raise FetchError(f'요청 실패: {url}: {exc}') from exc
                finally:
                    self.last_finished[server] = time.monotonic()
                if response is None:
                    continue
                if response.status_code in RETRY_STATUSES and attempt < 2:
                    # Retry-After의 초 단위 값은 최소 대기 시간으로 존중한다.
                    delay = response.headers.get('Retry-After', '')
                    if delay.isdigit():
                        self.last_finished[server] += int(delay)
                    response.close()
                    response = None
                    continue
                break
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get('Location')
                response.close()
                redirects += 1
                if not location or redirects > 5:
                    raise FetchError(f'잘못된 리다이렉트: {url}')
                url = urljoin(url, location)
                continue
            try:
                response.raise_for_status()
                if json_mode:
                    if 'json' not in response.headers.get('Content-Type', '').lower():
                        raise FetchError(f'JSON이 아닌 응답: {url}')
                    try:
                        return response.json(), response.url
                    except ValueError as exc:
                        raise FetchError(f'잘못된 JSON: {url}') from exc
                if 'text/html' not in response.headers.get('Content-Type', '').lower():
                    raise FetchError(f'HTML이 아닌 응답: {url}')
                # requests의 ISO-8859-1 기본값 대신 HTML 선언/바이트로 판정한다.
                from bs4 import BeautifulSoup
                html = BeautifulSoup(response.content, 'html.parser',
                                     from_encoding=response.encoding if response.encoding and
                                     response.encoding.lower() != 'iso-8859-1' else None)
                return str(html), response.url
            except requests.RequestException as exc:
                raise FetchError(f'HTTP 오류: {url}: {exc}') from exc
            finally:
                response.close()
