import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../tools/knua-app.html', import.meta.url), 'utf8');
const code = html.slice(html.indexOf('function centerStartField(el)'), html.indexOf('/* 4-2 게시판 고르기 */'));
function setup({coarse = true, keyboard = 300} = {}) {
  const listeners = {}, vvListeners = {}, timers = [];
  const scr = {scrollTop: 0, style: {}};
  const field = id => ({id, closest: () => scr, getBoundingClientRect: () => ({top: 520 - scr.scrollTop, height: 52})});
  const c = vm.createContext({
    window: {innerHeight: 800, matchMedia: () => ({matches: coarse}), visualViewport: {offsetTop: 0, height: 800, addEventListener: (type, fn) => { vvListeners[type] = fn; }}},
    document: {activeElement: null, addEventListener: (type, fn) => { listeners[type] = fn; }}, setTimeout(fn) { timers.push(fn); }, Math, parseFloat});
  vm.runInContext(code, c);
  return {c, scr, field, focus(el) { c.document.activeElement = el; listeners.focusin({target: el}); },
          blur(el, next = null) { c.document.activeElement = next; listeners.focusout({target: el}); timers.splice(0).forEach(fn => fn()); },
          openKeyboard() { c.window.visualViewport.height = 800 - keyboard; vvListeners.resize(); }};
}
const fromTop = el => el.getBoundingClientRect().top;

test('이름·학과 칸을 누르면 보이는 영역 위에서 90px 아래로 온다', () => {
  for (const id of ['inName', 'inDept']) {
    const s = setup(), el = s.field(id);
    s.focus(el);
    assert.equal(fromTop(el), 90); // 라벨이 보이도록 위에 여백을 둔다
    assert.equal(s.scr.style.paddingBottom, '540px'); // 자판이 뜨기 전에 화면 절반만큼 미리 여백을 둔다
    const before = s.scr.scrollTop;
    s.openKeyboard();
    assert.equal(s.scr.scrollTop, before); // 자판이 올라와도 다시 움직이지 않는다
    assert.equal(s.scr.style.paddingBottom, '540px'); // 입력 중에는 여백을 줄이지 않는다
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

test('입력을 마치면 여백을 되돌리고, 이름에서 학과로 넘어갈 때는 유지한다', () => {
  const s = setup(), name = s.field('inName'), dept = s.field('inDept');
  s.focus(name); s.blur(name, dept);
  assert.equal(s.scr.style.paddingBottom, '540px');
  s.focus(dept); s.blur(dept);
  assert.equal(s.scr.style.paddingBottom, '140px');
});

test('자판이 화면 절반보다 많이 가리면 그만큼 여백을 더 늘린다', () => {
  const s = setup({keyboard: 480}), el = s.field('inName');
  s.focus(el); s.openKeyboard();
  assert.equal(s.scr.style.paddingBottom, '620px');
  assert.equal(el.getBoundingClientRect().top, 90);
});

