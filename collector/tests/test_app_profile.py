import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def function_source(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if depth == 0:
                return source[start:end + 1]
    raise AssertionError(f'함수 블록을 찾지 못했습니다: {marker}')


def test_multiple_department_selection_and_legacy_profile_migration():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js가 없어 앱 선택 로직 검사를 건너뜁니다')
    html = (ROOT / 'tools/app-test.html').read_text(encoding='utf-8')
    helper_start = html.index('// 다른 학과 필수 공지와 식당을 선택으로 추가한다.')
    helper_end = html.index('const deptLabel=', helper_start)
    helpers = html[helper_start:helper_end]
    migration = function_source(html, 'function loadProfile(){')
    script = r"""
const assert = require('node:assert/strict');
let catalog, byId;
const KEY = 'knua-app-test';
const memory = new Map();
const localStorage = {getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value)};
""" + helpers + migration + r"""
catalog = {
  departments: [
    {id:'dept-a', name:'A', college:'College'},
    {id:'dept-b', name:'B', college:'College'},
    {id:'dept-c', name:'C', college:'College'},
    {id:'dept-current', name:'Current', college:'College'}
  ],
  channels: [
    {id:'knu-academic', type:'notice', classification:'required', required:'all', required_department_ids:[]},
    {id:'notice-a', type:'notice', classification:'required', required:['A'], required_department_ids:['dept-a']},
    {id:'notice-b', type:'notice', classification:'required', required:['B','C'], required_department_ids:['dept-b','dept-c']},
    {id:'notice-c', type:'notice', classification:'required', required:['C'], required_department_ids:['dept-c']},
    {id:'meal-1', type:'meal', classification:'optional', collection_enabled:true},
    {id:'deleted-job-board', type:'notice', classification:'optional', collection_enabled:true}
  ]
};
byId = Object.fromEntries(catalog.channels.map(channel => [channel.id, channel]));
assert.deepEqual(chosenIds({dept:'dept-a', optionalDepartments:['dept-b','dept-c'], optional:['meal-1','deleted-job-board']}),
  ['knu-academic','notice-a','notice-b','notice-c','meal-1']);
assert.deepEqual(chosenIds({dept:'dept-a', optionalDepartments:['dept-b'], optional:['meal-1']}),
  ['knu-academic','notice-a','notice-b','meal-1']);
assert.deepEqual(chosenIds({dept:'dept-a', optionalDepartments:[], optional:[]}),
  ['knu-academic','notice-a']);

memory.set(KEY, JSON.stringify({name:'legacy', dept:'dept-a', optional:['deleted-job-board','meal-1','unknown'], optionalDepartments:['dept-a','dept-b','gone']}));
const migrated = loadProfile();
assert.deepEqual(migrated.optional, ['meal-1']);
assert.deepEqual(migrated.optionalDepartments, ['dept-b']);
assert.deepEqual(JSON.parse(memory.get(KEY)), migrated);
memory.set(KEY, JSON.stringify({name:'old', dept:'dept-a', optional:['meal-1']}));
assert.deepEqual(loadProfile().optionalDepartments, []);
"""
    subprocess.run([node, '-e', script], cwd=ROOT, check=True, capture_output=True, text=True)
