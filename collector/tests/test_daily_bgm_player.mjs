// Run: node collector/tests/test_daily_bgm_player.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Audio {
  constructor() { this.paused = true; this.src = ''; this.attrs = {}; this.events = {}; this.pending = []; }
  getAttribute(key) { return this.attrs[key]; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
  play() { return new Promise(resolve => this.pending.push(() => { this.paused = false; resolve(); })); }
  pause() { this.paused = true; }
  async resolveNext() { this.pending.shift()(); await Promise.resolve(); }
}

const html = readFileSync(new URL('../../tools/knua-app.html', import.meta.url), 'utf8');
const engine = html.slice(html.indexOf('var A = new Audio();'), html.indexOf('function audioUrl('));
const c = vm.createContext({Audio, P: {playing: true}, S: {voice: true, bgm: true},
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

// A request completing after pause/waiting must never restart music alone.
c.startBgm();
c.A.events.waiting();
await c.B.resolveNext();
assert.equal(c.B.paused, true);
c.A.events.playing();
await c.B.resolveNext();
assert.equal(c.B.paused, false);
c.A.events.pause();
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
