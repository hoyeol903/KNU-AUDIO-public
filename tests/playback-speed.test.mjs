import test from 'node:test';
import assert from 'node:assert/strict';
import {applyPlaybackSpeed, playbackSpeed} from '../web/player/playback-speed.mjs';
test('invalid saved speed falls back to normal', () => {
  for (const value of [null, undefined, 'bad', 0, 5, -1]) assert.equal(playbackSpeed(value), 1);
  assert.equal(playbackSpeed('1.5'), 1.5);
});
test('speed changes live without resetting the audio or its pitch', () => {
  const audio = {currentTime:12, src:'blob:current', webkitPreservesPitch:false};
  applyPlaybackSpeed(audio, '1.75');
  assert.equal(audio.playbackRate, 1.75);
  assert.equal(audio.defaultPlaybackRate, 1.75);
  assert.equal(audio.currentTime, 12);
  assert.equal(audio.src, 'blob:current');
  assert.equal(audio.preservesPitch, true);
  assert.equal(audio.webkitPreservesPitch, true);
});
