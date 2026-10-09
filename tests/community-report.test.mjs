import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../tools/knua-app.html',import.meta.url),'utf8');
test('신고 입력창은 사유를 안전하게 표시하고 접수 중 중복 전송을 막는다',()=>{
 const context={S:{report:{reason:'</textarea><script>bad</script>'}},COMMUNITY:{busy:false},IC:{x:''},esc:s=>s.replaceAll('<','&lt;').replaceAll('>','&gt;')};
 vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function vReportSheet(){'),source.indexOf('function vDecideSheet(){')),context);
 let html=context.vReportSheet();assert(html.includes('maxlength="300"'));assert(html.includes('&lt;script&gt;'));assert(!html.includes('<script>bad'));
 context.COMMUNITY.busy=true;html=context.vReportSheet();assert(html.includes(' disabled'));assert(html.includes('접수 중'));
 assert(!source.slice(source.indexOf("case 'meetReport':"),source.indexOf("case 'meetDeleteShared':")).includes('prompt('));
});
