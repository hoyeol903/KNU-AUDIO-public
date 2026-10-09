import test from 'node:test';
import assert from 'node:assert/strict';
import {selectPlaylist, requiredChannels} from '../web/player/playlist.mjs';
const segment = (id, kind, channels=[], dday=null) => ({id, kind, channel_ids:channels, dday, title:id});
const manifest = {
  departments:[{id:'computer',name:'컴퓨터학부'}, {id:'business',name:'경영학부'}],
  channels:[{id:'common', required:'all', department_ids:[]},{id:'cs',required:['컴퓨터학부'],department_ids:['computer']},
    {id:'biz',required:['경영학부'],department_ids:['business']}],
  segments:[segment('hello','greeting'), segment('weather','weather'), segment('common','notice',['common']),
    segment('cs','notice',['cs'],1),segment('biz','notice',['biz'],0),segment('shared','notice',['cs','biz'],3),
    segment('meal1','meal',['cafeteria']),segment('empty1','empty_notices'),segment('empty2','empty_meals'),
    segment('events','events'),segment('bye','outro')]
};
test('학과별 필수 채널, 다른 학과 제외', () => {
  assert.deepEqual(requiredChannels(manifest,'computer'), ['common','cs']);
  const ids=selectPlaylist(manifest,['common','cs','cafeteria']).map(s=>s.id);
  assert.deepEqual(ids,['hello','weather','cs','shared','common','meal1','events','bye']);
  assert(!ids.includes('biz'));
});
test('공유 공지 한 번, 개별 공지 제외',()=>{
  const ids=selectPlaylist(manifest,['cs','biz'],['biz']).map(s=>s.id);
  assert.equal(ids.filter(id=>id==='shared').length,1);
  assert(!ids.includes('biz'));
});
test('빈 선택은 공지 없음 안내 없이 공통 구간만 유지',()=>{
  assert.deepEqual(selectPlaylist(manifest,[]).map(s=>s.id), ['hello','weather','empty2','events','bye']);
});
test('500명 선택은 합성 요청 없이 독립적으로 계산',()=>{
  for(let i=0;i<500;i++) {
    const channel=i%2?'cs':'biz', other=i%2?'biz':'cs';
    const ids=selectPlaylist(manifest,['common',channel]).map(s=>s.id);
    assert(ids.includes(channel)); assert(!ids.includes(other));
  }
});
