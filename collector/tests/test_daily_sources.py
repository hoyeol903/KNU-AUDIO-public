from copy import deepcopy
import json
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from collector import daily_sources as sources, store, run
from collector.daily_items import build_items
from collector.http import Client, FetchError
from collector.knu_cms import ParseError

FIXTURES = Path(__file__).parent / 'fixtures'
DAY = date(2026, 10, 1)


def html(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


def weather():
    return dict(utc_offset_seconds=32400,
                daily=dict(time=['2026-10-01'], weather_code=[0], temperature_2m_min=[15.2],
                           temperature_2m_max=[27.1], precipitation_probability_max=[10]),
                daily_units=dict(weather_code='wmo code', temperature_2m_min='°C',
                                 temperature_2m_max='°C', precipitation_probability_max='%'))


def test_real_meals_match_dates_not_wrong_weekday_labels():
    meals = sources.parse_meals(html('daily-sources/meal-46.html'), DAY, 'GP감꽃식당')
    assert meals == [dict(place='GP감꽃식당',time='11:15~13:30',
                         menu=['홍국밥','매콤호박감자국','대패삼겹야채찜★','카레가자미튀김','온두부찜&양념장','포기김치'])]
    other = sources.parse_meals(html('daily-sources/meal-35.html'), DAY, '정보센터식당')
    assert len(other) == 12
    assert other[0]['menu'][0] == '바베큐폭립오므라이스★'
    assert other[1]['time'] is None  # 앞 메뉴의 시간을 다른 메뉴에 복사하지 않는다.
    assert other[-1]['time'] == '17:00~19:00'
    assert all('￦' not in x and ':' not in x for r in other for x in r['menu'])


@pytest.mark.parametrize('name,day,place',[
    ('학식_식단_다음주.html',date(2026,10,5),'GP감꽃식당'),
    ('daily-sources/meal-46.html',date(2026,10,3),'GP감꽃식당'),
    ('daily-sources/meal-46.html',date(2026,11,1),'GP감꽃식당'),
    ('daily-sources/meal-46.html',DAY,'정보센터식당'),
])
def test_missing_menu_date_or_identity_is_failure(name,day,place):
    with pytest.raises(ParseError): sources.parse_meals(html(name),day,place)


@pytest.mark.parametrize('channel,place',[
    ('meal-85','공학관교직원식당(외부업체)'),
    ('meal-86','공학관학생식당(외부업체)'),
    ('meal-bokji','복지관 교직원식당'),
    ('meal-37','카페테리아 첨성'),
])
def test_new_restaurant_fixtures_parse_menu_and_reject_unpublished_today(channel,place):
    source=html(f'daily-sources/{channel}.html')
    meals=sources.parse_meals(source,date(2026,10,6),place)
    assert meals and all(row['place']==place and row['menu'] for row in meals)
    if channel=='meal-37':
        ramen=next(row for row in meals if '라면' in row['menu'])
        assert ramen['time']=='9:00~11:00,13:00~15:30'
    with pytest.raises(ParseError,match='메뉴 미게시'):
        sources.parse_meals(source,date(2026,10,3),place)


def test_all_restaurant_ids_route_to_their_shop_number():
    fixture_by_shop={
        '46':'daily-sources/meal-46.html', '35':'daily-sources/meal-35.html',
        '85':'daily-sources/meal-85.html', '86':'daily-sources/meal-86.html',
        '36':'daily-sources/meal-bokji.html', '37':'daily-sources/meal-37.html',
    }
    class FakeClient:
        urls=[]
        def get_json(self,url): raise FetchError('fixture only: 날씨 미수집')
        def get(self,url):
            self.urls.append(url)
            parsed=urlsplit(url)
            if 'yearSchedule' in parsed.path: raise FetchError('fixture only: 일정 미수집')
            shop=parse_qs(parsed.query)['shop_sqno'][0]
            if shop not in {'85','86','36','37'}:
                raise FetchError('fixture only: 기존 두 식당은 이번 수집 검증 범위에서 제외')
            return html(fixture_by_shop[shop]),url
    context=sources.collect(FakeClient(),date(2026,10,6))
    requested={parse_qs(urlsplit(url).query)['shop_sqno'][0] for url in FakeClient.urls
               if 'shop_sqno' in parse_qs(urlsplit(url).query)}
    assert requested == set(fixture_by_shop)
    assert [row['channel_id'] for row in context['channels']] == list(sources.MEAL_SOURCES)
    assert all(channel['meals'] for channel in context['channels'][2:])
    assert {error['source'] for error in context['errors']} == {'weather','meal-46','meal-35','schedule'}


@pytest.mark.parametrize('final_host,redirected',[
    ('http://coop.knu.ac.kr/sub03/sub01_01.html?shop_sqno=46&selDate=2026-10-01',False),
    ('http://errdoc.gabia.io/403.html',True),
    ('http://coop.knu.ac.kr/403.html',True),
])
def test_restaurant_final_url_rejects_external_redirect_but_allows_http(final_host,redirected):
    class FakeClient:
        def get_json(self,url): raise FetchError('fixture: 날씨 미수집')
        def get(self,url):
            if 'shop_sqno=46' in url:
                return html('daily-sources/meal-46.html'),final_host
            raise FetchError('fixture: 이 시험은 다른 원문을 요청하지 않음')
    context=sources.collect(FakeClient(),DAY)
    meal=next(c for c in context['channels'] if c['channel_id']=='meal-46')
    error=next((e for e in context['errors'] if e['source']=='meal-46'),None)
    if redirected:
        assert meal['meals']==[]
        assert error and '식당 원문과 다른 주소로 이동했습니다' in error['message']
        assert final_host in error['message']
        assert not any(s['source']=='meal-46' for s in context['sources'])
    else:
        assert meal['meals']
        assert error is None
        assert any(s['source']=='meal-46' and s['url']==final_host for s in context['sources'])


def test_skip_meals_collects_weather_and_schedule_and_marks_local_meals_missing():
    class FakeClient:
        request_count=0
        def get_json(self,url):
            self.request_count+=1
            return weather(),url
        def get(self,url):
            self.request_count+=1
            assert 'yearSchedule' in url
            return html('daily-sources/schedule-2026.html'),url
    client=FakeClient()
    context=sources.collect(client,DAY,include_meals=False)
    assert client.request_count==2
    assert context['channels']==[]
    assert {row['source'] for row in context['sources']}=={'weather','schedule'}
    # 앱 달력용 연간 일정은 가까운 일정보다 많고, 가까운 일정은 모두 그 안에 있다.
    year=[(r['title'],r['start']) for r in context['schedule_year']]
    assert len(year)>len(context['schedule']) and all(r['start'].startswith('2026-') for r in context['schedule_year'])
    assert all((r['title'],r['start']) in year for r in context['schedule'])
    fixed_now=datetime.fromisoformat('2026-10-01T06:00:00+09:00')
    context['collected_at']=fixed_now.isoformat()
    items=build_items([],{'boards':{}},[],now=fixed_now,context=context)
    info=next(e for e in items['errors'] if e['source']=='meals')
    assert info['message']=='오늘 식단은 로컬에서 아직 수집하지 않았습니다'
    assert not context['errors']


def test_meals_only_collects_six_restaurants_without_weather_or_schedule():
    fixture_by_shop={
        '46':'daily-sources/meal-46.html', '35':'daily-sources/meal-35.html',
        '85':'daily-sources/meal-85.html', '86':'daily-sources/meal-86.html',
        '36':'daily-sources/meal-bokji.html', '37':'daily-sources/meal-37.html',
    }
    class FakeClient:
        urls=[]
        def get_json(self,url):
            raise AssertionError('meals-only는 날씨 API를 요청하지 않습니다')
        def get(self,url):
            parsed=urlsplit(url)
            assert parsed.hostname=='coop.knu.ac.kr' and parsed.path=='/sub03/sub01_01.html'
            assert 'selDate=2026-10-06' in parsed.query
            shop=parse_qs(parsed.query)['shop_sqno'][0]
            self.urls.append(shop)
            return html(fixture_by_shop[shop]),url
    client=FakeClient()
    context=sources.collect(client,date(2026,10,6),include_extras=False)
    assert set(client.urls)==set(fixture_by_shop)
    assert len(client.urls)==6
    assert context['weather']==dict(summary=None,temp_min=None,temp_max=None,rain_prob=None)
    assert context['schedule']==[]
    assert [row['channel_id'] for row in context['channels']]==list(sources.MEAL_SOURCES)


def test_context_merge_keeps_unrequested_groups_and_rejects_other_dates(tmp_path):
    day=DAY.isoformat()
    previous=dict(date=day,collected_at='2026-10-01T05:00:00+09:00',
                  weather=dict(summary='맑음'),channels=[dict(channel_id='meal-46',notices=[],meals=[{'menu':['old']}])],
                  schedule=[dict(title='old')],errors=[
                      dict(source='weather',message='old weather'),
                      dict(source='schedule',message='old schedule'),
                      dict(source='meal-46',message='old meal')],
                  sources=[dict(source='weather',url='old'),dict(source='schedule',url='old'),
                           dict(source='meal-46',url='old')])
    meal_run=dict(date=day,collected_at='2026-10-01T06:00:00+09:00',weather=dict(summary=None),
                  channels=[dict(channel_id='meal-46',notices=[],meals=[{'menu':['new']}])],
                  schedule=[],errors=[dict(source='meal-46',message='new meal')],
                  sources=[dict(source='meal-46',url='new')],request_count=6)
    local=sources.merge_context(previous,meal_run,include_extras=False)
    assert local['weather']==previous['weather'] and local['schedule']==previous['schedule']
    assert local['schedule_year']==[]
    assert local['channels']==meal_run['channels']
    assert {e['source'] for e in local['errors']}=={'weather','schedule','meal-46'}
    assert next(e for e in local['errors'] if e['source']=='meal-46')['message']=='new meal'
    assert local['request_count']==6
    remote_run=dict(date=day,collected_at='2026-10-01T07:00:00+09:00',weather=dict(summary='흐림'),
                    channels=[],schedule=[dict(title='new')],errors=[],
                    sources=[dict(source='weather',url='new'),dict(source='schedule',url='new')],request_count=2)
    remote=sources.merge_context(local,remote_run,include_meals=False)
    assert remote['weather']==remote_run['weather'] and remote['schedule']==remote_run['schedule']
    assert remote['channels']==local['channels']
    assert [e for e in remote['errors'] if e['source'].startswith('meal-')]==[
        dict(source='meal-46',message='new meal')]
    assert {row['source'] for row in remote['sources']}=={'weather','schedule','meal-46'}
    path=tmp_path/'context.json';store.save_collection_report(remote,path);original=path.read_bytes()
    bad=dict(meal_run,date='2026-09-30')
    with pytest.raises(ValueError,match='다른 날짜'):
        sources.save_context(bad,path,include_extras=False)
    assert path.read_bytes()==original


def test_run_skip_meals_uses_only_fresh_extra_errors(monkeypatch,tmp_path):
    from datetime import datetime as DateTime
    from collector.store import SEOUL, load_collection_report
    today=DateTime.now(SEOUL).date()
    data=tmp_path/'data';(data/'channels.yaml').parent.mkdir(parents=True)
    (data/'channels.yaml').write_text('[]',encoding='utf-8')
    context_path=data/'raw'/today.isoformat()/'context.json'
    store.save_collection_report(dict(date=today.isoformat(),collected_at=DateTime.now(SEOUL).isoformat(),
        weather=dict(summary=None),channels=[dict(channel_id='meal-46',notices=[],meals=[])],schedule=[],
        errors=[dict(source='meal-46',message='old meal failure')],
        sources=[dict(source='meal-46',url='old')],request_count=1),context_path)
    class FakeClient:
        request_count=0
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get_json(self,url):
            self.request_count+=1
            payload=weather();payload['daily']['time']=[today.isoformat()]
            return payload,url
        def get(self,url):
            self.request_count+=1
            assert 'yearSchedule' in url
            return html('daily-sources/schedule-2026.html'),url
    monkeypatch.setattr(run,'ROOT',tmp_path)
    monkeypatch.setattr(run,'select_channels',lambda *args,**kwargs:[])
    monkeypatch.setattr(run,'Client',FakeClient)
    monkeypatch.setattr(sys,'argv',['collector.run','--write-items','--collect-extras','--skip-meals',
                                    '--db-path',str(tmp_path/'notices.json'),
                                    '--report-path',str(tmp_path/'run.json'),
                                    '--items-path',str(tmp_path/'items.json')])
    assert run.main()==0
    report=load_collection_report(tmp_path/'run.json')
    assert report['extras']['errors']==[]
    items=json.loads((tmp_path/'items.json').read_text())
    assert any(e['source']=='meal-46' and e['message']=='old meal failure' for e in items['errors'])
    assert items['channels'][0]['meals']==[]


def test_one_board_failure_does_not_stop_the_run(tmp_path,monkeypatch):
    class FakeClient:
        request_count=0
        def __enter__(self):return self
        def __exit__(self,*args):pass
    boards=[dict(id=id,name=id,channel_ids=[id],source_url='https://x.knu.ac.kr/HOME/x/sub.htm?nav_code='+id) for id in ('a','b')]
    def fake_collect(client,channel,**kwargs):
        if channel['id']=='a': raise RuntimeError('boom')
        return dict(channel_id='b',errors=[],truncated=False,request_count=0,listed=0,successful=0,new=[],updated=[],skipped=[],duration_sec=0)
    monkeypatch.setattr(run,'ROOT',tmp_path)
    (tmp_path/'data').mkdir();(tmp_path/'data/channels.yaml').write_text('[]')
    monkeypatch.setattr(run,'VALIDATION_PATH',tmp_path/'none.json')
    monkeypatch.setattr(run,'select_channels',lambda *args,**kwargs:boards)
    monkeypatch.setattr(run,'collect',fake_collect)
    monkeypatch.setattr(run,'Client',FakeClient)
    monkeypatch.setattr(sys,'argv',['collector.run','--all-required','--report-path',str(tmp_path/'run.json')])
    assert run.main()==1
    done=json.loads((tmp_path/'run.json').read_text())['channels']
    assert [c['channel_id'] for c in done]==['a','b']
    assert 'boom' in done[0]['errors'][0]['message'] and done[0]['started_at']


def test_explicit_closed_is_distinct_from_unpublished():
    doc='<h2>식당</h2><table class="tstyle_me"><p class="week_t">(10/01)</p></table><table class="tstyle_me"><caption>중식</caption><tbody><tr><td><ul class="menu_im"><li>휴무</li></ul></td></tr></tbody></table>'
    assert sources.parse_meals(doc,DAY,'식당') == []
    with pytest.raises(ParseError): sources.parse_meals(doc.replace('<li>휴무</li>',''),DAY,'식당')


def test_schedule_calendar_year_ranges_and_unknown_end():
    rows=sources.parse_schedule(html('daily-sources/schedule-2026.html'),2026)
    assert len(rows) > 90
    ongoing=next(r for r in rows if r['start']=='2026-09-30')
    assert ongoing['end']=='2026-10-02'
    rollover=next(r for r in rows if r['start']=='2026-12-28')
    assert rollover['end']=='2027-01-05'
    assert next(r for r in rows if r['title'].startswith('신정'))['end'] is None
    with pytest.raises(ParseError):sources.parse_schedule(html('daily-sources/schedule-2026.html'),2027)
    with pytest.raises(ParseError):sources.parse_schedule('<html>로그인</html>',2026)
    broken=html('daily-sources/schedule-2026.html').replace('12.28.~2027.1.5.','12.28.~1.5.')
    with pytest.raises(ParseError):sources.parse_schedule(broken,2026)


def test_weather_units_codes_missing_values_and_date():
    assert sources.parse_weather(weather(),DAY)==dict(summary='맑음',temp_min=15.2,temp_max=27.1,rain_prob=10)
    mutations=[('weather_code',999),('temperature_2m_min',None),('temperature_2m_min',30),
               ('temperature_2m_max',float('nan')),('precipitation_probability_max',101),('precipitation_probability_max',True)]
    for key,value in mutations:
        bad=weather();bad['daily'][key]=[value]
        with pytest.raises(ParseError):sources.parse_weather(bad,DAY)
    bad=weather();bad['daily_units']['temperature_2m_min']='°F'
    with pytest.raises(ParseError):sources.parse_weather(bad,DAY)
    with pytest.raises(ParseError):sources.parse_weather(weather(),date(2026,10,2))


def test_partial_failure_context_merge_and_atomic_validation(tmp_path):
    class FakeClient:
        def get_json(self,url): raise FetchError('의도한 날씨 실패')
        def get(self,url):
            if 'yearSchedule' in url: return html('daily-sources/schedule-2026.html'),url
            if 'shop_sqno=46' in url: name='meal-46'
            elif 'shop_sqno=35' in url: name='meal-35'
            else: raise FetchError('이 시험은 추가 식당 fixture 날짜를 설정하지 않았습니다')
            return html('daily-sources/'+name+'.html'),url
    context=sources.collect(FakeClient(),DAY)
    assert [e['source'] for e in context['errors']]==['weather','meal-85','meal-86','meal-bokji','meal-37']
    assert [len(c['meals']) for c in context['channels']]==[1,12,0,0,0,0]
    assert context['schedule'][0]['dday']==-1
    context['schedule'].append(dict(title='중간고사',start='2026-10-02',end=None,dday=1))
    context['collected_at']='2026-10-01T05:37:00+09:00'
    now=datetime.fromisoformat('2026-10-01T06:00:00+09:00')
    output=build_items([],{'boards':{}},[],now=now,context=context)
    assert output['errors']==context['errors'] and output['channels']==context['channels']
    path=tmp_path/'items.json';store.save_daily_items(output,path)
    original=path.read_bytes()
    for key,value in [('rain_prob',101),('temp_min',float('nan'))]:
        bad=deepcopy(output);bad['weather'][key]=value
        with pytest.raises(ValueError):store.save_daily_items(bad,path)
    bad=deepcopy(output);bad['channels'][0]['meals'][0]['menu']=[]
    with pytest.raises(ValueError):store.save_daily_items(bad,path)
    bad=deepcopy(output);bad['schedule'][0]['dday']=0
    with pytest.raises(ValueError):store.save_daily_items(bad,path)
    assert path.read_bytes()==original
    context['date']='2026-09-30'
    with pytest.raises(ValueError):build_items([],{'boards':{}},[],now=now,context=context)


def test_json_transport_uses_shared_client_and_rejects_invalid_json(monkeypatch):
    class Response:
        status_code=200;headers={'Content-Type':'application/json'};url='https://example.com/weather'
        def raise_for_status(self):pass
        def close(self):pass
        def json(self):return weather()
    with Client() as client:
        monkeypatch.setattr(client.session,'get',lambda *a,**kw:Response())
        payload,url=client.get_json(Response.url)
        assert payload==weather() and client.request_count==1 and 'example.com' in client.last_finished
        Response.headers={'Content-Type':'text/html'}
        client.last_finished.clear()
        with pytest.raises(FetchError):client.get_json(Response.url)


def test_meal_week_reads_every_date_and_keeps_unpublished_days_empty():
    week=sources.parse_meal_week(html('daily-sources/meal-85.html'),date(2026,10,3),'공학관교직원식당(외부업체)')
    assert [row['date'] for row in week]==['2026-10-03','2026-10-04','2026-10-05','2026-10-06','2026-10-07','2026-10-08']
    assert [row['status'] for row in week]==['empty','empty','ok','ok','ok','ok']
    today=sources.parse_meals(html('daily-sources/meal-85.html'),date(2026,10,6),'공학관교직원식당(외부업체)')
    assert week[0]['meals']==[] and [{k:row[k] for k in ('place','time','menu')} for row in week[3]['meals']]==today
    assert all(set(row)=={'place','time','menu'} for row in today)  # items.json 계약은 그대로


def test_meal_week_keeps_meal_label_price_and_main_dish_lines():
    week=sources.parse_meal_week(html('daily-sources/meal-86.html'),date(2026,10,3),'공학관학생식당(외부업체)')
    lunch=[row for row in week[3]['meals'] if row['label']=='중식']
    assert lunch[0]['menu']==['육회비빔밥'] and lunch[0]['price']==6500 and lunch[0]['head']==1
    assert {row['label'] for row in week[3]['meals']}=={'중식','석식'}
    cafe=sources.parse_meal_week(html('daily-sources/meal-37.html'),date(2026,10,3),'카페테리아 첨성')
    first=next(row for row in cafe[3]['meals'] if row['label']=='중식')
    assert first['menu'][:2]==['소시지','오므라이스★'] and first['head']==2 and first['price']==6000
    fixed=sources.parse_meal_week(html('daily-sources/meal-46.html'),date(2026,10,1),'GP감꽃식당')[0]['meals'][0]
    assert fixed['price']==6000 and fixed['head']==0 and fixed['label']=='중식'
    with pytest.raises(ParseError): sources.parse_meal_week(html('daily-sources/meal-85.html'),date(2026,10,3),'다른식당')
