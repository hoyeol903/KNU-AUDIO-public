import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../tools/knua-app.html',import.meta.url),'utf8');
const code=html.slice(html.indexOf('function loadApplicants('),html.indexOf('function saveDecision('));
function setup(request){
 const c={COMMUNITY:{detail:{id:'post',mine:true},applicants:null},S:{meetId:'post'},NOTE:{items:[]},render(){},checkNotes(){},toastMsg(){},communityRequest:request};
 vm.runInNewContext(code,c);return c;
}
test('신청을 더 불러오면 누적하고 중복 신청은 최신 내용으로 갱신한다',async()=>{
 const paths=[],pages=[{items:[{ref:'one',name:'처음'}],nextCursor:'1000:30'},{items:[{ref:'one',name:'수정'},{ref:'two'}],nextCursor:null}];
 const c=setup(async p=>{paths.push(p);return pages.shift();});
 await c.loadApplicants();await c.loadApplicants(true);
 assert.equal(c.COMMUNITY.applicants.length,2);assert.equal(c.COMMUNITY.applicants[0].name,'수정');
 assert.equal(paths[1],'meetings/post/applications?cursor=1000%3A30');assert.equal(c.COMMUNITY.applicantsCursor,null);assert.equal(c.COMMUNITY.applicantsBusy,false);
});
test('중복 요청과 다른 모집글의 늦은 응답을 막는다',async()=>{
 let resolve,count=0;const c=setup(()=>{count++;return new Promise(r=>{resolve=r;});});
 const pending=c.loadApplicants();c.loadApplicants();assert.equal(count,1);
 c.S.meetId='other';resolve({items:[{ref:'one'}],nextCursor:null});await pending;
 assert.equal(c.COMMUNITY.applicants,null);
});
test('더 보기 실패는 기존 신청과 다음 위치를 유지한다',async()=>{
 const c=setup(async()=>{throw Error('network');});c.COMMUNITY.applicants=[{ref:'one'}];c.COMMUNITY.applicantsCursor='1000:30';
 await c.loadApplicants(true);assert.equal(c.COMMUNITY.applicants.length,1);assert.equal(c.COMMUNITY.applicantsCursor,'1000:30');assert.equal(c.COMMUNITY.applicantsBusy,false);
});
