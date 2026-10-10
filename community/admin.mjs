import {json, Problem, text, hash, readBody} from './api.mjs';
import {adminPage} from './admin-page.mjs';
import {fixedMessage} from './fixed-message.mjs';
const COOKIE = '__Secure-knua-admin', TTL = 8 * 60 * 60 * 1000;
const hex = bytes => Array.from(bytes).map(x => x.toString(16).padStart(2, '0')).join('');
function same(a, b) { let difference = a.length ^ b.length; for (let i=0; i<a.length; i++) difference |= a.charCodeAt(i) ^ (b.charCodeAt(i) || 0); return difference === 0; }
function credentials(env) {
  if (!env.ADMIN_USERNAME || !/^pbkdf2-sha256:210000:[a-f0-9]{32}:[a-f0-9]{64}$/.test(env.ADMIN_PASSWORD_HASH || '')) throw new Problem(503, '관리자 계정을 아직 설정하지 않았어요.');
  return hash(env.ADMIN_USERNAME + '\n' + env.ADMIN_PASSWORD_HASH);
}
async function passwordMatches(password, stored) {
  const [, , salt, expected] = stored.split(':');
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
  const actual = await crypto.subtle.deriveBits({name:'PBKDF2', hash:'SHA-256', salt:Uint8Array.from(salt.match(/../g), x=>parseInt(x,16)), iterations:210000}, key, 256);
  return same(hex(new Uint8Array(actual)), expected);
}
async function limitLogin(db, request) {
  const hour = new Date().toISOString().slice(0,13), ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  for (const [key, max] of [['admin-login:global',200],['admin-login:'+await hash(ip),10]]) {
    const count = await db.prepare('INSERT INTO community_limits (key, day, count) VALUES (?, ?, 1) ON CONFLICT(key) DO UPDATE SET day=excluded.day, count=CASE WHEN community_limits.day=excluded.day THEN community_limits.count+1 ELSE 1 END RETURNING count').bind(key,hour).first();
    if (count.count > max) throw new Problem(429,'로그인 시도가 너무 많아요. 잠시 후 다시 시도해 주세요.');
  }
}
function sessionToken(request) { return new RegExp('(?:^|;\\s*)'+COOKIE+'=([a-f0-9]{64})(?:;|$)').exec(request.headers.get('Cookie') || '')?.[1]; }
function cookie(token, age=TTL/1000) { return `${COOKIE}=${token}; Path=/admin; HttpOnly; Secure; SameSite=Strict; Max-Age=${age}`; }
export async function handleAdmin(request, env) {
  let response;
  try {
    const url=new URL(request.url), path=url.pathname.replace(/\/$/,''), method=request.method;
    if (url.protocol !== 'https:') throw new Problem(403,'관리자 로그인은 HTTPS에서만 가능합니다.');
    if (path==='/admin' && method==='GET') {
      const nonce=hex(crypto.getRandomValues(new Uint8Array(16)));
      response=new Response(adminPage.replaceAll('__NONCE__',nonce),{headers:{'Content-Type':'text/html; charset=utf-8','Content-Security-Policy':`default-src 'none'; script-src 'nonce-${nonce}'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`}});
    } else {
      if (!env.COMMUNITY_DB) throw new Problem(503,'모임 서버 연결을 확인해 주세요.');
      const db=env.COMMUNITY_DB, credential=await credentials(env);
      // 쿠키 인증 변경 요청은 관리자 페이지 자체 출처에서만 받는다.
      if (method!=='GET' && request.headers.get('Origin')!==url.origin) throw new Problem(403,'관리자 페이지에서만 요청할 수 있어요.');
      if (path==='/admin/api/login' && method==='POST') {
        await limitLogin(db,request);
        const body=await readBody(request), username=text(body,'username',80,true), password=body.password;
        if (typeof password!=='string' || !password || password.length>256) throw new Problem(400,'아이디와 비밀번호를 확인해 주세요.');
        const passwordOk=await passwordMatches(password,env.ADMIN_PASSWORD_HASH);
        if (!same(await hash(username),await hash(env.ADMIN_USERNAME)) || !passwordOk) throw new Problem(401,'아이디 또는 비밀번호가 맞지 않아요.');
        const token=hex(crypto.getRandomValues(new Uint8Array(32)));
        await db.prepare('DELETE FROM community_admin_sessions WHERE expires_at <= ?').bind(Date.now()).run();
        await db.prepare('INSERT INTO community_admin_sessions (token_hash, credential_hash, expires_at) VALUES (?, ?, ?)').bind(await hash(token),credential,Date.now()+TTL).run();
        response=json({ok:true}); response.headers.set('Set-Cookie',cookie(token));
      } else {
        const token=sessionToken(request), session=token ? await db.prepare('SELECT credential_hash, expires_at FROM community_admin_sessions WHERE token_hash=?').bind(await hash(token)).first() : null;
        if (!session || session.expires_at<=Date.now() || !same(session.credential_hash,credential)) throw new Problem(401,'관리자 로그인이 필요해요.');
        if (path==='/admin/api/session' && method==='GET') response=json({ok:true});
        else if (path==='/admin/api/fixed-message' && method==='GET') response=json(await fixedMessage(db));
        else if (path==='/admin/api/fixed-message' && method==='PUT') {
          const body=await readBody(request), value=text(body,'text',500,true);
          if(!Number.isSafeInteger(body.updatedAt) || body.updatedAt<0) throw new Problem(400,'저장된 멘트를 다시 불러와 주세요.');
          const updatedAt=Math.max(Date.now(),body.updatedAt+1);
          const row=await db.prepare('UPDATE community_fixed_message SET text=?, updated_at=? WHERE id=1 AND updated_at=? RETURNING text, updated_at').bind(value,updatedAt,body.updatedAt).first();
          if(!row) throw new Problem(409,'다른 곳에서 멘트가 바뀌었어요. 새로고침 후 다시 수정해 주세요.');
          response=json({text:row.text,updatedAt:row.updated_at});
        }
        else if (path==='/admin/api/logout' && method==='POST') {
          await db.prepare('DELETE FROM community_admin_sessions WHERE token_hash=?').bind(await hash(token)).run();
          response=json({ok:true});response.headers.set('Set-Cookie',cookie('',0));
        } else if (path==='/admin/api/reports' && method==='GET') {
          const cursor=url.searchParams.get('cursor') || '';
          if(cursor && !/^\d{1,16}:\d{1,16}$/.test(cursor)) throw new Problem(400,'신고 목록 위치를 확인해 주세요.');
          const [time,position]=cursor.split(':').map(Number);
          if(cursor && (!Number.isSafeInteger(time)||!Number.isSafeInteger(position)||position<1)) throw new Problem(400,'신고 목록 위치를 확인해 주세요.');
          const result=await db.prepare('SELECT r.rowid AS position, r.reason, r.created_at, p.id, p.payload, p.hidden FROM community_reports r JOIN community_posts p ON p.id=r.post_id'+(cursor?' WHERE (r.created_at < ? OR (r.created_at = ? AND r.rowid < ?))':'')+' ORDER BY r.created_at DESC, r.rowid DESC LIMIT 31').bind(...(cursor?[time,time,position]:[])).all();
          const rows=result.results.slice(0,30), last=rows.at(-1);
          response=json({items:rows.map(r=>({post:{...JSON.parse(r.payload),id:r.id,hidden:!!r.hidden},reason:r.reason,reportedAt:r.created_at})),nextCursor:result.results.length>30?`${last.created_at}:${last.position}`:null});
        } else if (path==='/admin/api/meetings' && method==='GET') {
          const query=(url.searchParams.get('q') || '').trim(), cursor=url.searchParams.get('cursor') || '';
          if(query.length>80) throw new Problem(400,'검색어는 80자 이내로 적어 주세요.');
          if(cursor && !/^\d{1,16}:\d{1,16}$/.test(cursor)) throw new Problem(400,'목록 위치를 확인해 주세요.');
          const [time,position]=cursor.split(':').map(Number);
          if(cursor && (!Number.isSafeInteger(time)||!Number.isSafeInteger(position)||position<1)) throw new Problem(400,'목록 위치를 확인해 주세요.');
          const where=[], args=[];
          if(query){where.push("instr(lower(json_extract(payload,'$.title')),lower(?))>0");args.push(query);}
          if(cursor){where.push('(created_at < ? OR (created_at = ? AND rowid < ?))');args.push(time,time,position);}
          const result=await db.prepare('SELECT rowid AS position,id,payload,hidden,closed,created_at FROM community_posts'+(where.length?' WHERE '+where.join(' AND '):'')+' ORDER BY created_at DESC,rowid DESC LIMIT 31').bind(...args).all();
          const rows=result.results.slice(0,30),last=rows.at(-1);
          response=json({items:rows.map(r=>({...JSON.parse(r.payload),id:r.id,hidden:!!r.hidden,closed:!!r.closed,createdAt:r.created_at})),nextCursor:result.results.length>30?`${last.created_at}:${last.position}`:null});
        } else if (/^\/admin\/api\/meetings\/[a-f0-9-]{36}$/.test(path) && method==='DELETE') {
          const id=path.split('/').at(-1),body=await readBody(request);
          if(body.confirmId!==id) throw new Problem(400,'삭제할 글을 다시 확인해 주세요.');
          const row=await db.prepare('SELECT id FROM community_posts WHERE id=?').bind(id).first();
          if(!row) throw new Problem(404,'모집글이 삭제되었거나 없어요.');
          await db.prepare('DELETE FROM community_posts WHERE id=?').bind(id).run();
          response=json({ok:true});
        } else if (/^\/admin\/api\/meetings\/[a-f0-9-]{36}$/.test(path) && method==='PUT') {
          const id=path.split('/').at(-1), body=await readBody(request);
          if(typeof body.hidden!=='boolean') throw new Problem(400,'숨김 상태를 확인해 주세요.');
          const row=await db.prepare('SELECT id FROM community_posts WHERE id=?').bind(id).first();
          if(!row) throw new Problem(404,'모집글이 삭제되었거나 없어요.');
          await db.prepare('UPDATE community_posts SET hidden=? WHERE id=?').bind(Number(body.hidden),id).run();
          response=json({ok:true,hidden:body.hidden});
        } else throw new Problem(404,'관리자 기능을 찾을 수 없어요.');
      }
    }
  } catch(e) { response=json({error:e instanceof Problem?e.message:'관리자 서버에 연결하지 못했어요.'},e instanceof Problem?e.status:503); }
  response.headers.set('Cache-Control','no-store');response.headers.set('X-Content-Type-Options','nosniff');response.headers.set('X-Frame-Options','DENY');response.headers.set('Referrer-Policy','no-referrer');
  return response;
}
