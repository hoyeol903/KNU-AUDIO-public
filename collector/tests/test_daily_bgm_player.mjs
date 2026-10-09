import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Audio {
  static count = 0;
  constructor(){Audio.count++; this.attrs={};this.events={};this.currentTime=12;this.readyState=2;this.seekable={length:1,end(){return 60;}};this.duration=60;this.paused=true;}
  getAttribute(k){return this.attrs[k];} setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,v){this.events[k]=v;} pause(){this.paused=true;}
  load(){this.readyState=0;this.currentTime=0;}
  play(){this.paused=false;return Promise.resolve();}
}
const html=readFileSync(new URL('../../tools/knua-app.html',import.meta.url),'utf8');
const engine=html.slice(html.indexOf('var A = new Audio();'),html.indexOf('var voiceKo ='));
const start=html.slice(html.indexOf('function startChapter(resume)'),html.indexOf('function play(ch, restart)'));
const seek=html.slice(html.indexOf('function applyPend()'),html.indexOf('function audioProgress()'));
const timers=[];let skipped=0;
const c=vm.createContext({Audio,setTimeout:f=>timers.push(f),isFinite,
  CH:[{audio:'voice.mp3',audio_bgm:'mix.mp3',s:'안내합니다.'}],P:{ch:0,chT:12,playing:true,playToken:1},
  S:{voice:true,bgm:true,speed:1.25},window:{},media(){},render(){},stopVoice(){},toastMsg(){},nextAuto(){skipped++;}});
vm.runInContext(engine+start+seek,c);
c.startChapter(true);
assert.equal(Audio.count,1);assert.equal(c.A.src,'data/briefing/mix.mp3');assert.equal(c.A.playbackRate,1.25);
c.A.currentTime=12;c.S.bgm=false;c.syncBgm();assert.equal(c.P.pend,12);c.A.readyState=2;c.A.events.loadeddata();assert.equal(c.A.src,'data/briefing/voice.mp3');assert.equal(c.A.currentTime,12);assert.equal(c.P.playing,true);
c.P.playing=false;c.A.pause();c.S.bgm=true;c.syncBgm();assert.equal(c.A.paused,true);c.A.readyState=2;c.A.events.loadeddata();assert.equal(c.A.currentTime,12);
c.P.playing=true;c.A.events.error();assert.equal(c.CH[0].bgmFailed,true);assert.equal(c.A.src,'data/briefing/voice.mp3');assert.equal(skipped,0);
c.A.events.error();assert.equal(skipped,1);
c.S.voice=false;c.startChapter(true);assert.equal(c.A.muted,true);assert.equal(Audio.count,1);
c.P.pend=null;c.A.pause();c.A.events.pause();timers.shift()();assert.equal(c.P.playing,false);
console.log('Mixed BGM source switching, seek, mute, fallback and device pause passed');
