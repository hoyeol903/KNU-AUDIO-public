import {applyPlaybackSpeed, playbackSpeed} from './playback-speed.mjs';
import {combineAudio} from './continuous-audio.mjs';
import {requiredChannels, selectPlaylist} from './playlist.mjs';
const $ = id => document.getElementById(id);
let manifest, selected = new Set(), excluded = new Set(), queue = [], generation = 0, mergedURL, pending;
const speech = $('speech'), bgm = new Audio();
let context, musicGain;
bgm.loop = true; bgm.preload = 'none';
function message(text) { $('status').textContent = text; }
function safeURL(value) {
  const url = new URL(value, location.href);
  if (!['http:', 'https:'].includes(url.protocol)) throw Error('지원하지 않는 주소');
  return url.href;
}
function element(tag, text) { const e = document.createElement(tag); e.textContent = text; return e; }
function stop() {
  generation++; pending?.abort(); pending = null; speech.pause(); speech.removeAttribute('src'); speech.load();
  if (mergedURL) URL.revokeObjectURL(mergedURL); mergedURL = null;
  $('download').hidden = true; $('download').removeAttribute('href');
  bgm.pause(); bgm.currentTime = 0;
}
function audioContext() {
  if (!context) context = new (window.AudioContext || window.webkitAudioContext)({sampleRate:24000});
  return context;
}
function save() {
  try {localStorage.setItem('knua-v2', JSON.stringify({department: $('department').value, voice: $('voice').value, speed: playbackSpeed($('speed').value), selected: [...selected]}));} catch {}
}
async function musicPlay() {
  if (!manifest.bgm || !$('music').checked || speech.paused) return;
  try {
    audioContext();
    if (!musicGain) {
      musicGain = context.createGain();
      context.createMediaElementSource(bgm).connect(musicGain).connect(context.destination);
    }
    musicGain.gain.value = Number($('volume').value) / 100;
    await context.resume();
    if ($('music').checked && !speech.paused) await bgm.play();
  } catch (error) { if (error.name === 'AbortError') return; message('배경음악을 시작하지 못했어요. 음악 선택을 껐다 켜서 다시 시도해 주세요.'); }
}
async function playCombined() {
  if (mergedURL) {speech.currentTime = 0; bgm.currentTime = 0; try {await speech.play();} catch {message('플레이어의 재생 버튼을 눌러 주세요.');} return;}
  const ticket = generation, controller = new AbortController(); pending = controller;
  const selection = queue.slice(), voice = $('voice').value;
  $('start').disabled = true;
  message('내 브리핑을 한 편으로 준비하고 있어요…');
  try {
    const ctx = audioContext(); await ctx.resume();
    const blob = await combineAudio(selection.map(s => safeURL(s.audio[voice].url)), {
      context:ctx, signal:controller.signal,
      onProgress:(done, total) => {if (ticket === generation) message(`음성 준비 중 · ${done} / ${total}`);}
    });
    if (ticket !== generation) return;
    mergedURL = URL.createObjectURL(blob); speech.src = mergedURL; applyPlaybackSpeed(speech, $('speed').value);
    $('download').href = mergedURL; $('download').download = `크누아-${manifest.date}-${voice}.wav`; $('download').hidden = false;
    $('now').textContent = '나의 아침 브리핑';
    $('start').textContent = '처음부터 다시 듣기';
    message('한 편의 브리핑이 준비됐어요. 진행 막대로 원하는 부분을 찾아 들을 수 있어요.');
    try {await speech.play();} catch {message('준비됐어요! 플레이어의 재생 버튼을 눌러 주세요.');}
  } catch (error) {
    if (ticket === generation && error.name !== 'AbortError') message(error.message || '음성을 준비하지 못했어요. 다시 시도해 주세요.');
  } finally {
    if (ticket === generation) {$('start').disabled = false; pending = null;}
  }
}
speech.addEventListener('pause', () => bgm.pause());
speech.addEventListener('waiting', () => bgm.pause());
speech.addEventListener('playing', musicPlay);
speech.addEventListener('ended', () => {bgm.pause(); message('오늘의 브리핑이 끝났어요. 좋은 하루 보내세요!');});
speech.addEventListener('error', () => {bgm.pause(); message('이 음성을 불러오지 못했어요. 화면을 새로고침한 뒤 다시 준비해 주세요.');});
bgm.addEventListener('error', () => { $('music').checked = false; message('배경음악을 불러오지 못해 음성만 재생해요.'); });
$('start').onclick = playCombined;
$('music').onchange = () => $('music').checked ? musicPlay() : bgm.pause();
$('volume').oninput = () => {if (musicGain) musicGain.gain.value = Number($('volume').value) / 100;};

