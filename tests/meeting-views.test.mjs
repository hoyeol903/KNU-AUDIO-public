import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../tools/knua-app.html', import.meta.url), 'utf8');
const cut = (from, to) => html.slice(html.indexOf(from), html.indexOf(to));
function load() {
  const c = vm.createContext({
    window: {}, location: {hostname: 'localhost'}, document: {addEventListener() {}, querySelectorAll: () => [], hidden: false, activeElement: null},
    localStorage: {getItem: () => null, setItem() {}}, setInterval() {}, setTimeout() {}, crypto: {randomUUID: () => 'id'}, URL, console, fetch: () => Promise.reject(new Error('offline')),
    W: {hasBrief: false, pf: {name: '테스트', dept: {dept: '컴퓨터학부', college: 'IT대학'}}}, P: {started: false}, SPLASH: {active: false},
    S: {route: 'meeting', meetCategory: 'study', meetSize: '전체', meetTeam: '전체'}, store: {}, render() {}, nav() {}, toastMsg() {}, save() {}, $: () => null});
  const ic = html.indexOf('var IC = {'), esc = html.indexOf('function esc(s)');
  vm.runInContext(html.slice(ic, html.indexOf('\n', esc)), c);
  vm.runInContext(html.slice(html.indexOf('var MEET_CATEGORIES'), html.indexOf('function saveSharedMeeting()')), c);
  return c;
}
const acts = text => new Set([...text.matchAll(/data-act="(\w+)"/g)].map(m => m[1]));
const post = (extra = {}) => ({id: 'p1', shared: true, category: 'study', title: '토익 아침 스터디', capacity: 6, dept: '컴퓨터학부', college: 'IT대학', when: '화·목 9시', where: '중앙도서관', goal: '800점', intro: '같이 공부해요', applicationCount: 2, contact: 'https://open.kakao.com/o/abc', ...extra});

test('허브: 이름은 모임, 알림 카드와 세 카테고리, 배지용 inbox-btn 뒤에 셰브론', () => {
  const c = load(); c.NOTE.items = [{}, {}];
  const h = c.vMeet();
  assert.match(h, /<h1 class="cm-h1">모임<\/h1>/);
  assert.match(h, /새 알림 2개가 도착했어요/);
  assert.match(h, /class="inbox-btn" data-act="meetInbox">확인하기<span class="tb-badge"[^>]*>2<\/span><svg/);
  assert.deepEqual([...h.matchAll(/data-act="meetCategory" data-k="(\w+)"/g)].map(m => m[1]), ['study', 'dating', 'club']);
  assert.match(h, /최근 · \[예시\] /); // 실제 글이 없으면 예시 제목
  assert.ok(acts(h).has('meetRefresh'));
});

test('목록: 세그먼트·필터·내 모집글·새로고침·모집글 만들기와 접는 구역 id 유지', () => {
  const c = load(); c.S.route = 'meeting-list'; c.S.meetCategory = 'dating'; c.COMMUNITY.status = 'ready';
  c.COMMUNITY.rows = [post({category: 'dating', team: 'm', size: '3:3', mine: true})]; c.COMMUNITY.cursor = 'next';
  const h = c.vMeetList();
  for (const act of ['back', 'meetCategory', 'meetMineOnly', 'meetRefresh', 'meetSize', 'meetTeam', 'meetDetails', 'meetMore', 'meetNew']) assert.ok(acts(h).has(act), act);
  assert.match(h, /id="meetExamples" data-k="dating"/);
  assert.match(h, /내 모집글<\/span><\/span><b class="cm-t">토익 아침 스터디/);
  assert.match(h, /신청 2팀/);
  assert.ok(h.indexOf('cm-fab') > h.lastIndexOf('</div>'), '모집글 만들기 버튼은 스크롤 영역 밖에 둔다');
  c.S.meetCategory = 'study';
  assert.ok(!acts(c.vMeetList()).has('meetSize'), '인원·팀 필터는 과팅에만 나온다');
});

test('상세(작성자): 수정·마감·삭제, 신청 내역 펼치기와 수락·거절', () => {
  const c = load(); c.S.route = 'meeting-detail'; c.COMMUNITY.detail = post({mine: true});
  let h = c.vMeetDetail();
  for (const act of ['back', 'meetEdit', 'meetToggleClosed', 'meetDeleteShared', 'meetApplicants']) assert.ok(acts(h).has(act), act);
  assert.match(h, /cm-pill on/);
  c.COMMUNITY.applicants = [{ref: 'r1', name: '민지', status: 'pending', message: '4명이에요', contact: 'https://www.instagram.com/minji'}, {ref: 'r2', name: '서준', status: 'accepted', reason: '환영해요'}];
  h = c.vMeetDetail();
  assert.deepEqual([...h.matchAll(/data-act="decideOpen" data-ref="(\w+)" data-s="(\w+)"/g)].map(m => m[1] + ':' + m[2]), ['r1:rejected', 'r1:accepted', 'r2:rejected']);
  assert.match(h, /신청자에게 연락 · 인스타그램/);
  assert.ok(!acts(h).has('meetApplicants'));
});

