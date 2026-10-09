// Run: node collector/tests/test_daily_bgm_player.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Audio {
  constructor() { this.paused = true; this.src = ''; this.attrs = {}; this.events = {}; this.pending = []; }
  getAttribute(key) { return this.attrs[key]; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(name, callback) { const previous = this.events[name]; this.events[name] = (...args) => { if (previous) previous(...args); callback(...args); }; }
  play() { return new Promise(resolve => this.pending.push(() => { this.paused = false; resolve(); })); }
  pause() { this.paused = true; }
  async resolveNext() { this.pending.shift()(); await Promise.resolve(); }
}

const html = readFileSync(new URL('../../tools/knua-app.html', import.meta.url), 'utf8');
const engine = html.slice(html.indexOf('var A = new Audio();'), html.indexOf('function audioUrl('));
const timers = [];
const c = vm.createContext({window:{addEventListener(){}},location:{hostname:'127.0.0.1',protocol:'http:'},Audio, setTimeout: fn => timers.push(fn), media: () => {}, render: () => {}, P: {playing: true, playToken: 1}, S: {voice: true, bgm: true},
  BGM_TRACK: {audio: 'a'.repeat(64) + '.mp3', volume: 0.1}, mode: () => 'audio'});
vm.runInContext(engine, c);
assert.equal(c.B.loop, true);
c.A.paused = false;
c.syncBgm();
await c.B.resolveNext();
assert.equal(c.B.paused, false);
const src = c.B.src;

// A late earlier request must not pause a newer, valid playback request.
c.startBgm(); c.startBgm();
await c.B.resolveNext();
assert.equal(c.B.paused, false);
await c.B.resolveNext();
assert.equal(c.B.src, src);

// Music keeps going while speech changes segments: the voice briefly pauses/ends and buffers the next file.
c.startBgm();
c.A.events.waiting?.(); // 처리기가 없거나 있어도 음악을 멈추면 안 된다
await c.B.resolveNext();
assert.equal(c.B.paused, false);
c.A.events.pause();
assert.equal(c.B.paused, false);
// A segment change (newer play request) within the check window keeps both speech and music going.
c.A.paused = true;
c.P.playToken++;
timers.shift()();
assert.equal(c.P.playing, true);
assert.equal(c.B.paused, false);
// A real device pause (same request still current) pauses the UI and stops music.
c.A.events.pause();
timers.shift()();
assert.equal(c.P.playing, false);
assert.equal(c.B.paused, true);
c.P.playing = true; c.A.paused = false;
// A request completing after an explicit stop (user pause) must never restart music alone.
c.startBgm();
c.stopBgm();
await c.B.resolveNext();
assert.equal(c.B.paused, true);

c.S.voice = false;
c.startBgm();
assert.equal(c.B.paused, true);
c.S.voice = true; c.S.bgm = false;
c.startBgm();
assert.equal(c.B.paused, true);
c.S.bgm = true; c.BGM_TRACK = null;
c.startBgm();
assert.equal(c.B.paused, true);
assert.equal(c.A.paused, false); // Missing music never stops speech.
console.log('Daily BGM playback checks passed');
