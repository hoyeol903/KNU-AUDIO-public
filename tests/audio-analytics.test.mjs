import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../tools/knua-app.html',import.meta.url),'utf8');
function fixture(host='hoyeol903.github.io'){
 const events=[],context={P:{playing:true},location:{hostname:host,protocol:'https:'},gtag:(...args)=>events.push(args)};
 vm.createContext(context);vm.runInContext(source.slice(source.indexOf('var AUDIO_USAGE ='),source.indexOf("A.addEventListener('playing', audioUsageStart)")),context);return{context,events};
}
test('실제 시작만 1회 기록하고 중복 일시정지와 종료를 막는다',()=>{
 const {context:c,events}=fixture();c.P.playing=false;c.audioUsageStart();assert.equal(events.length,0);
 c.P.playing=true;c.audioUsageStart();c.audioUsageStart();c.audioUsagePause();c.audioUsagePause();c.audioUsageStart();c.audioUsageComplete();c.audioUsageComplete();
 assert.deepEqual(events,[['event','briefing_start'],['event','briefing_pause'],['event','briefing_complete']]);
});
test('음성 실패와 구간 건너뛰기는 끝까지 들음으로 집계하지 않는다',()=>{
 const {context:c,events}=fixture();c.audioUsageStart();c.AUDIO_USAGE.skipped=true;c.audioUsageComplete();assert.deepEqual(events,[['event','briefing_start']]);
 assert(source.includes("AUDIO_USAGE.skipped=true; nextAuto()"));
});
test('로컬 테스트는 보내지 않고 분석 도구 실패는 재생에 영향을 주지 않는다',()=>{
 const {context:c,events}=fixture('127.0.0.1');c.audioUsageStart();c.audioUsagePause();assert.deepEqual(events,[]);
 c.location.hostname='example.com';c.gtag=()=>{throw Error('blocked');};assert.doesNotThrow(()=>c.audioUsageStart());
});
