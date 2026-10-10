import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../tools/knua-app.html', import.meta.url), 'utf8');
const fn = name => { const from = html.indexOf('function ' + name + '('); return html.slice(from, html.indexOf('\n}', from) + 2); };
const seg = (id, title, script, extra = {}) => ({id, channel_id: id, title, script, duration_sec: 10, items: [], ...extra});
function chapters(segments, boards) {
  const c = vm.createContext({BRIEF: {date: '2026-10-10', segments}, BRIEF_OLD: false, dd: n => 'D-' + n});
  vm.runInContext('var WD = ["일","월","화","수","목","금","토"];' + fn('fmtKo') + fn('wday') + fn('chapters'), c);
  return c.chapters({boards, cafes: []});
}
const tail = [seg('empty', '공지 안내', '공지가 없어요.'), seg('message', '크누아의 응원', '밥 챙겨요.'), seg('outro', '마무리', '좋은 하루!')];
const notice = seg('n1', '장학 안내', '장학금 신청.', {kind: 'notice', channel_ids: ['cs'], items: [{section: '소식', title: '장학 안내', channel_id: 'cs'}]});

test('응원·마무리 구간은 대본으로 카드 한 장을 만든다', () => {
  const list = chapters([notice, ...tail], [{id: 'cs', today: [{id: 1}]}]);
  assert.deepEqual(Array.from(list, c => c.id), ['n1', 'message', 'outro']);
  const [, cheer, end] = Array.from(list, c => c.cards);
  assert.deepEqual([cheer.length, cheer[0].kind, cheer[0].t, cheer[0].quote], [1, '크누아의 응원', '밥 챙겨요.', true]);
  assert.equal(end[0].d, '10월 10일 토요일 · 소식 1건');
  assert.equal(end[0].again, true);
});

test('들을 소식이 없으면 공지 없음 카드가 나오고 마무리에 소식 수를 적지 않는다', () => {
  const list = chapters([notice, ...tail], [{id: 'biz', today: []}]);
  assert.deepEqual(Array.from(list, c => c.id), ['empty', 'message', 'outro']);
  assert.equal(list[0].cards[0].d, '내 게시판 기준');
  assert.equal(list[2].cards[0].d, '10월 10일 토요일');
});

test('카드 종류마다 바탕색이 있고 밝은·어두운 화면 값이 모두 있다', () => {
  for (const [kind, cls] of [['크누아의 응원', 'sp-cheer'], ['마무리', 'sp-end'], ['공지 안내', 'sp-calm']]) {
    assert.ok(html.includes(`'${kind}': '${cls}'`), kind);
    assert.equal(html.split(`--${cls}:`).length - 1, 3, cls);
  }
});
