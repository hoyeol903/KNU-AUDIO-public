import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../tools/knua-app.html', import.meta.url), 'utf8');
const code = html.slice(html.indexOf('function centerStartField(el)'), html.indexOf('/* 4-2 게시판 고르기 */'));
function setup({coarse = true, keyboard = 300} = {}) {
  const listeners = {}, vvListeners = {};
  const scr = {scrollTop: 0, style: {}};
  const field = id => ({id, closest: () => scr, getBoundingClientRect: () => ({top: 520 - scr.scrollTop, height: 52})});
  const c = vm.createContext({
    window: {innerHeight: 800, matchMedia: () => ({matches: coarse}), visualViewport: {offsetTop: 0, height: 800, addEventListener: (type, fn) => { vvListeners[type] = fn; }}},
    document: {activeElement: null, addEventListener: (type, fn) => { listeners[type] = fn; }}, setTimeout() {}, Math});
  vm.runInContext(code, c);
  return {c, scr, field, focus(el) { c.document.activeElement = el; listeners.focusin({target: el}); },
          openKeyboard() { c.window.visualViewport.height = 800 - keyboard; vvListeners.resize(); }};
}
const center = (s, el, visible) => el.getBoundingClientRect().top + 26 - visible / 2;

test('자판이 올라오면 이름·학과 칸이 보이는 영역 가운데로 온다', () => {
  for (const id of ['inName', 'inDept']) {
    const s = setup(), el = s.field(id);
    s.focus(el);
    assert.equal(center(s, el, 800), 0); // 자판이 뜨기 전에도 화면 가운데
    s.openKeyboard();
    assert.equal(center(s, el, 500), 0); // 자판에 가려지지 않는 500px의 가운데
    assert.equal(s.scr.style.paddingBottom, '440px'); // 가려진 300px만큼 더 내릴 수 있게 여백을 늘린다
  }
});

test('마우스를 쓰는 화면과 다른 입력칸은 움직이지 않는다', () => {
  let s = setup({coarse: false}), el = s.field('inName');
  s.focus(el); s.openKeyboard();
  assert.equal(s.scr.scrollTop, 0);
  s = setup(); el = s.field('meetTitle');
  s.focus(el); s.openKeyboard();
  assert.equal(s.scr.scrollTop, 0);
});
