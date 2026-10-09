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
    BRIEF:{segments:[{id:'greeting',script:'안녕하세요.',personal_template:'안녕하세요, {name}님. 좋은 아침이에요!',audio:'hello.mp3',duration_sec:2},
      {id:'intro',script:'겉옷을 챙겨 주세요.',audio:'weather.mp3',duration_sec:3},
      {id:'outro',script:'힘내세요.',audio:'bye.mp3',duration_sec:2}]}};
  vm.createContext(context);vm.runInContext(chapters,context);
  context.CH=context.chapters({boards:[],cafes:[]});vm.runInContext(engine,context);vm.runInContext(cues,context);
  return {context,spoken,audio};
}
{
 const {context:c,spoken,audio}=setup();
 assert.equal(c.CH[0].s,'안녕하세요, 김경민님. 좋은 아침이에요!');
 assert.equal(c.CH.length,3);c.play(0);
 assert.equal(c.mode(),'tts');assert.equal(audio.playCount,0);
 assert.equal(spoken[0].text,'안녕하세요, 김경민님.');
 spoken[spoken.length-1].onend();
 assert.equal(c.P.ch,1);assert.equal(c.mode(),'audio');assert.equal(audio.playCount,1);
}
{
 const {context:c,audio}=setup(false);c.play(0);
 assert.equal(c.mode(),'audio');assert.equal(audio.src,'data/briefing/hello.mp3');
 assert.equal(audio.playCount,1);
}
{
 const {context:c,spoken}=setup();c.play(0);const end=spoken[spoken.length-1].onend;
 c.pause();end();assert.equal(c.P.ch,0);assert.equal(c.P.playing,false);
 c.play();assert.equal(c.mode(),'tts');
 c.S.voice=false;c.startChapter(true);assert.equal(c.A.muted,true);assert.equal(c.A.playCount,1);
}
{
 const {context:c,audio}=setup();c.play(0);c.P.voiceOk=false;c.P.speakAt=-5000;c.tick();
 assert.equal(c.mode(),'audio');assert.equal(audio.playCount,1);assert.equal(c.P.ch,0);
}
console.log('이름 인사·기본 음성 대체·일시정지·무음·다음 구간 연결: 통과');
