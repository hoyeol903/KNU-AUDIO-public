/* Pages Functions + D1. Browser capability tokens are hashed; no admin key is sent to clients. */
const categories = ['dating', 'study', 'club'];
const json = (data, status = 200) => new Response(JSON.stringify(data), {status, headers: {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}});
class Problem extends Error { constructor(status, message) { super(message); this.status = status; } }
function text(body, key, max, required = false) {
  const value = body[key] == null ? '' : body[key];
  if (typeof value !== 'string' || value.length > max || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value)) throw new Problem(400, `${key} 입력을 확인해 주세요.`);
  const result = value.trim();
  if (required && !result) throw new Problem(400, '필수 항목을 입력해 주세요.');
  return result;
}
export function contactLink(value) {
  if (!value) return '';
  let u;
  try { u = new URL(value); } catch { throw new Problem(400, '참가 링크를 확인해 주세요.'); }
  const host = u.hostname.toLowerCase();
  if (u.protocol !== 'https:' || u.username || u.password || u.port || !['instagram.com', 'www.instagram.com', 'open.kakao.com'].includes(host) || u.pathname === '/') throw new Problem(400, '인스타그램 또는 오픈카톡의 https 링크를 입력해 주세요.');
  return u.href;
}
export function validatePost(body) {
  const category = text(body, 'category', 10, true);
  if (!categories.includes(category)) throw new Problem(400, '모임 분류를 확인해 주세요.');
  const p = {category, title: text(body, 'title', 60, true), intro: text(body, 'intro', 2000, true), when: text(body, 'when', 100, true), where: text(body, 'where', 100), dept: text(body, 'dept', 80), college: text(body, 'college', 80), contact: contactLink(text(body, 'contact', 500)), requirements: text(body, 'requirements', 500), cost: text(body, 'cost', 100), goal: text(body, 'goal', 200), activity: text(body, 'activity', 200), want: text(body, 'want', 100), size: '', team: '', capacity: 0};
  if (category === 'dating') {
    p.team = text(body, 'team', 1, true); p.size = text(body, 'size', 3, true);
    if (!['m', 'f'].includes(p.team) || !['2:2', '3:3', '4:4'].includes(p.size)) throw new Problem(400, '팀과 인원을 선택해 주세요.');
  } else {
    p.capacity = Number(body.capacity);
    if (!Number.isInteger(p.capacity) || p.capacity < 2 || p.capacity > 100) throw new Problem(400, '모집 인원은 2~100명으로 입력해 주세요.');
    if (category === 'study' && !p.goal) throw new Problem(400, '스터디 목표를 입력해 주세요.');
    if (category === 'club' && !p.activity) throw new Problem(400, '주요 활동을 입력해 주세요.');
  }
  return p;
}
async function hash(value) { return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))).map(x => x.toString(16).padStart(2, '0')).join(''); }
async function identity(request, required = false) {
  const match = /^Bearer ([a-f0-9]{64})$/.exec(request.headers.get('Authorization') || '');
  if (!match && required) throw new Problem(401, '작성자 인증을 준비하지 못했어요. 브라우저 저장 설정을 확인해 주세요.');
  return match ? hash(match[1]) : '';
}
async function readBody(request) {
  if (!(request.headers.get('Content-Type') || '').includes('application/json')) throw new Problem(415, 'JSON 요청만 가능해요.');
  if (Number(request.headers.get('Content-Length')) > 16000) throw new Problem(413, '입력 내용이 너무 길어요.');
  const reader = request.body?.getReader(); if (!reader) throw new Problem(400, '입력 내용이 없어요.');
  let size = 0; const parts = [];
  for (;;) { const {done, value} = await reader.read(); if (done) break; size += value.byteLength; if (size > 16000) { await reader.cancel(); throw new Problem(413, '입력 내용이 너무 길어요.'); } parts.push(value); }
  const bytes = new Uint8Array(size); let offset = 0; for (const part of parts) { bytes.set(part, offset); offset += part.length; }
  try { const b = JSON.parse(new TextDecoder().decode(bytes)); if (!b || typeof b !== 'object' || Array.isArray(b)) throw 0; return b; } catch { throw new Problem(400, '입력 내용을 읽을 수 없어요.'); }
}
async function rate(db, request, owner, action) {
  const day = new Date().toISOString().slice(0, 10);
  const ip = request.headers.get('CF-Connecting-IP');
  const keys = [[`device:${owner}:${action}`, action === 'post' ? 20 : 100]];
  if (ip) keys.push([`ip:${await hash(ip)}:${action}`, action === 'post' ? 100 : 500]);
  for (const [key, max] of keys) {
    const row = await db.prepare('INSERT INTO community_limits (key, day, count) VALUES (?, ?, 1) ON CONFLICT(key) DO UPDATE SET day=excluded.day, count=CASE WHEN community_limits.day=excluded.day THEN community_limits.count+1 ELSE 1 END RETURNING count').bind(key, day).first();
    if (row.count > max) throw new Problem(429, '오늘 등록 횟수를 초과했어요. 내일 다시 시도해 주세요.');
  }
  // Indexed expiry avoids accumulating a new row per browser per day.
  await db.prepare("DELETE FROM community_limits WHERE day < date('now', '-7 days')").run();
}
const decisions = ['accepted', 'rejected'];
const titleOf = payload => JSON.parse(payload).title || '';
// 모집자에게는 신청자 인증값 대신 글마다 다른 짧은 번호만 보여 준다.
async function applicationRef(postId, applicant) { return (await hash(`${postId}:${applicant}`)).slice(0, 32); }
function publicPost(row, owner) { return {...JSON.parse(row.payload), id: row.id, shared: true, mine: !!owner && row.owner_hash === owner, closed: !!row.closed, createdAt: row.created_at, updatedAt: row.updated_at, applicationCount: row.application_count || 0}; }
async function rowById(db, id) { return db.prepare('SELECT * FROM community_posts WHERE id=?').bind(id).first(); }
function allowedOrigin(request, env) {
  const origin = request.headers.get('Origin');
  return !origin || origin === new URL(request.url).origin || (env.COMMUNITY_ALLOWED_ORIGINS || '').split(',').map(x => x.trim()).filter(Boolean).includes(origin);
}
export async function handleCommunity(request, env) {
  if (!allowedOrigin(request, env)) return json({error: '허용되지 않은 사이트 요청이에요.'}, 403);
  const origin = request.headers.get('Origin');
  const response = request.method === 'OPTIONS' ? new Response(null, {status:204}) : await routeCommunity(request, env);
  if (origin) {
    response.headers.set('Access-Control-Allow-Origin', origin);
    response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    response.headers.set('Access-Control-Allow-Headers', 'Authorization, Content-Type');
    response.headers.set('Vary', 'Origin');
  }
  return response;
}
async function routeCommunity(request, env) {
  try {
    if (!env.COMMUNITY_DB) throw new Problem(503, '모집글 공유 연결을 준비 중이에요. 잠시 후 다시 확인해 주세요.');
    const db = env.COMMUNITY_DB, url = new URL(request.url), parts = url.pathname.replace(/^\/api\/community\/?/, '').split('/').filter(Boolean), method = request.method;
    if (!['GET', 'POST', 'PUT', 'DELETE'].includes(method)) throw new Problem(405, '지원하지 않는 요청이에요.');
    if (method !== 'GET') {
      const origin = request.headers.get('Origin');
      if (origin && !allowedOrigin(request, env)) throw new Problem(403, '다른 사이트에서는 등록할 수 없어요.');
    }
    const owner = await identity(request, method !== 'GET');
    if (parts[0] === 'applications' && parts.length === 1 && method === 'GET') {
      // 내가 신청한 모집글과 수락·거절 결과.
      if (!owner) throw new Problem(401, '신청자 인증이 필요해요.');
      const result = await db.prepare('SELECT a.post_id, a.status, a.reason, a.decided_at, a.created_at, a.applicant_seen, p.payload, p.category, p.closed FROM community_applications a JOIN community_posts p ON p.id=a.post_id WHERE a.applicant_hash=? ORDER BY a.created_at DESC LIMIT 100').bind(owner).all();
      return json({items: result.results.map(r => ({postId: r.post_id, title: titleOf(r.payload), category: r.category, closed: !!r.closed, status: r.status, reason: r.reason, decidedAt: r.decided_at || null, createdAt: r.created_at, unread: r.status !== 'pending' && !r.applicant_seen}))});
    }
    if (parts[0] === 'notifications') {
      if (!owner) throw new Problem(401, '알림을 확인하려면 인증이 필요해요.');
      if (parts.length === 1 && method === 'GET') {
        // 모집자: 아직 확인하지 않은 새 신청. 신청자: 아직 확인하지 않은 수락·거절 결과.
        const incoming = await db.prepare('SELECT a.post_id, a.name, a.team, a.created_at, p.payload FROM community_applications a JOIN community_posts p ON p.id=a.post_id WHERE p.owner_hash=? AND a.owner_seen=0 ORDER BY a.created_at DESC LIMIT 50').bind(owner).all();
        const decided = await db.prepare("SELECT a.post_id, a.status, a.reason, a.decided_at, p.payload FROM community_applications a JOIN community_posts p ON p.id=a.post_id WHERE a.applicant_hash=? AND a.applicant_seen=0 AND a.status<>'pending' ORDER BY a.decided_at DESC LIMIT 50").bind(owner).all();
        const items = incoming.results.map(r => ({kind: 'applied', postId: r.post_id, title: titleOf(r.payload), name: r.name, team: r.team, at: r.created_at}))
          .concat(decided.results.map(r => ({kind: r.status, postId: r.post_id, title: titleOf(r.payload), reason: r.reason, at: r.decided_at})))
          .sort((a, b) => b.at - a.at);
        return json({items});
      }
      if (parts.length === 2 && parts[1] === 'read' && method === 'POST') {
        // 화면에 보여 준 시점(before)까지만 읽음 처리해, 그 사이 도착한 알림은 남긴다.
        const before = Number((await readBody(request)).before);
        if (!Number.isInteger(before) || before <= 0) throw new Problem(400, '읽음 시점을 확인해 주세요.');
        await db.prepare('UPDATE community_applications SET owner_seen=1 WHERE owner_seen=0 AND created_at<=? AND post_id IN (SELECT id FROM community_posts WHERE owner_hash=?)').bind(before, owner).run();
        await db.prepare("UPDATE community_applications SET applicant_seen=1 WHERE applicant_seen=0 AND status<>'pending' AND decided_at<=? AND applicant_hash=?").bind(before, owner).run();
        return json({ok: true});
      }
      throw new Problem(405, '지원하지 않는 요청이에요.');
    }
    if (parts[0] !== 'meetings') throw new Problem(404, '페이지를 찾을 수 없어요.');
    if (parts.length === 1 && method === 'GET') {
      const category = url.searchParams.get('category') || '';
      if (category && !categories.includes(category)) throw new Problem(400, '모임 분류를 확인해 주세요.');
      const cursor = url.searchParams.get('cursor') || '';
      if (cursor && !/^\d{13}:[a-f0-9-]{36}$/.test(cursor)) throw new Problem(400, '목록 위치를 확인해 주세요.');
      const [time, id] = cursor.split(':');
      const mine = url.searchParams.get('mine') === '1';
      if (mine && !owner) throw new Problem(401, '작성자 인증이 필요해요.');
      let sql = mine ? 'SELECT * FROM community_posts WHERE owner_hash=?' : 'SELECT * FROM community_posts WHERE closed=0', args = mine ? [owner] : [];
      if (category) { sql += ' AND category=?'; args.push(category); }
      if (cursor) { sql += ' AND (created_at < ? OR (created_at = ? AND id < ?))'; args.push(Number(time), Number(time), id); }
      sql += ' ORDER BY created_at DESC, id DESC LIMIT 31';
      const result = await db.prepare(sql).bind(...args).all(), rows = result.results.slice(0, 30);
      const counts = await db.prepare('SELECT category, COUNT(*) AS count FROM community_posts WHERE closed=0 GROUP BY category').all();
      const last = rows.at(-1);
      return json({items: rows.map(r => publicPost(r, owner)), counts: Object.fromEntries(counts.results.map(r => [r.category, r.count])), nextCursor: result.results.length > 30 ? `${last.created_at}:${last.id}` : null});
    }
    if (parts.length === 1 && method === 'POST') {
      const body = await readBody(request), p = validatePost(body);
      const id = text(body, 'id', 36, true);
      if (!/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(id)) throw new Problem(400, '등록 번호를 확인해 주세요.');
      const old = await rowById(db, id);
      if (old) { if (old.owner_hash !== owner) throw new Problem(409, '등록 번호가 겹쳤어요. 다시 시도해 주세요.'); return json({item: publicPost(old, owner)}); }
      await rate(db, request, owner, 'post');
      const now = Date.now();
      await db.prepare('INSERT INTO community_posts (id, owner_hash, category, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)').bind(id, owner, p.category, JSON.stringify(p), now, now).run();
      return json({item: publicPost(await rowById(db, id), owner)}, 201);
    }
    const id = parts[1];
    if (!id || !/^[a-f0-9-]{36}$/.test(id)) throw new Problem(404, '모집글을 찾을 수 없어요.');
    const row = await rowById(db, id);
    if (!row) throw new Problem(404, '삭제되었거나 없는 모집글이에요.');
    if (parts.length === 2) {
      if (method === 'GET') {
        const item = publicPost(row, owner);
        if (owner && row.owner_hash !== owner) {
          // 신청자가 글을 열면 자기 신청 상태를 함께 보여 주고, 결과 알림은 확인한 것으로 둔다.
          const mine = await db.prepare('SELECT status, reason, decided_at, applicant_seen FROM community_applications WHERE post_id=? AND applicant_hash=?').bind(id, owner).first();
          if (mine) {
            item.myApplication = {status: mine.status, reason: mine.reason, decidedAt: mine.decided_at || null};
            if (!mine.applicant_seen) await db.prepare('UPDATE community_applications SET applicant_seen=1 WHERE post_id=? AND applicant_hash=?').bind(id, owner).run();
          }
        }
        return json({item});
      }
      if (row.owner_hash !== owner) throw new Problem(403, '작성자만 변경할 수 있어요.');
      if (method === 'DELETE') { await db.prepare('DELETE FROM community_posts WHERE id=? AND owner_hash=?').bind(id, owner).run(); return json({ok: true}); }
      if (method === 'PUT') {
        const body = await readBody(request), p = validatePost(body);
        if (p.category !== row.category || typeof body.closed !== 'boolean') throw new Problem(400, '분류와 모집 상태를 확인해 주세요.');
        await rate(db, request, owner, 'update');
        await db.prepare('UPDATE community_posts SET payload=?, closed=?, updated_at=? WHERE id=? AND owner_hash=?').bind(JSON.stringify(p), Number(body.closed), Date.now(), id, owner).run();
        return json({item: publicPost(await rowById(db, id), owner)});
      }
    }
    if (parts.length === 3 && parts[2] === 'applications') {
      if (method === 'GET') {
        if (!owner || row.owner_hash !== owner) throw new Problem(403, '모집자만 신청 내역을 볼 수 있어요.');
        const cursor = url.searchParams.get('cursor') || '';
        if (cursor && !/^\d{1,16}:\d{1,16}$/.test(cursor)) throw new Problem(400, '신청 목록 위치를 확인해 주세요.');
        const [time, position] = cursor.split(':').map(Number);
        if (cursor && (!Number.isSafeInteger(time) || !Number.isSafeInteger(position) || position < 1)) throw new Problem(400, '신청 목록 위치를 확인해 주세요.');
        const boundary = cursor ? ' AND (created_at < ? OR (created_at = ? AND rowid < ?))' : '';
        const result = await db.prepare('SELECT rowid AS position, applicant_hash, name, team, message, contact, created_at, status, reason, decided_at FROM community_applications WHERE post_id=?' + boundary + ' ORDER BY created_at DESC, rowid DESC LIMIT 31').bind(id, ...(cursor ? [time, time, position] : [])).all();
        const rows = result.results.slice(0, 30), items = [];
        // 조회한 신청만 읽음 처리하고, 조회 후 새로 제출된 신청은 남긴다.
        if (rows.length) await db.prepare('UPDATE community_applications SET owner_seen=1 WHERE post_id=? AND (applicant_hash, created_at) IN (' + rows.map(() => '(?, ?)').join(',') + ')').bind(id, ...rows.flatMap(r => [r.applicant_hash, r.created_at])).run();
        for (const r of rows) items.push({ref: await applicationRef(id, r.applicant_hash), name: r.name, team: r.team, message: r.message, contact: r.contact, created_at: r.created_at, status: r.status, reason: r.reason, decidedAt: r.decided_at || null});
        const last = rows.at(-1);
        return json({items, nextCursor: result.results.length > 30 ? `${last.created_at}:${last.position}` : null});
      }
      if (row.owner_hash === owner) throw new Problem(400, '내 모집글에는 신청할 수 없어요.');
      if (method === 'POST') {
        if (row.closed) throw new Problem(409, '모집이 마감되었어요.');
        const body = await readBody(request), name = text(body, 'name', 30, true), message = text(body, 'message', 500), contact = contactLink(text(body, 'contact', 500)), team = text(body, 'team', 1);
        if (row.category === 'dating' && !['m', 'f'].includes(team)) throw new Problem(400, '신청하는 팀을 선택해 주세요.');
        await rate(db, request, owner, 'apply');
        await db.prepare("INSERT INTO community_applications (post_id, applicant_hash, name, team, message, contact, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(post_id, applicant_hash) DO UPDATE SET name=excluded.name, team=excluded.team, message=excluded.message, contact=excluded.contact, created_at=excluded.created_at, status='pending', reason='', decided_at=0, owner_seen=0, applicant_seen=1").bind(id, owner, name, team, message, contact, Date.now()).run();
        return json({ok: true});
      }
      if (method === 'DELETE') { await db.prepare('DELETE FROM community_applications WHERE post_id=? AND applicant_hash=?').bind(id, owner).run(); return json({ok: true}); }
    }
    if (parts.length === 4 && parts[2] === 'applications' && method === 'PUT') {
      // 모집자가 신청을 수락·거절하고 사유를 남긴다. 신청자에게는 결과 알림이 생긴다.
      if (row.owner_hash !== owner) throw new Problem(403, '모집자만 수락·거절할 수 있어요.');
      if (!/^[a-f0-9]{32}$/.test(parts[3])) throw new Problem(404, '신청을 찾을 수 없어요.');
      const body = await readBody(request), status = text(body, 'status', 10, true), reason = text(body, 'reason', 300);
      if (!decisions.includes(status)) throw new Problem(400, '수락 또는 거절을 선택해 주세요.');
      const rows = await db.prepare('SELECT applicant_hash FROM community_applications WHERE post_id=?').bind(id).all();
      let applicant = null;
      for (const r of rows.results) if (await applicationRef(id, r.applicant_hash) === parts[3]) { applicant = r.applicant_hash; break; }
      if (!applicant) throw new Problem(404, '신청을 찾을 수 없어요. 신청자가 취소했을 수 있어요.');
      await rate(db, request, owner, 'decide');
      const now = Date.now();
      await db.prepare('UPDATE community_applications SET status=?, reason=?, decided_at=?, owner_seen=1, applicant_seen=0 WHERE post_id=? AND applicant_hash=?').bind(status, reason, now, id, applicant).run();
      return json({ok: true, status, reason, decidedAt: now});
    }
    throw new Problem(405, '지원하지 않는 요청이에요.');
  } catch (e) { return json({error: e instanceof Problem ? e.message : '공유 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.'}, e instanceof Problem ? e.status : 503); }
}
