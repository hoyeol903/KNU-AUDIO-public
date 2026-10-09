import test from 'node:test';
import assert from 'node:assert/strict';
import {encodeWav, combineAudio} from '../web/player/continuous-audio.mjs';

test('WAV 길이와 구간 순서를 보존하고 경계 샘플을 잃지 않는다', () => {
  const result = encodeWav([new Int16Array([12,-34]),new Int16Array([56,78])],24000);
  const view = new DataView(result);
  assert.equal(result.byteLength, 52);
  assert.equal(view.getUint32(24,true),24000);
  assert.equal(view.getUint32(40,true),8);
  assert.deepEqual(Array.from({length:4},(_,i)=>view.getInt16(44+i*2,true)),[12,-34,56,78]);
});

test('선택을 바꾸어 취소하면 디코딩 뒤 이전 음성을 반환하지 않는다', async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  globalThis.fetch = async () => ({ok:true,arrayBuffer:async()=>new ArrayBuffer(0)});
  try {
    await assert.rejects(combineAudio(['audio/a.mp3'],{
      signal:controller.signal,
      context:{sampleRate:24000, decodeAudioData:async()=>{controller.abort();return {};}}
    }),{name:'AbortError'});
  } finally {globalThis.fetch = original;}
});
