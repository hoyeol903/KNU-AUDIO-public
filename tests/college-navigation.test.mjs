import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../tools/knua-app.html',import.meta.url),'utf8');
const departments=[{id:'kor',college:'인문대학',dept:'국어국문학과'},{id:'history',college:'인문대학',dept:'사학과'},{id:'ai',college:'IT대학',dept:'인공지능전공'},{id:'free',college:'자율전공학부',dept:'자율전공학부'}];
function college(){const c=vm.createContext({DATA:{departments},S:{startCollege:'',startQuery:'',startDept:null},esc:s=>s,avatar:()=>'',IC:{check:''}});vm.runInContext(html.slice(html.indexOf('function collegeOptions(){'),html.indexOf('/* 4-1 시작 */')),c);return c;}
test('대학을 고르기 전에는 전체 학과를 나열하지 않는다',()=>{const c=college();assert.match(c.deptList(),/대학을 선택하면/);assert.doesNotMatch(c.deptList(),/data-act="dept"/);assert.equal((c.collegeOptions().match(/data-college="인문대학"/g)||[]).length,1);assert.match(c.collegeOptions(),/자율전공학부/);});
test('선택한 대학의 학과만 보이고 대학 내 검색과 선택 표시를 유지한다',()=>{const c=college();c.S.startCollege='인문대학';assert.match(c.deptList(),/국어국문학과/);assert.match(c.deptList(),/사학과/);assert.doesNotMatch(c.deptList(),/인공지능전공/);c.S.startQuery='사학';c.S.startDept='history';assert.doesNotMatch(c.deptList(),/국어국문학과/);assert.match(c.deptList(),/aria-pressed="true"/);c.S.startQuery='없는과';assert.match(c.deptList(),/맞는 학과가 없어요/);});
function historySetup(){
 const handlers={},stack=[],renders=[];let position=-1;const sc={scrollTop:0};
 const c=vm.createContext({S:{route:'home',loadPhase:null,startQuery:'',startCollege:'',startDept:null},DATA:{},JSON,
 document:{querySelector:()=>sc},profileOk:()=>true,refresh(){},loadBoard(){},loadCommunity(){},loadInbox(){},openMeeting(){},render(){c.syncAppHistory();renders.push(c.S.route);},
 window:{addEventListener(k,fn){handlers[k]=fn;},history:{
 replaceState(v){const copy=structuredClone(v);if(position<0){stack.push(copy);position=0;}else stack[position]=copy;},
 pushState(v){stack.splice(position+1);stack.push(structuredClone(v));position++;},
 back(){if(position>0){position--;queueMicrotask(()=>handlers.popstate({state:structuredClone(stack[position])}));}},
 forward(){if(position+1<stack.length){position++;queueMicrotask(()=>handlers.popstate({state:structuredClone(stack[position])}));}}
 }}});
 vm.runInContext(html.slice(html.indexOf('var lastRoute = null;'),html.indexOf('function render(animate)')),c);
 return {c,sc,stack,renders};
}
test('휴대폰 뒤로·앞으로 가기는 이전 화면과 목록 스크롤을 복원한다',async()=>{const {c,sc,stack}=historySetup();c.render();sc.scrollTop=420;c.nav('board',{boardId:'notice'});assert.equal(stack.length,2);c.window.history.back();await Promise.resolve();assert.equal(c.S.route,'home');assert.equal(sc.scrollTop,420);c.window.history.forward();await Promise.resolve();assert.equal(c.S.route,'board');assert.equal(c.S.boardId,'notice');});
test('공지 상세창은 뒤로 가기로 먼저 닫히며 화면 갱신은 방문 기록을 늘리지 않는다',async()=>{const {c,stack}=historySetup();c.render();c.nav('board',{boardId:'notice'});c.S.sheet={b:'notice',id:'post'};c.render();assert.equal(stack.length,3);c.render();assert.equal(stack.length,3);c.window.history.back();await Promise.resolve();assert.equal(c.S.route,'board');assert.equal(c.S.sheet,null);});
test('앱 뒤로 버튼도 같은 기록을 사용하고 대학 선택은 이전 화면에서 유지된다',async()=>{const {c}=historySetup();c.S.route='start';c.render();c.S.startCollege='인문대학';c.S.startDept='history';c.nav('pick',{pickMode:'first'});assert.equal(c.appBack(),true);await Promise.resolve();assert.equal(c.S.route,'start');assert.equal(c.S.startCollege,'인문대학');assert.equal(c.S.startDept,'history');assert.equal(c.appBack(),false);});
test('상세창의 닫기 버튼으로 닫은 뒤 뒤로 가도 다시 열리지 않는다',async()=>{const {c}=historySetup();c.render();c.nav('board',{boardId:'notice'});c.S.sheet={b:'notice',id:'post'};c.render();c.S.sheet=null;c.render();await Promise.resolve();assert.equal(c.S.sheet,null);c.appBack();await Promise.resolve();assert.equal(c.S.route,'home');});
test('학과 목록은 열린 대학 카드 바로 아래 하나만 표시되고 접으면 숨겨진다',()=>{const c=college();c.S.startCollege='인문대학';let h=c.collegeOptions();assert.equal((h.match(/id="deptList"/g)||[]).length,1);assert.ok(h.indexOf('국어국문학과')<h.indexOf('data-college="IT대학"'));assert.match(h,/aria-expanded="true"/);c.S.startCollegeCollapsed=true;assert.doesNotMatch(c.collegeOptions(),/id="deptList"/);c.S.startCollegeCollapsed=false;c.S.startCollege='IT대학';h=c.collegeOptions();assert.match(h,/인공지능전공/);assert.doesNotMatch(h,/국어국문학과/);});