function renderQueue() {
  stop(); save();
  queue = selectPlaylist(manifest, [...selected], [...excluded]);
  $('playlist').replaceChildren();
  for (const s of queue) {
    const li = element('li', s.title), detail = document.createElement('details');
    detail.append(element('summary', '대본 보기'), element('p', s.script));
    const links = s.url ? [{source_url:s.url, title:'공지 원문'}] : (s.events || []).filter(e => e.source_url);
    for (const link of links) {const a = element('a', link.title); a.href = safeURL(link.source_url); a.target = '_blank'; a.rel = 'noopener noreferrer'; detail.append(a);}
    li.append(detail); $('playlist').append(li);
  }
  const ready = queue.length > 0 && queue.every(s => s.audio[$('voice').value]);
  updateDuration();
  $('start').disabled = !ready; $('start').textContent = '내 브리핑 듣기';
  $('now').textContent = '나만의 아침을 준비했어요';
  message(ready ? '내 브리핑 듣기를 누르면 선택한 소식이 하나의 음성으로 준비돼요.' : '안내 음성이 아직 생성되지 않았어요. 대본과 선택 기능은 확인할 수 있어요.');
  $('issues').replaceChildren();
  for (const c of manifest.channels.filter(c => selected.has(c.id) && !c.available)) $('issues').append(element('li', c.name + ': 이번 입력에 자료가 없습니다. 해당 채널 수집이 필요합니다.'));
  for (const issue of manifest.warnings) $('issues').append(element('li', `${issue.source}: ${issue.message}`));
  if (!$('issues').children.length) $('issues').append(element('li', '전달된 수집 오류가 없습니다. 원문에서 최신 정보를 확인해 주세요.'));
}
function renderNotices() {
  $('notices').replaceChildren();
  const choices = manifest.segments.filter(s => s.kind === 'notice' && s.channel_ids.some(id => selected.has(id)));
  for (const s of choices) {
    const label = document.createElement('label'); label.className='choice';
    const box = document.createElement('input'); box.type='checkbox'; box.checked = !excluded.has(s.id);
    box.onchange = () => {box.checked ? excluded.delete(s.id) : excluded.add(s.id); renderQueue();};
    label.append(box, element('span', s.title)); $('notices').append(label);
  }
  if (!choices.length) $('notices').append(element('p', '이번에 안내할 공지가 없어요.'));
}
function renderChannels() {
  const mandatory = new Set(requiredChannels(manifest, $('department').value));
  for (const id of mandatory) selected.add(id);
  $('channels').replaceChildren(); $('meals').replaceChildren();
  for (const c of manifest.channels) {
    if (c.type !== 'meal' && !$('filter').value.split(' ').every(word => c.name.includes(word))) continue;
    const label = document.createElement('label'); label.className='choice';
    const box = document.createElement('input'); box.type='checkbox'; box.checked=selected.has(c.id); box.disabled=mandatory.has(c.id);
    box.onchange = () => {box.checked ? selected.add(c.id) : selected.delete(c.id); renderNotices(); renderQueue();};
    label.append(box, element('span', c.name + (mandatory.has(c.id) ? ' · 기본' : '') + (!c.available ? ' · 자료 미수집' : '')));
    $(c.type === 'meal' ? 'meals' : 'channels').append(label);
  }
}
$('filter').oninput = renderChannels;
$('department').onchange = () => {
  selected = new Set([...selected].filter(id => manifest.channels.find(c => c.id === id)?.type === 'meal'));
  excluded.clear(); renderChannels(); renderNotices(); renderQueue();
};
$('voice').onchange = renderQueue;
$('speed').onchange = () => {applyPlaybackSpeed(speech, $('speed').value); save(); updateDuration();};
function updateDuration() {
  const ready = queue.length > 0 && queue.every(s => s.audio[$('voice').value]);
  const seconds = queue.reduce((sum, s) => sum + (s.audio[$('voice').value]?.duration_sec || 0), 0);
  $('count').textContent = '브리핑 한 편' + (ready ? ` · 약 ${Math.ceil(seconds / playbackSpeed($('speed').value) / 60)}분` : ' · 대본 미리보기');
}

try {
  const response = await fetch('manifest.json', {cache:'no-cache'});
  if (!response.ok) throw Error('브리핑 목록을 불러올 수 없어요.');
  manifest = await response.json();
  if (manifest.schema_version !== 2) throw Error('지원하지 않는 브리핑 형식이에요.');
  for (const [id, voice] of Object.entries(manifest.voices)) {const option=element('option', voice.name); option.value=id; $('voice').append(option);}
  for (const d of manifest.departments) {const option = element('option', `${d.college} · ${d.name}`); option.value=d.id; $('department').append(option);}
  try {
    const saved = JSON.parse(localStorage.getItem('knua-v2') || '{}');
    if (manifest.departments.some(d => d.id === saved.department)) $('department').value=saved.department;
    if (Object.hasOwn(manifest.voices, saved.voice)) $('voice').value=saved.voice;
    $('speed').value = String(playbackSpeed(saved.speed));
    applyPlaybackSpeed(speech, $('speed').value);
    selected = new Set((Array.isArray(saved.selected) ? saved.selected : []).filter(id => manifest.channels.some(c => c.id === id)));
  } catch {}
  const now = new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  $('date').textContent=`자료 기준일 ${manifest.date} · 공통 인사 → 날씨 → 공지 → 학식 → D-day → 응원 멘트 → 마무리`;
  const notices = [];
  if (manifest.date !== now) notices.push(`오늘 자료가 아닌 ${manifest.date} 자료예요. 날짜와 D-day는 자료 기준일 기준입니다.`);
  if (manifest.mode === 'text-only') notices.push('대본 미리보기입니다. 음성은 아직 준비되지 않았어요.');
  $('banner').textContent = notices.join(' ') || '오늘의 자료로 준비한 브리핑이에요. 선택한 채널의 수집 상태도 확인해 주세요.';
  if (manifest.bgm) {$('music').checked=true; bgm.src=safeURL(manifest.bgm.path); $('music').disabled=false; $('volume').disabled=false; $('volume').value=manifest.bgm.volume*100; $('music-credit').textContent=manifest.bgm.attribution;}
  else $('music-credit').textContent='배경음악 파일 연결 전';
  $('attribution').textContent = `음성: ${manifest.tts?.provider || (manifest.mode === 'slm-melo' ? 'MeloTTS Korean (이전 생성본)' : 'Qwen3-TTS')} · 대본: Qwen3 SLM · 규칙 검사 적용`;
  renderChannels(); renderNotices(); renderQueue();
} catch (error) { $('banner').textContent=error.message + ' 안내서대로 HTTP 서버에서 열었는지 확인해 주세요.'; }
