import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../tools/knua-app.html', import.meta.url), 'utf8');
const cut = (from, to) => html.slice(html.indexOf(from), html.indexOf(to));
class Audio {
  constructor() { this.paused = true; this.volume = 1; this.attrs = {}; this.events = {}; }
  getAttribute(k) { return this.attrs[k]; } setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(name, fn) { (this.events[name] ||= []).push(fn); }
  fire(name) { (this.events[name] || []).forEach(fn => fn()); }
  play() { this.paused = false; } pause() { this.paused = true; }
}
function load(music = true) {
  const c = vm.createContext({window: {addEventListener() {}}, location: {hostname: '127.0.0.1', protocol: 'http:'}, Audio, setTimeout() {}, now: 0,
    media() {}, render() {}, stopVoice() {}, startChapter() {}, toasts: [], mode: () => 'audio',
    P: {playing: true, started: true, done: false, ch: 0, chT: 0, playToken: 1}, S: {voice: true, bgm: music}, CH: [{est: 5}],
    BGM_TRACK: {audio: 'a'.repeat(64) + '.mp3', volume: 0.1}});
  c.performance = {now: () => c.now}; c.toastMsg = m => c.toasts.push(m);
  vm.runInContext(cut('function tailLen()', '/* ---------- 재생 엔진') + cut('var A = new Audio();', 'function audioUrl(') + cut('function play(ch, restart)', '/* 원하는 곳부터 듣기') + cut('function nextAuto()', 'function media()'), c);
  c.A.paused = false; c.startBgm(true);
  return c;
}
const at = (c, sec) => { c.now = sec * 1000; c.B.fire('timeupdate'); };

test('대본이 끝나면 음악만 8초 더 들리고, 커졌다가 서서히 줄어 끝난다', () => {
  const c = load(); c.nextAuto();
  assert.deepEqual([c.P.playing, c.P.done, c.B.paused, c.P.chT], [true, false, false, 5]);
  at(c, 0.5); assert.ok(Math.abs(c.B.volume - 0.2) < 1e-9);
  at(c, 4); assert.equal(c.B.volume, 0.3);
  c.nextAuto(); assert.equal(c.P.done, false); // 여운 중 다시 불려도 그대로
  at(c, 7); assert.ok(Math.abs(c.B.volume - 0.15) < 1e-9);
  at(c, 8);
  assert.deepEqual([c.P.playing, c.P.done, c.B.paused, c.toasts.length], [false, true, true, 1]);
});

test('음악을 꺼 두면 바로 끝난다', () => {
  const c = load(false); c.nextAuto();
  assert.deepEqual([c.P.playing, c.P.done, c.toasts.length], [false, true, 1]);
});

test('여운 중 일시정지는 끝으로 처리하고, 다시 듣기는 여운을 취소한다', () => {
  let c = load(); c.nextAuto(); c.pause();
  assert.deepEqual([c.P.done, c.B.paused, c.toasts.length], [true, true, 1]);
  c = load(); c.nextAuto(); c.play(0);
  at(c, 9);
  assert.deepEqual([c.P.playing, c.P.done, c.toasts.length], [true, false, 0]);
});

test('전체 길이와 지나간 시간에 여운 8초가 들어간다', () => {
  const c = load(); c.P.chT = 5;
  assert.deepEqual([c.total(), c.elapsed()], [13, 5]);
  c.nextAuto(); at(c, 3); assert.equal(c.elapsed(), 8);
  at(c, 8); assert.deepEqual([c.P.done, c.elapsed()], [true, 13]);
  const quiet = load(false); quiet.P.chT = 5; quiet.nextAuto();
  assert.deepEqual([quiet.total(), quiet.elapsed()], [5, 5]); // 음악을 끄면 여운이 없다
});
