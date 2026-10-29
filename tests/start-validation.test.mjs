import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../tools/knua-app.html', import.meta.url), 'utf8');
function setup(name = '', dept = 'ai') {
  const listeners = {}, attrs = {}, calls = [];
  const elements = {
    inName: {setAttribute(k,v){attrs[k]=v;}, scrollIntoView(){calls.push('scroll');}, focus(){calls.push('focus');}},
    nameError: {hidden:true}, nameCount: {}, deptList: {}
  };
  const button = {disabled:dept == null};
  const c = vm.createContext({S:{startName:name,startDept:dept,startNameError:false,startQuery:''},store:{},DATA:{deptMap:{}},
    document:{addEventListener(k,fn){listeners[k]=fn;},querySelector(){return button;}},
    $:id=>elements[id],save(){calls.push('save');},nav(route){calls.push(route);},deptList:()=>'',esc:s=>s,IC:{search:''},collegeOptions:()=>''});
  vm.runInContext(html.slice(html.indexOf('function vStart(){'),html.indexOf('/* 휴대폰에서 자판이 올라와도')),c);
  vm.runInContext(html.slice(html.indexOf("document.addEventListener('click', function(e){"),html.indexOf("document.addEventListener('toggle',")),c);
  return {c,calls,elements,attrs,button,next(){listeners.click({target:{closest:()=>({getAttribute:()=> 'startNext'})}});},input(value){listeners.input({target:{id:'inName',value}});}};
}
test('빈 이름·공백 이름은 저장과 화면 이동을 막고 오류 표시 후 이름 칸으로 이동한다',()=>{
  for (const name of ['', '   ', '\t\u3000']) {
    const s=setup(name);s.next();
    assert.deepEqual(s.calls,['scroll','focus']);
    assert.equal(s.c.store.name,undefined);
    assert.equal(s.attrs['aria-invalid'],'true');
    assert.equal(s.elements.nameError.hidden,false);
    assert.match(s.c.vStart(),/이름을 입력하세요<\/p>/);
    assert.doesNotMatch(s.c.vStart(),/data-act="startNext" disabled/);
  }
});
test('학과 선택 후 이름이 없어도 다음을 눌러 오류를 확인할 수 있다',()=>{
  const s=setup('',null);
  s.c.S.startDept='ai';
  // 학과 선택 이벤트의 실제 분기를 실행한다.
  const click=html.slice(html.indexOf("case 'dept': {"),html.indexOf("case 'startNext': {"));
  vm.runInContext("(function(){var el={getAttribute:()=> 'ai'};"+click.replace("case 'dept': ",'')+'})()',s.c);
  assert.equal(s.button.disabled,false);
});
test('공백만 입력하면 오류를 유지하고 이름을 입력하면 즉시 해제한다',()=>{
  const s=setup();s.next();s.input('  ');
  assert.equal(s.elements.nameError.hidden,false);
  s.input(' 경민 ');
  assert.equal(s.elements.nameError.hidden,true);
  assert.equal(s.attrs['aria-invalid'],'false');
  s.calls.length=0;s.next();
  assert.equal(s.c.store.name,'경민');
  assert.equal(s.c.store.dept,'ai');
  assert.deepEqual(s.calls,['save','pick']);
});
test('학과 미선택은 계속 막고 렌더링 후에도 이름 오류를 유지한다',()=>{
  const s=setup('경민',null);s.next();assert.deepEqual(s.calls,[]);
  assert.match(s.c.vStart(),/data-act="startNext" disabled/);
  s.c.S.startName='';s.next();
  assert.match(s.c.vStart(),/aria-invalid="true"/);
  assert.doesNotMatch(s.c.vStart(),/role="alert" hidden/);
});
