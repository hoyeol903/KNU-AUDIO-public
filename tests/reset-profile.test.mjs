import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../tools/knua-app.html',import.meta.url),'utf8');
const handler=html.slice(html.indexOf("    case 'reset':"),html.indexOf("    case 'jump':"));
function run(accept,fail=false){
 const calls=[];
 const context={KEY:'knua-app-v1',window:{confirm:()=>accept,location:{reload:()=>calls.push('reload')}},
 localStorage:{removeItem(key){if(fail)throw Error('blocked');calls.push(key);}},pause:()=>calls.push('pause'),toastMsg:()=>calls.push('error')};
 vm.runInNewContext("(function(){switch('reset'){"+handler+"}})()",context);
 return calls;
}
test('초기화 취소는 저장 정보와 재생 상태를 유지한다',()=>assert.deepEqual(run(false),[]));
test('프로필만 삭제하고 재생을 멈춘 뒤 처음 화면을 다시 연다',()=>assert.deepEqual(run(true),['knua-app-v1','pause','reload']));
test('저장 정보 삭제 실패를 알리고 재시작하지 않는다',()=>assert.deepEqual(run(true,true),['error']));
