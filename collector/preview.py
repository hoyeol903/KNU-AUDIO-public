"""읽기 전용 로컬 테스트 화면: python -m collector.preview"""
import argparse
import json
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote

import yaml
from collector.daily_items import build_items, decide_notice, load_context
from collector.deadlines import extract_deadline
from collector.store import DEFAULT_PATH, SEOUL, load_notices, load_collection_state, load_collection_report

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'tools/collector-test.html'
PAGES = {'/': HTML, '/app': ROOT / 'tools/app-test.html'}


def catalog():
    channels=yaml.safe_load((ROOT/'data/channels.yaml').read_text(encoding='utf-8'))
    departments=yaml.safe_load((ROOT/'data/departments.yaml').read_text(encoding='utf-8'))
    return channels, [d for d in departments if d['kind']=='department']


def latest_reports(day=None):
    latest={}
    for path in (ROOT/'data/runs').glob('*.json'):
        report=load_collection_report(path)
        boards=report.get('channels',[])
        if not isinstance(boards,list):continue
        for board in boards:
            if not isinstance(board,dict) or not {'source_board_id','started_at','errors','truncated'} <= board.keys():continue
            started=datetime.fromisoformat(board['started_at'])
            if day is not None and started.date()!=day:continue
            key=board['source_board_id']
            if key not in latest or board.get('finished_at',board['started_at']) > latest[key].get('finished_at',latest[key]['started_at']):
                latest[key]=board
    return [dict(channels=list(latest.values()))]


def snapshot(ids, *, now=None, db_path=DEFAULT_PATH):
    channels,_=catalog();by_id={c['id']:c for c in channels}
    if not isinstance(ids,list) or not ids or len(ids)>300 or any(not isinstance(i,str) or i not in by_id for i in ids):
        raise ValueError('채널을 하나 이상 선택하세요')
    rows=load_notices() if db_path == DEFAULT_PATH else load_notices(db_path)
    state=load_collection_state() if db_path == DEFAULT_PATH else load_collection_state(db_path)
    now=now or datetime.now(SEOUL)
    logical=[];missing=[]
    for id in dict.fromkeys(ids):
        c=by_id[id]
        if c['type']!='notice':continue
        boards={r['source_board_id'] for r in rows if id in r['channel_ids']}
        if len(boards)!=1:
            missing.append(dict(source=id,message=c['name']+': 저장 자료가 없거나 게시판 연결을 확정할 수 없습니다'))
            continue
        logical.append(dict(c,source_board_id=next(iter(boards))))
    context=load_context()
    if context is not None:context=dict(context,channels=[c for c in context['channels'] if c['channel_id'] in ids])
    reports=latest_reports(now.date())
    items=build_items(rows,state,logical,now=now,reports=reports,context=context)
    items['errors'].extend(missing)
    failed={unquote(e['url']) for report in reports for b in report['channels'] for e in b['errors'] if e.get('url')}
    checks=[]
    for r in rows:
        if not set(r['channel_ids']).intersection(ids):continue
        baseline=state['boards'].get(r['source_board_id'],{}).get('initialized_at')
        checks.append(dict({k:r[k] for k in ('id','title','url','channel_ids','posted_at','deadline','first_seen_at','last_checked_at','body_status')},
                           **decide_notice(r,baseline,now,failed)))
    checks.sort(key=lambda r:(r['status']!='selected',r['dday'] if r['dday'] is not None else 10**9,r['id']))
    return dict(items=items,checks=checks,db_count=len(rows),checked_at=now.isoformat())


