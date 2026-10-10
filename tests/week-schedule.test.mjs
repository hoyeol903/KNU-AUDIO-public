import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../tools/knua-app.html',import.meta.url),'utf8');
function fixture(){
 const c={YEAR:{items:[{title:'논문심사료 납부',start:'2026-10-14',end:'2026-10-15'},{title:'위촉 승인',start:'2026-10-15',end:null}]},W:{schedule:[]}};
 vm.createContext(c);
 for(const name of ['schedOn','calItems','calOn']){
  const begin=source.indexOf('function '+name+'('),end=source.indexOf('\n',begin);
  vm.runInContext(source.slice(begin,end),c);
 }
 return c;
}
test('홈은 3일 요약이 비어도 전체 일정의 4~5일 뒤 일정과 종료일을 표시한다',()=>{
 const c=fixture();assert.equal(c.schedOn('2026-10-14').length,1);assert.equal(c.schedOn('2026-10-15').length,2);assert.equal(c.schedOn('2026-10-16').length,0);
});
test('전체 일정 조회 실패 시 기존 요약을 사용하고 모두 없으면 빈 목록이다',()=>{
 const c=fixture();c.YEAR=null;c.W.schedule=[{start:'2026-10-10',end:null}];assert.equal(c.schedOn('2026-10-10').length,1);c.W.schedule=null;assert.equal(c.schedOn('2026-10-10').length,0);
});
test('전체 일정이 있으면 요약 실패를 수집 실패로 표시하지 않고 원본과 배포본이 일치한다',()=>{
 const week=source.slice(source.indexOf('function vWeek(){'),source.indexOf("return h + '</section>';",source.indexOf('function vWeek(){')));
 assert(week.includes('if (!YEAR && !W.schedule)'));
 assert(week.includes('wk.some(function(d){ return schedOn(d).length; })'));
 assert.equal(source,readFileSync(new URL('../output/app/index.html',import.meta.url),'utf8'));
});
