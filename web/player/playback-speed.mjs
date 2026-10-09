export const SPEEDS = Object.freeze([0.75, 1, 1.25, 1.5, 1.75, 2]);
export function playbackSpeed(value) {
  const number = Number(value);
  return SPEEDS.includes(number) ? number : 1;
}
export function applyPlaybackSpeed(audio, value) {
  const speed = playbackSpeed(value);
  audio.defaultPlaybackRate = speed;
  audio.playbackRate = speed;
  audio.preservesPitch = true;
  if ('webkitPreservesPitch' in audio) audio.webkitPreservesPitch = true;
  return speed;
}
