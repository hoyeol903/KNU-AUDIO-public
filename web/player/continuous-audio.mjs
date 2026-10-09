// Combine only the current selection locally; no per-user synthesis request.
export function encodeWav(chunks, sampleRate) {
  const frames = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + frames * 2), view = new DataView(buffer);
  const label = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  label(0, 'RIFF'); view.setUint32(4, 36 + frames * 2, true); label(8, 'WAVE');
  label(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  label(36, 'data'); view.setUint32(40, frames * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const value of chunk) {
    view.setInt16(offset, value, true); offset += 2;
  }
  return buffer;
}

export async function combineAudio(urls, {context, signal, onProgress = () => {}}) {
  const chunks = [];
  let frames = 0;
  for (let i = 0; i < urls.length; i++) {
    signal.throwIfAborted();
    const response = await fetch(urls[i], {signal});
    if (!response.ok) throw Error('음성 파일을 불러오지 못했어요. 다시 시도해 주세요.');
    const decoded = await context.decodeAudioData(await response.arrayBuffer());
    signal.throwIfAborted();
    frames += decoded.length;
    if (frames / context.sampleRate > 15 * 60) throw Error('한 번에 최대 15분까지 준비할 수 있어요. 공지를 조금 줄여 주세요.');
    const pcm = new Int16Array(decoded.length);
    const channels = Array.from({length: decoded.numberOfChannels}, (_, ch) => decoded.getChannelData(ch));
    for (let frame = 0; frame < pcm.length; frame++) {
      const value = Math.max(-1, Math.min(1, channels.reduce((sum, ch) => sum + ch[frame], 0) / channels.length));
      pcm[frame] = Math.round(value * (value < 0 ? 32768 : 32767));
    }
    chunks.push(pcm);
    onProgress(i + 1, urls.length);
  }
  signal.throwIfAborted();
  return new Blob([encodeWav(chunks, context.sampleRate)], {type: 'audio/wav'});
}
