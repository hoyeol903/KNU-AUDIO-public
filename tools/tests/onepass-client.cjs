const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../briefing-onepass.js'), 'utf8');
assert.equal(source, fs.readFileSync(path.join(__dirname, '../../output/app/briefing-onepass.js'), 'utf8'));
const appHtml = fs.readFileSync(path.join(__dirname, '../knua-app.html'), 'utf8');
assert.equal(appHtml, fs.readFileSync(path.join(__dirname, '../../output/app/index.html'), 'utf8'));
assert.match(fs.readFileSync(path.join(__dirname, '../../collector/export_app.py'), 'utf8'), /'briefing-onepass\.js', 'tools\/briefing-onepass\.js'/);
const appScript = appHtml.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(appScript);
assert.match(appHtml, /segmentIds:\s*CH\.map\(function\(c\)\{ return c\.id; \}\)/);
assert.match(appHtml, /O\.playbackRate\s*=\s*S\.speed/);
assert.match(appHtml, /C 목소리 연속 재생 준비 중/);
assert.match(appHtml, /구간별로 듣기/);
assert.match(appHtml, /oldSignature !== newSignature\) invalidateOnepass/);
assert.match(appHtml, /BRIEFING_SERVICE = window\.KnuOnePass && window\.KnuOnePass\.validConfig\(service\)/);
assert.match(appHtml, /O\.playbackRate = S\.speed/);
assert.match(appHtml, /O\.muted = !S\.voice/);
assert.doesNotMatch(appHtml, /140자 한도|omittedIds/);
const context = { URL, Promise, Set, encodeURIComponent, Date, Math, Error, Object, Array,
  setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout };
vm.createContext(context);
vm.runInContext(source, context);

const config = { enabled: true, api_base: 'https://audio.example.test', site_key: '0x1234567890' };
assert.equal(context.KnuOnePass.validConfig(config), true);
assert.equal(context.KnuOnePass.validConfig({ ...config, api_base: 'http://audio.example.test' }), false);
assert.equal(context.KnuOnePass.validConfig({ ...config, api_base: 'https://user:pass' + '@audio.example.test' }), false);

async function rejects(promise, code) {
  await assert.rejects(promise, error => error.message === code);
}

(async function main() {
  let tokenCalls = 0;
  await rejects(context.KnuOnePass.create({ config, date: '2026-10-09', segmentIds: ['a', 'a'],
    tokenProvider() { tokenCalls++; return Promise.resolve('token'); } }), 'selection_invalid');
  assert.equal(tokenCalls, 0, 'invalid selection must fail before requesting a challenge');

  const requests = [], statuses = [];
  const jobId = 'a'.repeat(43);
  const sequence = [
    { ok: true, json: async () => ({ job_id: jobId, status: 'queued' }) },
    { ok: true, json: async () => ({ job_id: jobId, status: 'running' }) },
    { ok: true, json: async () => ({ job_id: jobId, status: 'complete', duration_sec: 37.5,
      }) }
  ];
  const result = await context.KnuOnePass.create({
    config, date: '2026-10-09', segmentIds: ['greeting', 'intro', 'n1', 'n2', 'outro'],
    tokenProvider: key => { tokenCalls++; assert.equal(key, config.site_key); return Promise.resolve('challenge'); },
    fetch: async (url, options) => { requests.push({ url, options }); return sequence.shift(); },
    delay: () => Promise.resolve(), pollMs: 0, onStatus: state => statuses.push(state)
  });
  assert.equal(tokenCalls, 1);
  assert.deepEqual(statuses, ['running']);
  assert.equal(result.durationSec, 37.5);
  assert.equal(result.includedSegmentIds, undefined);
  assert.equal(result.omittedSegmentIds, undefined);
  assert.equal(result.audioUrl, 'https://audio.example.test/v1/jobs/' + jobId + '/audio');
  assert.equal(requests.length, 3);
  const posted = JSON.parse(requests[0].options.body);
  assert.deepEqual(Object.keys(posted).sort(), ['date', 'segment_ids', 'turnstile_token']);
  assert.equal('script' in posted, false);
  assert.equal(requests[0].options.credentials, 'omit');
  assert.equal(requests[0].options.mode, 'cors');
  assert.deepEqual(JSON.parse(requests[0].options.body).segment_ids, ['greeting', 'intro', 'n1', 'n2', 'outro']);

  let renderedOptions;
  context.document = {
    createElement: () => ({ hidden: false, remove() {} }),
    body: { appendChild() {} }, head: { appendChild() {} }
  };
  context.turnstile = { render(_node, opts) { renderedOptions = opts; opts.callback('challenge-token'); return 1; }, execute() {}, remove() {} };
  await rejects(context.KnuOnePass.create({ config, date: '2026-10-09', segmentIds: ['greeting','outro'],
    fetch: async () => ({ ok: false, status: 503 }) }), 'request_failed');
  assert.equal(renderedOptions.execution, 'execute');
  assert.equal(renderedOptions.action, 'onepass');

  await rejects(context.KnuOnePass.create({ config, date: '2026-10-09', segmentIds: ['intro', 'outro'],
    tokenProvider: () => Promise.resolve('token'), fetch: async () => ({ ok: false, status: 503 }) }), 'request_failed');
  console.log('one-pass client selection, ID-only payload, polling and service-error behavior: passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