def simulate(payload):
    fields={'date','time','title','body','body_status','posted_at','deadline','first_seen_at','last_checked_at','baseline'}
    if not isinstance(payload,dict) or set(payload)!=fields or any(not isinstance(v,str) for v in payload.values()):
        raise ValueError('시험 입력 형식 오류')
    now=datetime.fromisoformat(payload['date']+'T'+payload['time']+':00+09:00')
    if payload['body_status'] not in {'text','image-only','attachment-only','empty','needs-review'}:
        raise ValueError('본문 상태 오류')
    if not payload['title'].strip():raise ValueError('제목을 입력하세요')
    for key in ('posted_at','deadline'):
        if payload[key]:date.fromisoformat(payload[key])
    for key in ('first_seen_at','last_checked_at','baseline'):
        if key=='baseline' and not payload[key]:continue
        stamp=datetime.fromisoformat(payload[key])
        if stamp.utcoffset()!=timedelta(hours=9):raise ValueError('확인 시각은 +09:00을 포함해야 합니다')
    if datetime.fromisoformat(payload['last_checked_at']) < datetime.fromisoformat(payload['first_seen_at']):
        raise ValueError('마지막 확인 시각은 처음 발견보다 빠를 수 없습니다')
    body=None if payload['body_status'] in {'image-only','attachment-only'} else payload['body']
    if payload['body_status']=='text' and not body.strip():raise ValueError('텍스트 상태에는 본문을 입력하세요')
    if payload['body_status']=='empty' and body:raise ValueError('빈 본문 상태에서는 본문을 비워주세요')
    row=dict(id='test:1',source_board_id='test',channel_ids=['test-channel'],title=payload['title'],body=body,
             body_status=payload['body_status'],url='https://example.com/test',posted_at=payload['posted_at'] or None,
             deadline=payload['deadline'] or None,first_seen_at=payload['first_seen_at'],last_checked_at=payload['last_checked_at'])
    baseline=payload['baseline'] or None
    state={'boards':{'test':dict(initialized_at=baseline)}}
    items=build_items([row],state,[dict(id='test-channel',name='가상 시험 채널',source_board_id='test')],now=now)
    return dict(decision=decide_notice(row,baseline,now),items=items)


class Handler(BaseHTTPRequestHandler):
    def reply(self,status,value,content_type='application/json; charset=utf-8'):
        raw=value.encode() if isinstance(value,str) else json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)

    def allowed(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self.allowed():return self.reply(403,dict(error='로컬 접속만 허용합니다'))
        url=urlsplit(self.path)
        try:
            if url.path in PAGES:return self.reply(200,PAGES[url.path].read_text(encoding='utf-8'),'text/html; charset=utf-8')
            if url.path=='/api/catalog':
                channels,depts=catalog()
                stored=sorted({id for r in load_notices() for id in r['channel_ids']})
                return self.reply(200,dict(channels=channels,departments=depts,stored_channel_ids=stored,date=datetime.now(SEOUL).date().isoformat()))
            if url.path=='/api/notice':
                id=parse_qs(url.query).get('id',[''])[0]
                row=next((r for r in load_notices() if r['id']==id),None)
                return self.reply(200,row) if row else self.reply(404,dict(error='공지를 찾을 수 없습니다'))
            self.reply(404,dict(error='없는 주소입니다'))
        except (ValueError,OSError) as exc:self.reply(400,dict(error=str(exc)))

    def do_POST(self):
        if not self.allowed() or self.headers.get('Origin') not in {None,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:
            return self.reply(403,dict(error='로컬 테스트 화면에서 실행하세요'))
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=64000:raise ValueError('시험 입력이 비었거나 너무 큽니다')
            payload=json.loads(self.rfile.read(size))
            if self.path=='/api/snapshot' and isinstance(payload,dict) and set(payload)=={'channels'}:
                return self.reply(200,snapshot(payload['channels']))
            if self.path=='/api/simulate':return self.reply(200,simulate(payload))
            if self.path=='/api/deadline' and isinstance(payload,dict) and set(payload)=={'title','body'}:
                return self.reply(200,extract_deadline(payload['title'],payload['body']))
            self.reply(404,dict(error='없는 시험 주소입니다'))
        except (ValueError,TypeError,KeyError,OSError) as exc:self.reply(400,dict(error=str(exc)))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    with HTTPServer(('127.0.0.1',args.port),Handler) as server:
        print(f'테스트 화면: http://127.0.0.1:{args.port} (종료: Ctrl+C)',flush=True)
        server.serve_forever()


if __name__=='__main__':main()