test('상세(신청자·예시): 하단 고정 버튼과 내 신청 카드, 예시는 신청 불가 안내', () => {
  const c = load(); c.S.route = 'meeting-detail'; c.COMMUNITY.detail = post();
  let h = c.vMeetDetail();
  assert.match(h, /class="cm-bar"[\s\S]*참가 문의 · 오픈카톡[\s\S]*data-act="meetApply" data-id="p1">참가 신청하기/);
  assert.ok(!acts(h).has('meetCancel'));
  c.COMMUNITY.detail = post({myApplication: {status: 'rejected', reason: '정원 초과'}});
  h = c.vMeetDetail();
  assert.match(h, /내 신청<\/b><span class="badge b-due">거절됨/);
  assert.match(h, /다시 신청하기/); assert.ok(acts(h).has('meetCancel'));
  c.COMMUNITY.detail = post({closed: true, myApplication: {status: 'accepted'}});
  h = c.vMeetDetail();
  assert.ok(!acts(h).has('meetApply')); assert.match(h, /모집 마감/);
  c.COMMUNITY.detail = c.MEET_SAMPLES[0];
  h = c.vMeetDetail();
  assert.match(h, /아직 등록된 링크가 없어요/); assert.match(h, /참가·신청할 수 없어요/); assert.ok(!/cm-bar/.test(h));
});

test('작성·신청 시트: 입력 id와 글자 수 자리, 선택 항목 접기, 저장 버튼', () => {
  const c = load();
  c.S.meetSheet = {mode: 'new', category: 'dating', team: null, size: '3:3', title: '', intro: '', when: '', where: '', want: '', requirements: '', cost: '', contact: ''};
  let h = c.vMeetSheet();
  for (const id of ['meetTitle', 'meetTitleN', 'meetWant', 'meetIntro', 'meetIntroN', 'meetWhen', 'meetWhere', 'meetRequirements', 'meetCost', 'meetContact', 'meetContactHint', 'meetFormError', 'meetHint', 'meetSave']) assert.match(h, new RegExp('id="' + id + '"'), id);
  for (const act of ['meetClose', 'meetTm', 'meetSz', 'meetSave']) assert.ok(acts(h).has(act), act);
  assert.match(h, /<details class="cm-fold opt" id="meetOptional">/); // 새 글은 접힌 상태
  assert.match(h, /id="meetSave" data-act="meetSave"/); assert.match(h, /cm-save off/);
  assert.ok(h.indexOf('class="cm-foot"') > h.indexOf('id="meetFormError"'), '저장 버튼은 스크롤 영역 밖');
  c.S.meetSheet = {...c.S.meetSheet, contact: 'kakao.me/x'};
  assert.match(c.vMeetSheet(), /id="meetOptional" open/); // 링크 오류가 있으면 펼친다
  c.S.meetSheet = {mode: 'new', category: 'study', title: '', capacity: '', goal: '', intro: '', when: ''};
  h = c.vMeetSheet();
  assert.match(h, /id="meetCapacity"/); assert.match(h, /id="meetGoal"/);
  c.COMMUNITY.rows = [post()];
  c.S.meetSheet = {mode: 'apply', id: 'p1', category: 'study', name: '지훈', msg: '', contact: '', team: null};
  h = c.vMeetSheet();
  assert.match(h, /class="cm-over">토익 아침 스터디/); assert.match(h, /id="meetName"/); assert.match(h, /id="meetMsg"/); assert.match(h, /신청 보내기/);
});

test('알림·내 신청과 수락·거절 시트', () => {
  const c = load();
  c.COMMUNITY.inbox = {status: 'ready', notes: [{kind: 'applied', postId: 'p1', at: Date.now(), name: '민지', title: '볼링 과팅'}], apps: [{postId: 'p2', status: 'rejected', category: 'study', title: '토익', reason: '정원 초과', createdAt: Date.now()}]};
  let h = c.vMeetInbox();
  assert.match(h, /data-act="meetDetails" data-id="p1" data-open="applicants"><i class="dot">/);
  assert.match(h, /거절 사유: 정원 초과/); assert.match(h, /알림은 크누아를 열어 두었을 때 확인돼요/);
  c.COMMUNITY.inbox = {status: 'error', error: '연결 실패', notes: [], apps: []};
  assert.match(c.vMeetInbox(), /연결 실패[\s\S]*data-act="meetInbox">다시 불러오기/);
  c.COMMUNITY.detail = post({mine: true}); c.COMMUNITY.applicants = [{ref: 'r1', name: '민지', message: '수요일 저녁 좋아요'}];
  c.S.decide = {ref: 'r1', name: '민지', status: 'accepted', reason: ''};
  h = c.vDecideSheet();
  assert.match(h, /수요일 저녁 좋아요/); assert.match(h, /id="decideReason"/); assert.match(h, /id="decideReasonN" class="num">0\/300/);
  assert.match(h, /id="decideSave" data-act="decideSave">수락하기/);
  assert.deepEqual([...h.matchAll(/data-act="decideStatus" data-s="(\w+)" aria-pressed="(\w+)"/g)].map(m => m[1] + m[2]), ['acceptedtrue', 'rejectedfalse']);
});
