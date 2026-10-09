import assert from 'node:assert/strict';
import {mkdtempSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {once} from 'node:events';
import {createCommunityServer} from './server.mjs';
const dir=mkdtempSync(join(tmpdir(),'knua-oracle-test-'));
const config={databasePath:join(dir,'community.sqlite'),allowedOrigins:'https://hoyeol903.github.io'};
let server,base;
async function start(){server=createCommunityServer(config);server.listen(0,'127.0.0.1');await once(server,'listening');base='http://127.0.0.1:'+server.address().port;}
async function stop(){await new Promise((resolve,reject)=>server.close(err=>err?reject(err):resolve()));}
const owner='a'.repeat(64),other='b'.repeat(64);
async function call(path,method='GET',body,token=owner,origin='https://hoyeol903.github.io'){
 return fetch(base+'/api/community/'+path,{method,headers:{Origin:origin,Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body===undefined?{}:{body:typeof body==='string'?body:JSON.stringify(body)})});
}
try {
 await start();
 assert.equal((await fetch(base+'/health')).status,200);
 assert.equal((await fetch(base+'/community.sqlite')).status,404);
 const preflight=await call('meetings','OPTIONS');assert.equal(preflight.status,204);assert.equal(preflight.headers.get('Access-Control-Allow-Origin'),'https://hoyeol903.github.io');
 assert.equal((await call('meetings','GET',undefined,other,'https://evil.example')).status,403);
 const post={id:crypto.randomUUID(),category:'study',title:'Oracle 저장 테스트',intro:'서버 재시작 후에도 보이는 모집글',when:'화요일',capacity:5,goal:'토익',contact:'https://open.kakao.com/o/test'};
 assert.equal((await call('meetings','POST',post)).status,201);
 assert.equal((await call('meetings','POST',post)).status,200);
 assert.equal((await call('meetings/'+post.id,'DELETE',undefined,other)).status,403);
 const apply={name:'참가자',message:'참가 요청',contact:'https://instagram.com/test/'};
 assert.equal((await call('meetings/'+post.id+'/applications','POST',apply,other)).status,200);
 assert.equal((await call('meetings/'+post.id+'/applications','GET',undefined,other)).status,403);
 assert.equal((await (await call('meetings/'+post.id+'/applications')).json()).items.length,1);
 assert.equal((await call('meetings','POST','x'.repeat(16001))).status,413);
 const anonymous=await fetch(base+'/api/community/meetings',{headers:{Origin:'https://hoyeol903.github.io'}});const shared=await anonymous.json();assert.equal(shared.items.length,1);assert.equal(shared.items[0].mine,false);assert(!JSON.stringify(shared).includes('owner_hash'));assert(!JSON.stringify(shared).includes(apply.contact));
 await stop();await start();
 assert.equal((await (await call('meetings','GET',undefined,other)).json()).items[0].title,post.title);
 assert.equal((await call('meetings/'+post.id,'DELETE')).status,200);
 assert.equal((await (await call('meetings')).json()).items.length,0);
 console.log('Oracle HTTP server: cross-browser sharing, persistence after restart, CORS, private applications, ownership and body limit passed');
} finally {if(server?.listening) await stop();rmSync(dir,{recursive:true,force:true});}
