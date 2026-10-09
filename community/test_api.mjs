import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {handleCommunity} from './api.mjs';
const sqlite = new DatabaseSync(':memory:');
sqlite.exec(readFileSync(new URL('../migrations/0001_community.sql',import.meta.url),'utf8'));
sqlite.exec(readFileSync(new URL('../migrations/0002_application_decisions.sql',import.meta.url),'utf8'));
const db = {prepare(sql) { let args=[]; const statement=sqlite.prepare(sql); return {bind(...values) {args=values; return this;}, async first(){return statement.get(...args) || null;}, async all(){return {results:statement.all(...args)};}, async run(){return statement.run(...args);}};}};
const owner='a'.repeat(64), other='b'.repeat(64), stranger='c'.repeat(64);
async function call(path='', method='GET', body, token=owner, options={}) { const request=new Request('https://knu-audio.pages.dev/api/community/meetings'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),...options.headers},body:body===undefined?undefined:typeof body==='string'?body:JSON.stringify(body)}); const response=await handleCommunity(request,{COMMUNITY_DB:db}); return {status:response.status,body:await response.json()}; }
const post={id:crypto.randomUUID(),category:'study',title:'토익 함께 공부해요',intro:'자세한 소개\n매주 문제 풀이',when:'화요일 9시',where:'도서관',capacity:5,goal:'토익 800점',requirements:'초보 환영',cost:'무료',contact:'https://open.kakao.com/o/testStudy'};
assert.equal((await handleCommunity(new Request('https://example.com/api/community/meetings'),{})).status,503);
let r=await call('','POST',post); assert.equal(r.status,201); assert.equal(r.body.item.mine,true);
assert(!JSON.stringify(r.body).includes(owner)); assert(!JSON.stringify(r.body).includes('owner_hash'));
assert.equal((await call('','POST',post)).status,200); // Retry is idempotent.
r=await call('','GET',undefined,other); assert.equal(r.body.items.length,1);assert.equal(r.body.items[0].mine,false);assert.equal(r.body.counts.study,1);
assert.equal((await call('/'+post.id,'PUT',{...post,closed:false},other)).status,403);
assert.equal((await call('/'+post.id,'DELETE',undefined,other)).status,403);
assert.equal((await call('','POST',{...post,id:crypto.randomUUID(),contact:'javascript:alert(1)'})).status,400);
// 모집글 참가 문의 링크는 선택이다. 비워도 저장되고 빈 값으로 남는다.
{const id=crypto.randomUUID(),r=await call('','POST',{...post,id,contact:''});assert.equal(r.status,201);assert.equal(r.body.item.contact,'');assert.equal((await call('/'+id,'DELETE')).status,200);}
assert.equal((await call('','POST',{...post,id:crypto.randomUUID(),contact:'https://open.kakao.com.evil.example/o/test'})).status,400);
assert.equal((await call('','POST',{...post,id:crypto.randomUUID(),contact:'https://user:pass@instagram.com/example'})).status,400);
assert.equal((await call('','POST',{...post,id:crypto.randomUUID(),capacity:2.5})).status,400);
assert.equal((await call('','POST',post,null)).status,401);
assert.equal((await call('','POST',post,owner,{headers:{Origin:'https://evil.example'}})).status,403);
const application={name:'참가자',message:'화요일 가능해요',contact:'https://www.instagram.com/testparticipant/',team:''};
assert.equal((await call('/'+post.id+'/applications','POST',{...application,contact:'https://example.com/me'},other)).status,400); // 링크를 적었다면 인스타그램·오픈카톡만.
assert.equal((await call('/'+post.id+'/applications','POST',application,other)).status,200);
assert.equal((await call('/'+post.id+'/applications','POST',application,other)).status,200);
assert.equal((await call('/'+post.id,'GET',undefined,other)).body.item.applicationCount,1);
assert.equal((await call('/'+post.id+'/applications','GET',undefined,other)).status,403);
assert.equal((await call('/'+post.id+'/applications','GET',undefined,null)).status,403);
r=await call('/'+post.id+'/applications');assert.equal(r.body.items.length,1);assert.equal(r.body.items[0].contact,application.contact);assert(!JSON.stringify(r.body).includes('applicant_hash'));
assert.equal((await call('/'+post.id+'/applications','DELETE',undefined,stranger)).status,200);
assert.equal((await call('/'+post.id)).body.item.applicationCount,1);
assert.equal((await call('/'+post.id+'/applications','DELETE',undefined,other)).status,200);
assert.equal((await call('/'+post.id)).body.item.applicationCount,0);
// 신청 연락 링크도 선택이다. 비워도 신청되고 모집자에게는 빈 값으로 보인다.
assert.equal((await call('/'+post.id+'/applications','POST',{...application,contact:''},stranger)).status,200);
r=await call('/'+post.id+'/applications');assert.equal(r.body.items.length,1);assert.equal(r.body.items[0].contact,'');
assert.equal((await call('/'+post.id+'/applications','DELETE',undefined,stranger)).status,200);
assert.equal((await call('/'+post.id,'PUT',{...post,closed:true})).status,200);
assert.equal((await call()).body.items.length,0);
assert.equal((await call('?mine=1')).body.items.length,1);
assert.equal((await call('/'+post.id+'/applications','POST',application,other)).status,409);
assert.equal((await call('/'+post.id,'PUT',{...post,closed:false})).status,200);
for (const category of ['dating','club']) { const b={...post,id:crypto.randomUUID(),category,team:'m',size:'3:3',activity:'사진 산책'};assert.equal((await call('','POST',b)).status,201); }
// Pagination without duplicates at identical creation times.
for (let i=0;i<35;i++) { const id=crypto.randomUUID();sqlite.prepare('INSERT INTO community_posts(id,owner_hash,category,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)').run(id,'x','study',JSON.stringify(post),1700000000000,1700000000000); }
r=await call('?category=study');assert.equal(r.body.items.length,30);assert(r.body.nextCursor);
const next=await call('?category=study&cursor='+encodeURIComponent(r.body.nextCursor));assert.equal(next.body.items.length,6);assert.equal(new Set([...r.body.items,...next.body.items].map(p=>p.id)).size,36);
for(let i=0;i<20;i++) await call('','POST',{...post,id:crypto.randomUUID()},stranger);
assert.equal((await call('','POST',{...post,id:crypto.randomUUID()},stranger)).status,429);
assert.equal((await call('/'+post.id+'/applications','POST',application,other)).status,200);
assert.equal((await call('/'+post.id,'DELETE')).status,200);
assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM community_applications WHERE post_id=?').get(post.id).n,0);
assert.equal((await call('/'+post.id)).status,404);
// GitHub Pages cross-origin access is allowed only after explicit backend configuration.
const ghOrigin='https://hoyeol903.github.io';
const preflight=new Request('https://api.example.com/api/community/meetings',{method:'OPTIONS',headers:{Origin:ghOrigin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'}});
assert.equal((await handleCommunity(preflight,{COMMUNITY_DB:db})).status,403);
const crossEnv={COMMUNITY_DB:db,COMMUNITY_ALLOWED_ORIGINS:ghOrigin};
const cors=await handleCommunity(preflight,crossEnv);assert.equal(cors.status,204);assert.equal(cors.headers.get('Access-Control-Allow-Origin'),ghOrigin);
const crossRead=await handleCommunity(new Request('https://api.example.com/api/community/meetings',{headers:{Origin:ghOrigin}}),crossEnv);assert.equal(crossRead.status,200);assert.equal(crossRead.headers.get('Access-Control-Allow-Origin'),ghOrigin);
const crossWrite=await handleCommunity(new Request('https://api.example.com/api/community/meetings',{method:'POST',headers:{Origin:ghOrigin,Authorization:'Bearer '+other,'Content-Type':'application/json'},body:JSON.stringify({...post,id:crypto.randomUUID()})}),crossEnv);assert.equal(crossWrite.status,201);assert.equal(crossWrite.headers.get('Access-Control-Allow-Origin'),ghOrigin);
assert.equal((await handleCommunity(new Request('https://api.example.com/api/community/meetings',{headers:{Origin:'https://evil.example'}}),crossEnv)).status,403);
// 수락·거절과 알림: 모집자는 새 신청을, 신청자는 수락·거절 결과와 사유를 알림으로 받는다.
async function api(path, method='GET', body, token=owner) { const request=new Request('https://knu-audio.pages.dev/api/community/'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body===undefined?undefined:JSON.stringify(body)}); const response=await handleCommunity(request,{COMMUNITY_DB:db}); return {status:response.status,body:await response.json()}; }
const p2={...post,id:crypto.randomUUID(),title:'알림 시험 스터디'};
assert.equal((await call('','POST',p2)).status,201);
assert.equal((await api('notifications','GET',undefined,null)).status,401);
assert.equal((await call('/'+p2.id+'/applications','POST',application,other)).status,200);
r=await api('notifications');assert.equal(r.body.items.length,1);assert.equal(r.body.items[0].kind,'applied');assert.equal(r.body.items[0].name,'참가자');assert.equal(r.body.items[0].title,'알림 시험 스터디');
assert.equal((await api('notifications','GET',undefined,other)).body.items.length,0);
r=await call('/'+p2.id+'/applications');assert.equal(r.body.items[0].status,'pending');assert.match(r.body.items[0].ref,/^[a-f0-9]{32}$/);assert(!JSON.stringify(r.body).includes(other));
const ref=r.body.items[0].ref;
assert.equal((await api('notifications')).body.items.length,0); // 신청 내역을 열면 새 신청 알림은 확인한 것으로 둔다.
assert.equal((await call('/'+p2.id+'/applications/'+ref,'PUT',{status:'rejected',reason:'x'},other)).status,403);
assert.equal((await call('/'+p2.id+'/applications/'+ref,'PUT',{status:'maybe'})).status,400);
assert.equal((await call('/'+p2.id+'/applications/'+'0'.repeat(32),'PUT',{status:'accepted'})).status,404);
assert.equal((await call('/'+p2.id+'/applications/'+ref,'PUT',{status:'rejected',reason:'x'.repeat(301)})).status,400);
assert.equal((await call('/'+p2.id+'/applications/'+ref,'PUT',{status:'rejected',reason:'인원이 다 찼어요'})).status,200);
r=await api('notifications','GET',undefined,other);assert.equal(r.body.items.length,1);assert.equal(r.body.items[0].kind,'rejected');assert.equal(r.body.items[0].reason,'인원이 다 찼어요');
r=await api('applications','GET',undefined,other);assert.equal(r.body.items[0].postId,p2.id);assert.equal(r.body.items[0].status,'rejected');assert.equal(r.body.items[0].unread,true);
r=await call('/'+p2.id,'GET',undefined,other);assert.equal(r.body.item.myApplication.status,'rejected');assert.equal(r.body.item.myApplication.reason,'인원이 다 찼어요');
assert.equal((await api('notifications','GET',undefined,other)).body.items.length,0); // 글을 열면 결과 알림은 확인한 것으로 둔다.
assert.equal((await call('/'+p2.id,'GET',undefined,stranger)).body.item.myApplication,undefined);
// 다시 신청하면 대기 상태로 돌아가고 모집자에게 새 신청 알림이 간다.
assert.equal((await call('/'+p2.id+'/applications','POST',{...application,message:'다시 신청해요'},other)).status,200);
r=await call('/'+p2.id,'GET',undefined,other);assert.equal(r.body.item.myApplication.status,'pending');assert.equal(r.body.item.myApplication.reason,'');
assert.equal((await api('notifications')).body.items.length,1);
assert.equal((await api('notifications/read','POST',{before:0})).status,400);
assert.equal((await api('notifications/read','POST',{before:1})).status,200);
assert.equal((await api('notifications')).body.items.length,1); // 읽음 시점 이후의 알림은 남는다.
assert.equal((await api('notifications/read','POST',{before:Date.now()})).status,200);
assert.equal((await api('notifications')).body.items.length,0);
assert.equal((await call('/'+p2.id+'/applications/'+ref,'PUT',{status:'accepted',reason:''})).status,200);
r=await api('notifications','GET',undefined,other);assert.equal(r.body.items.length,1);assert.equal(r.body.items[0].kind,'accepted');
assert.equal((await api('notifications/read','POST',{before:Date.now()},other)).status,200);
assert.equal((await api('notifications','GET',undefined,other)).body.items.length,0);
r=await api('applications','GET',undefined,other);assert.equal(r.body.items[0].status,'accepted');assert.equal(r.body.items[0].unread,false);
assert.equal((await call('/'+p2.id,'DELETE')).status,200);
assert.equal((await api('applications','GET',undefined,other)).body.items.length,0); // 글이 지워지면 신청과 알림도 사라진다.
console.log('Community API: sharing, private applications, decisions and notifications, ownership, validation, idempotency, pagination, rate limits and deletion passed.');

// 101건과 같은 시각의 신청도 누락 없이 넘기고, 보여 주지 않은 신청은 읽음 처리하지 않는다.
{
 const id=crypto.randomUUID(); assert.equal((await call('', 'POST', {...post,id})).status,201);
 for(let i=0;i<101;i++) sqlite.prepare('INSERT INTO community_applications (post_id,applicant_hash,name,team,message,contact,created_at) VALUES (?,?,?,?,?,?,?)').run(id,'page-'+i,'신청'+i,'','','',1000);
 let cursor='',refs=[];
 do {
  const page=await call('/'+id+'/applications'+(cursor?'?cursor='+encodeURIComponent(cursor):''));
  assert.equal(page.status,200); assert(page.body.items.length<=30);
  refs.push(...page.body.items.map(a=>a.ref));
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM community_applications WHERE post_id=? AND owner_seen=1').get(id).n,refs.length);
  cursor=page.body.nextCursor;
 }while(cursor);
 assert.equal(refs.length,101);assert.equal(new Set(refs).size,101);
 assert.equal((await call('/'+id+'/applications?cursor=invalid')).status,400);
 assert.equal((await call('/'+id+'/applications?cursor=1000:0')).status,400);
 assert.equal((await call('/'+id+'/applications?cursor=1000:1','GET',undefined,other)).status,403);
 // 조회 뒤 다시 제출된 신청은 옛 응답으로 읽음 처리하지 않는다.
 sqlite.prepare('UPDATE community_applications SET owner_seen=0 WHERE post_id=?').run(id);
 const prepare=db.prepare;let changed;
 db.prepare=function(query){
  const statement=prepare.call(this,query);
  if(query.startsWith('SELECT rowid AS position')){
   const all=statement.all;
   statement.all=async function(){const result=await all.call(this);changed=result.results[0].applicant_hash;sqlite.prepare('UPDATE community_applications SET created_at=2000 WHERE post_id=? AND applicant_hash=?').run(id,changed);return result;};
  }
  return statement;
 };
 try{assert.equal((await call('/'+id+'/applications')).status,200);}finally{db.prepare=prepare;}
 assert.equal(sqlite.prepare('SELECT owner_seen FROM community_applications WHERE post_id=? AND applicant_hash=?').get(id,changed).owner_seen,0);
 await call('/'+id,'DELETE');
}
