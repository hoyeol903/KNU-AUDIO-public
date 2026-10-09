// Run: node collector/tests/test_saved_notices_player.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../../tools/knua-app.html',import.meta.url),'utf8');
const helpers=html.slice(html.indexOf('function savedPosts('),html.indexOf('/* 재생 목록:'));
const board={id:'academic',name:'학교 학사공지',url:'https://example.com/board',today:[]};
const post={id:'n1',title:'저장할 공지',date:'2026-10-07',deadline:'2026-10-14',url:'https://example.com/post',body:'보존할 본문 전체',bodyStatus:'ok'};
let persisted='',storageOK=true;
const c=vm.createContext({store:{},W:{boards:[board]},DATA:{boardMap:{academic:board}},POSTS:{academic:[post]},S:{sheet:null},Date,
  dday:()=>7,save(){if(!storageOK)return false;persisted=JSON.stringify(c.store);return true;},toastMsg(){}});
vm.runInContext(helpers,c);
c.toggleSavedPost('academic','n1');
assert.equal(c.savedPosts().length,1);assert.equal(c.savedPosts()[0].body,post.body);
c.store=JSON.parse(persisted);c.POSTS.academic=[];board.today=[{id:'n1',title:post.title,date:post.date,tag:'new'}];
assert.equal(c.findPost(c.postBoard('academic'),'n1').url,post.url); // Recent-feed expiration must not lose a saved notice.
c.W.boards=[];c.DATA.boardMap={};
assert.equal(c.findPost(c.postBoard('academic'),'n1').body,post.body); // It still opens after changing selected departments.
storageOK=false;c.toggleSavedPost('academic','n1');assert.equal(c.savedPosts().length,1); // Storage failure rolls back instead of silently removing data.
storageOK=true;c.toggleSavedPost('academic','n1');assert.equal(c.savedPosts().length,0);
c.W.boards=[board];c.DATA.boardMap={academic:board};c.POSTS.academic=[post];
c.toggleSavedPost('academic','n1');c.toggleSavedPost('academic','n1');c.toggleSavedPost('academic','n1');assert.equal(c.savedPosts().length,1);
c.toggleSavedPost('missing','absent');assert.equal(c.savedPosts().length,1);
console.log('Saved notice persistence checks passed');
