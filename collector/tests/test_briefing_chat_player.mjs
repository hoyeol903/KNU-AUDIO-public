// Run: node collector/tests/test_briefing_chat_player.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../../tools/knua-app.html', import.meta.url), 'utf8');
const script = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));
new vm.Script(script); // Catch syntax errors in the entire app, too.
const helpers = html.slice(html.indexOf('function sentences('), html.indexOf('/* 말풍선 상태:'));
const engine = html.slice(html.indexOf('function mode('), html.indexOf('function paintProgress('));
let now = 0, tick, queue = [], painted = [];
const audio = {paused:true, readyState:1, currentTime:0, attrs:{}, events:{},
  getAttribute(k){return this.attrs[k];}, setAttribute(k,v){this.attrs[k]=v;},
  addEventListener(k,fn){this.events[k]=fn;}, pause(){this.paused=true;}, play(){this.paused=false;}};
const speech = {getVoices:()=>[{lang:'ko-KR'}], cancel(){queue=[];}, speak(u){queue.push(u);}};
const c = vm.createContext({console, A:audio, P:{ch:0,chT:0,gen:0,playing:false,last:0},
  S:{voice:true,speed:1}, CH:[], window:{speechSynthesis:speech}, speechSynthesis:speech,
  SpeechSynthesisUtterance:class {constructor(text){this.text=text;}},
  performance:{now:()=>now}, setInterval:fn=>{tick=fn;}, navigator:{},
  audioUrl:x=>x, startBgm(){}, stopBgm(){}, toastMsg(){}, render(){},
  paintProgress(){painted.push(c.sentAt(c.CH[c.P.ch],c.P.chT));}});
vm.runInContext(helpers, c);vm.runInContext(engine, c);
const greeting={s:'안녕하세요. 좋은 아침이에요! 소식을 전해요.',personal_template:'안녕하세요, {name}님.',audio:'greeting.mp3',est:8,cues:[]};
c.CH=[greeting];c.play(0);
assert.equal(c.mode(),'audio');
assert.equal(queue.length,0); // Legacy personal_template is ignored; the recorded Sohee greeting plays.
assert.equal(c.chatText(greeting),greeting.s);
greeting.audio=null;c.P.playing=false;c.P.fallback=false;c.play(0);
assert.equal(c.mode(),'tts');
assert.equal(queue[0].text,'안녕하세요.');
now=500;tick();assert.equal(c.P.chT,0); // Waiting for the device must not advance the chat.
queue[0].onstart();
now=2200;tick();assert.equal(c.sentAt(greeting,c.P.chT),0); // Length/time estimates cannot select the next sentence.
queue[1].onstart();assert.equal(painted.at(-1),1); // Native sentence start switches immediately.
const stale=queue[1];
c.pause();c.play();assert.equal(queue[0].text,'좋은 아침이에요!'); // Resume from the active sentence.
c.seekTo(0,c.sentStart(greeting,2)+0.01);assert.equal(queue[0].text,'소식을 전해요.'); // Seeking is independent of the previously active sentence.
const before=c.P.chT;stale.onstart();assert.equal(c.P.chT,before); // Cancelled utterance callbacks cannot change playback.
queue[0].onerror();assert.equal(c.mode(),'timer');
assert.equal(c.chatCues(greeting)[0].text,'안녕하세요.');
c.voiceKo=null;c.P.fallback=false;assert.equal(c.chatText(greeting),greeting.s);
greeting.audio='greeting.mp3';c.play(0);c.voiceKo={lang:'ko-KR'};assert.equal(c.mode(),'audio');assert.equal(c.chatText(greeting),greeting.s); // Legacy personal text never replaces recorded audio.
const recording={s:'아주 긴 첫 문장이에요. 짧아요.',audio:'news.mp3',est:12,cues:[
  {text:'아주 긴 첫 문장이에요.',start_sec:0,end_sec:2},
  {text:'짧아요.',start_sec:2,end_sec:12}]};
c.CH=[recording];c.P.ch=0;c.P.chT=0;
assert.equal(c.sentAt(recording,1.99),0);assert.equal(c.sentAt(recording,2),1);
audio.currentTime=2.01;audio.events.timeupdate();assert.equal(c.P.chT,2.01);assert.equal(painted.at(-1),1);
assert.equal(c.sentStart(recording,1),2);
recording.cues[1].text='다른 대본';assert.equal(c.chatCues(recording).length,1); // Reject stale cue text.
recording.cues=[];assert.equal(c.chatCues(recording).length,1); // Legacy MP3s do not invent sentence timestamps.
console.log('Briefing chat synchronization checks passed');
