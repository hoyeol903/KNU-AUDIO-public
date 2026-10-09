const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../knua-app.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script); // 앱 전체 문법
assert.equal(html, fs.readFileSync(path.join(__dirname, '../../output/app/index.html'), 'utf8'));
const chapters = script.slice(script.indexOf('function chapters(W)'), script.indexOf('var W = null, CH = []'));
const engine = script.slice(script.indexOf('var A = new Audio()'), script.indexOf('/* ---------- 화면 ---------- */'));
const cues = script.slice(script.indexOf('function sentences(t)'), script.indexOf('/* 말풍선 상태:'));
function setup(korean = true) {
  const spoken = [];
  const audio = { duration: 2, currentTime: 0, playCount: 0, pauseCount: 0, attrs: {},
    addEventListener(){}, pause(){this.pauseCount++;}, play(){this.playCount++;return Promise.resolve();},
    getAttribute(k){return this.attrs[k];}, setAttribute(k,v){this.attrs[k]=v;} };
  const speech = { getVoices(){return korean ? [{lang:'ko-KR'}] : [];}, cancel(){}, speak(u){spoken.push(u);} };
  const context = { Audio: function(){return audio;}, window: {speechSynthesis:speech}, speechSynthesis:speech,
    SpeechSynthesisUtterance:function(text){this.text=text;}, performance:{now:()=>1000},
    setTimeout(){}, setInterval(fn){context.tick=fn;}, navigator:{}, render(){}, media(){}, paintProgress(){}, toastMsg(){},
    store:{name:'김경민'}, S:{voice:true,speed:1}, P:{ch:0,chT:0,gen:0,fallback:false,playToken:0}, BGM_TRACK:null, BRIEF_OLD:false,
    BRIEF:{segments:[{id:'greeting',script:'안녕하세요. 좋은 아침이에요!',personal_template:'안녕하세요, {name}님. 좋은 아침이에요!',audio:'hello.mp3',duration_sec:2},
      {id:'intro',script:'겉옷을 챙겨 주세요.',audio:'weather.mp3',duration_sec:3},
      {id:'outro',script:'힘내세요.',audio:'bye.mp3',duration_sec:2}]}};
  vm.createContext(context);vm.runInContext(chapters,context);
  context.CH=context.chapters({boards:[],cafes:[]});vm.runInContext(engine,context);vm.runInContext(cues,context);
  return {context,spoken,audio};
}
{
 const {context:c,spoken,audio}=setup();
 assert.equal(c.CH[0].s,'안녕하세요. 좋은 아침이에요!');
 assert.equal(c.CH[0].personalGreeting,undefined);
 assert.equal(c.CH.length,3);c.play(0);
 assert.equal(c.mode(),'audio');assert.equal(audio.playCount,1);
 assert.equal(audio.src,'data/briefing/hello.mp3');
 assert.equal(spoken.length,0); // 저장 이름이나 예전 template으로 기기 음성을 부르지 않는다
}
{
 const {context:c,audio}=setup(false);c.play(0);
 assert.equal(c.mode(),'audio');assert.equal(audio.src,'data/briefing/hello.mp3');
 assert.equal(audio.playCount,1);
}
{
 const {context:c}=setup();c.play(0);
 c.pause();assert.equal(c.P.ch,0);assert.equal(c.P.playing,false);
 c.play();assert.equal(c.mode(),'audio');
 c.S.voice=false;c.startChapter(true);assert.equal(c.A.muted,true);
}
console.log('고정 생성 인사·예전 이름 template 무시·일시정지·무음: 통과');
