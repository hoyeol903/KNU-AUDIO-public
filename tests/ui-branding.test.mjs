import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../tools/knua-app.html',import.meta.url),'utf8');
function moods(weather={status:'ok',summary:'맑음',rain:0}) {
 const c=vm.createContext({DATA:{weather},P:{playing:true,done:false,ch:0,chT:0},CH:[]});
 vm.runInContext(html.slice(html.indexOf('function sentences('),html.indexOf('function chStart(')),c);
 vm.runInContext(html.slice(html.indexOf('var HOB_MOODS ='),html.indexOf('function hobImage(')),c);
 return c;
}
test('브리핑 ID, 종류와 문장 위치에 따라 호반우가 바뀐다',()=>{
 const c=moods();
 for(const [segment,expected] of [
  [{id:'greeting'},'greeting'],[{id:'empty'},'empty'],[{id:'outro'},'outro'],
  [{id:'meal-46'},'meal'],[{cards:[{kind:'학식'}]},'meal'],
  [{id:'notice-a',cards:[{kind:'소식'},{kind:'마감 임박'}]},'deadline'],
  [{id:'notice-a',cards:[{kind:'소식'}]},'news']
 ]) assert.equal(c.moodOf(segment),expected);
 const intro={id:'intro',s:'안녕하세요. 오늘 날씨는 맑음입니다.',est:12,cards:[{kind:'날씨'}]};
 assert.equal(c.moodOf(intro,0),'greeting');assert.equal(c.moodOf(intro,11),'sun');
});
test('비·눈·흐림·실패·누락 자료를 맑음으로 추측하지 않는다',()=>{
 for(const [weather,key] of [
  [{status:'ok',summary:'맑음',rain:60},'rain'],[{status:'ok',summary:'소나기',rain:10},'rain'],
  [{status:'ok',summary:'눈',rain:80},'snow'],[{status:'ok',summary:'구름 많음',rain:0},'weather'],
  [{status:'failed',summary:'맑음',rain:0},'weather'],[null,'weather'],
  [{status:'ok',summary:'맑음',rain:0},'sun'],[{status:'ok',summary:'흐림',rain_prob:70},'rain']
 ]) assert.equal(moods(weather).weatherMood(),key);
});
test('일시정지는 기본 자세, 재생 완료는 마무리 인사',()=>{
 const c=moods();c.CH=[{id:'meal-46'}];
 assert.equal(c.liveMood(),'meal');c.P.playing=false;assert.equal(c.liveMood(),'idle');
 c.P.done=true;assert.equal(c.liveMood(),'outro');
});
function splash(reduced=false){
 let now=0,id=0,renders=0;const timers=new Map();
 const els={view:{},overlay:{},splash:{hidden:false,contains:()=>false,classList:{add(){}}},splashSkip:{focus(){}}};
 const c=vm.createContext({$:key=>els[key],window:{matchMedia:()=>({matches:reduced})},document:{activeElement:null},
  performance:{now:()=>now},render(){renders++},setTimeout(fn,ms){timers.set(++id,{at:now+ms,fn});return id},clearTimeout:id=>timers.delete(id)});
 vm.runInContext(html.slice(html.indexOf('var SPLASH ='),html.indexOf('/* ---------- 호반우:')),c);
 c.bootSplash();
 return {c,els,get renders(){return renders},advance(ms){const until=now+ms;for(;;){const first=[...timers].filter(([,v])=>v.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!first)break;const [key,v]=first;now=v.at;timers.delete(key);v.fn()}now=until}};
}
test('빠른 로딩도 1.2초 표시 후 사라지고 화면 입력을 복구한다',()=>{
 const s=splash();s.c.splashReady();s.advance(1199);assert.equal(s.els.splash.hidden,false);
 s.advance(181);assert.equal(s.els.splash.hidden,true);assert.equal(s.els.view.inert,false);assert.equal(s.renders,1);
});
test('느리거나 영원히 응답하지 않는 요청도 2.5초 안에 스플래시 종료',()=>{
 const s=splash();s.advance(2499);assert.equal(s.els.splash.hidden,false);s.advance(1);assert.equal(s.els.splash.hidden,true);
 s.c.splashReady();s.advance(3000);assert.equal(s.renders,1);
});
test('누르기·오류 시 즉시 종료, 모션 줄이기에서는 150ms',()=>{
 const click=splash();click.c.dismissSplash(true);assert.equal(click.els.splash.hidden,true);click.advance(3000);assert.equal(click.renders,1);
 const r=splash(true);r.c.splashReady();r.advance(149);assert.equal(r.els.splash.hidden,false);r.advance(1);assert.equal(r.els.splash.hidden,true);
});

test('2.45초에 응답해도 사라지는 전환까지 2.5초 안에 끝난다',()=>{
 const s=splash();s.advance(2450);s.c.splashReady();s.advance(49);assert.equal(s.els.splash.hidden,false);s.advance(1);assert.equal(s.els.splash.hidden,true);
});

function exchangeHelpers(){
 const start=html.indexOf('var MEET_CATEGORIES ='),end=html.indexOf('var MEET_SAMPLES =');
 const c=vm.createContext({});vm.runInContext(html.slice(start,end),c);return c;
}
function exchangeStorage(localStorage){
 const start=html.indexOf("var KEY = 'knua-app-v1';"),end=html.indexOf('var S = {',start);
 const c=vm.createContext({localStorage});vm.runInContext(html.slice(start,end),c);return c;
}
test('교류 분류 필터와 로컬 모임 생성·재로드, 과팅 저장값 하위호환',()=>{
 const c=exchangeHelpers();
 const groups=['study','club'].map((category,i)=>c.createLocalGroup({category,title:'모임 '+i,intro:'소개 '+i,capacity:'6'},'local-'+i,{dept:'전자공학부',college:'IT대학'}));
 const memory=new Map(),localStorage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)};
 const before=exchangeStorage(localStorage);before.store.meetMine=groups;before.save();
 const reloaded=exchangeStorage(localStorage).store.meetMine;
 assert.equal(c.meetCategory({id:'old-meet'}),'dating');
 assert.equal(c.filterMeetings(reloaded,'study').length,1);
 assert.equal(c.filterMeetings(reloaded,'club')[0].capacity,6);
 assert.deepEqual(JSON.parse(JSON.stringify([reloaded[0].title,reloaded[0].intro,reloaded[0].category])),['모임 0','소개 0','study']);
});
