// node collector/tests/test_notice_dedup_player.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../../tools/knua-app.html',import.meta.url),'utf8');
new vm.Script(html.slice(html.indexOf('<script>')+8,html.lastIndexOf('</script>')));
const shared={id:'shared',channel_id:'shared',kind:'notice',channel_ids:['a','b'],script:'한 번 듣기',audio:'shared.mp3',duration_sec:2,items:[
 {channel_id:'a',postId:'a:1',title:'A',url:'https://a'}, {channel_id:'b',postId:'b:2',title:'B',url:'https://b'}]};
const c=vm.createContext({BRIEF:{segments:[{id:'intro',script:'인사'},shared,{id:'outro',script:'끝'}]},store:{},dd:x=>x});
vm.runInContext(html.slice(html.indexOf('function chapters('),html.indexOf('var W = null, CH = [];')),c);
const board=id=>({id,today:[{id:id+':'+(id==='a'?1:2),dday:null}]});
for(const ids of [['a'],['b'],['a','b'],['b','a']]){
 const rows=c.chapters({boards:ids.map(board),cafes:[]});
 assert.equal(rows.filter(r=>r.audio==='shared.mp3').length,1);
 const cards=rows.find(r=>r.id==='shared').cards;
 assert.equal(cards.length,ids.length);
 assert.deepEqual(Array.from(cards,k=>k.post.board.id).sort(),[...ids].sort());
}
c.BRIEF={segments:[{id:'intro',script:'인사'},{id:'a',script:'옛 자료',audio:'old.mp3'},{id:'outro',script:'끝'}]};
assert.equal(c.chapters({boards:[board('a')],cafes:[]})[1].audio,'old.mp3');
console.log('Shared notice playback checks passed');
